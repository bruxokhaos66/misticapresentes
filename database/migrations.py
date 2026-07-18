import os
import secrets

from config import DOCS_PATH, hash_password_pbkdf2
from . import connection as _connection
from .connection import query_db

_BANCOS_MIGRADOS: set[str] = set()


def _exec_tolerante(sql, params=None):
    """Executa uma migração (ALTER TABLE/CREATE INDEX) tolerando apenas o erro
    esperado de coluna/índice já existente; qualquer outro erro é logado em vez
    de ser silenciosamente descartado, para não mascarar falhas reais de schema
    (disco cheio, banco travado, SQL inválido etc.)."""
    try:
        if params is not None:
            query_db(sql, params, commit=True)
        else:
            query_db(sql, commit=True)
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate column" not in msg and "already exists" not in msg:
            print(f"[migrations] falha inesperada ao aplicar '{sql[:120]}': {exc}")


def _migrar_pedidos_de_vendas():
    """Move para `pedidos`/`pedidos_itens` as linhas de `vendas` criadas pelo site
    (origem_sync='site'), que antes ficavam misturadas com vendas reais do caixa.
    Idempotente: só migra o que ainda não foi migrado, então pode rodar a cada
    inicialização sem custo relevante depois da primeira vez."""
    pendentes = query_db("SELECT id FROM vendas WHERE origem_sync='site' AND id NOT IN (SELECT id FROM pedidos)")
    if not pendentes:
        return
    ids = [row[0] for row in pendentes]
    placeholders = ",".join("?" for _ in ids)
    query_db(
        f"""
        INSERT INTO pedidos (
            id, cliente, data_venda, data_iso, dia_operacional, subtotal, desconto, taxa,
            total_final, forma_pagamento, vendedor, status, origem, observacao_pedido,
            estoque_baixado, estoque_baixado_em, estoque_reposto_cancelamento, estoque_reposto_em, expira_em
        )
        SELECT
            id, cliente, data_venda, data_iso, dia_operacional, subtotal, desconto, taxa,
            total_final, forma_pagamento, vendedor, status, COALESCE(origem_sync,'site'), observacao_pedido,
            COALESCE(estoque_baixado,0), estoque_baixado_em, COALESCE(estoque_reposto_cancelamento,0), estoque_reposto_em, expira_em
        FROM vendas WHERE id IN ({placeholders})
        """,
        ids,
        commit=True,
    )
    query_db(
        f"""
        INSERT INTO pedidos_itens (id, pedido_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
        SELECT id, venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total
        FROM vendas_itens WHERE venda_id IN ({placeholders})
        """,
        ids,
        commit=True,
    )
    query_db(f"DELETE FROM vendas_itens WHERE venda_id IN ({placeholders})", ids, commit=True)
    query_db(f"DELETE FROM vendas WHERE id IN ({placeholders})", ids, commit=True)
    # pedido_status_log e pagamentos já referenciam o mesmo id (preservado na
    # migração acima), então continuam válidos sem nenhuma alteração aqui.


def _backfill_tipo_item_pedidos_itens():
    """Corrige, uma única vez por pedido, o valor padrão 'legado_ambiguo' que
    o ALTER TABLE de pedidos_itens.tipo_item grava em itens criados antes
    dessa coluna existir (ver init_db). Nunca promove um item ambíguo para
    'fisico' por padrão nem por descarte de evidência — só reclassifica
    quando há evidência estrutural inequívoca em audit_log, e nunca a partir
    do estoque atual do produto (já pode ter mudado) ou de texto livre
    (nome/categoria do produto).

    A evidência usada é só entidade='pedido' + acao — nunca o conteúdo JSON
    de dados_depois (que pode ter formato antigo, estar ausente ou ser
    inválido; nenhuma dessas variações importa aqui):
    - acao='criar_sob_encomenda': gravado só por
      backend/preorder_checkout.py::registrar_checkout_publico, no mesmo
      instante em que o pedido é criado. Esse caminho é o único que produz
      itens sob encomenda, e sempre grava esse evento.
    - acao='criar': gravado só por
      backend/site_stock_routes.py::registrar_venda_site (o caminho de
      pedido com estoque físico), também no instante da criação.

    Um pedido cujo audit_log tenha as duas evidências ao mesmo tempo (nunca
    deveria acontecer — cada pedido passa por exatamente um dos dois
    caminhos de criação — mas pode ocorrer por dado corrompido/manipulado)
    é tratado como conflito e permanece 'legado_ambiguo' em vez de escolher
    um lado arbitrariamente. Pedidos sem nenhuma das duas evidências (ex.:
    migrados de `vendas` antes de audit_log existir, ou audit_log ausente/
    inacessível) também permanecem 'legado_ambiguo': ficam bloqueados para
    conciliação administrativa na confirmação de pagamento (ver
    backend/order_status_routes.py::baixar_estoque_do_pedido) em vez de
    serem tratados como físicos silenciosamente.

    Idempotente: o WHERE tipo_item='legado_ambiguo' faz rodar de novo não
    reclassificar itens já resolvidos (nem os que permanecem ambíguos).

    init_db() (e, portanto, esta função) roda a cada conectar() — em produção,
    a cada requisição que abre uma conexão. Sem a saída antecipada abaixo,
    isso escanearia audit_log inteiro (que cresce com toda a atividade do
    sistema, não só criação de pedido) em toda requisição, mesmo quando não
    há mais nenhum item 'legado_ambiguo' para resolver."""
    try:
        ha_pendente = query_db("SELECT 1 FROM pedidos_itens WHERE tipo_item='legado_ambiguo' LIMIT 1")
        if not ha_pendente:
            return
        encomenda_ids = {
            row[0]
            for row in query_db("SELECT DISTINCT entidade_id FROM audit_log WHERE entidade='pedido' AND acao='criar_sob_encomenda'")
            if row[0]
        }
        fisico_ids = {
            row[0]
            for row in query_db("SELECT DISTINCT entidade_id FROM audit_log WHERE entidade='pedido' AND acao='criar'")
            if row[0]
        }
    except Exception:
        return

    conflito_ids = encomenda_ids & fisico_ids
    for pedido_id in encomenda_ids - conflito_ids:
        _exec_tolerante(
            "UPDATE pedidos_itens SET tipo_item='sob_encomenda' WHERE pedido_id=? AND tipo_item='legado_ambiguo'",
            (pedido_id,),
        )
    for pedido_id in fisico_ids - conflito_ids:
        _exec_tolerante(
            "UPDATE pedidos_itens SET tipo_item='fisico' WHERE pedido_id=? AND tipo_item='legado_ambiguo'",
            (pedido_id,),
        )


def init_db():
    """Aplica todas as migrações (todas idempotentes: `CREATE TABLE IF NOT
    EXISTS` / `ALTER TABLE` tolerante a coluna já existente).

    `backend.database.conectar()` chama `init_db()` a cada conexão aberta
    (uma por requisição HTTP, mais as tarefas periódicas do lifespan) --
    sem cache, isso reexecuta dezenas de instruções DDL por requisição. Sob
    carga concorrente (tarefa periódica + requisições simultâneas), a
    contenção de lock resultante já foi observada causando falhas
    intermitentes em rotas que tratam qualquer erro como "desativado"
    (fail-closed), como `backend.isis2_homolog`. Por isso o corpo real só
    roda uma vez por `DB_PATH` neste processo; chamadas repetidas para o
    mesmo caminho (o caso comum) são no-op.

    A cache é invalidada se o arquivo do banco não existir mais no disco --
    disco efêmero (ver `tests/test_persistencia_banco.py`) pode fazer o
    arquivo desaparecer entre uma chamada e outra sem que `DB_PATH` mude;
    tratar só a string do caminho como chave de cache, sem checar o disco,
    deixaria o schema sem ser recriado depois desse tipo de restart."""
    db_path_atual = _connection.DB_PATH
    if db_path_atual in _BANCOS_MIGRADOS and not os.path.exists(db_path_atual):
        _BANCOS_MIGRADOS.discard(db_path_atual)
    if db_path_atual in _BANCOS_MIGRADOS:
        return

    query_db("CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY, codigo_p TEXT, nome TEXT, preco REAL, quantidade INTEGER, categoria TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)", commit=True)
    query_db(
        """
        CREATE TABLE IF NOT EXISTS avaliacoes_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            nome_cliente TEXT NOT NULL,
            nota INTEGER NOT NULL,
            comentario TEXT,
            data_hora TEXT,
            aprovado INTEGER DEFAULT 1,
            ip_hash TEXT
        )
        """,
        commit=True,
    )
    query_db(
        "CREATE INDEX IF NOT EXISTS idx_avaliacoes_produto ON avaliacoes_produtos(produto_id, aprovado)",
        commit=True,
    )
    query_db("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, cpf TEXT, endereco TEXT, nascimento TEXT)", commit=True)
    for col, typ in [("telefone", "TEXT"), ("cpf", "TEXT"), ("endereco", "TEXT"), ("nascimento", "TEXT")]:
        _exec_tolerante(f"ALTER TABLE clientes ADD COLUMN {col} {typ}")
    query_db("CREATE TABLE IF NOT EXISTS vendas (id INTEGER PRIMARY KEY, cliente TEXT, data_venda TEXT, subtotal REAL, desconto REAL, taxa REAL, total_final REAL, forma_pagamento TEXT, vendedor TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, cpf TEXT, endereco TEXT, telefone TEXT, login TEXT UNIQUE, senha_hash TEXT, perfil TEXT)", commit=True)
    _exec_tolerante("ALTER TABLE usuarios ADD COLUMN senha_salt TEXT")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS painel_sessoes (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER,
            login TEXT,
            nome TEXT,
            perfil TEXT,
            ip TEXT,
            user_agent TEXT,
            criada_em TEXT,
            expira_em TEXT,
            ultimo_acesso TEXT
        )
        """,
        commit=True,
    )
    query_db("CREATE INDEX IF NOT EXISTS idx_painel_sessoes_expira ON painel_sessoes(expira_em)", commit=True)

    query_db(
        """
        CREATE TABLE IF NOT EXISTS painel_login_tentativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT,
            ip TEXT,
            user_agent TEXT,
            sucesso INTEGER,
            data_hora TEXT
        )
        """,
        commit=True,
    )
    query_db(
        "CREATE INDEX IF NOT EXISTS idx_painel_tentativas_login ON painel_login_tentativas(login, data_hora)",
        commit=True,
    )

    for col, typ in [("telephone", "TEXT")]:
        _exec_tolerante(f"ALTER TABLE clientes ADD COLUMN {col} {typ}")
    _exec_tolerante("UPDATE clientes SET telefone=COALESCE(NULLIF(telefone,''), telephone) WHERE telephone IS NOT NULL")
    _exec_tolerante("ALTER TABLE usuarios ADD COLUMN telephone TEXT")
    _exec_tolerante("UPDATE usuarios SET telefone=COALESCE(NULLIF(telefone,''), telephone) WHERE telephone IS NOT NULL")

    query_db("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, usuario TEXT, acao TEXT, detalhes TEXT, data_hora TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS vendas_itens (id INTEGER PRIMARY KEY, venda_id INTEGER, codigo_p TEXT, nome_p TEXT, quantidade INTEGER, custo_unitario REAL DEFAULT 0.0, valor_unitario REAL DEFAULT 0.0, valor_total REAL DEFAULT 0.0)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS fornecedores (id INTEGER PRIMARY KEY, nome TEXT, whatsapp TEXT, cidade TEXT, observacoes TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS contas_a_pagar (id INTEGER PRIMARY KEY, descricao TEXT, valor REAL, data_vencimento TEXT, status TEXT DEFAULT 'Pendente')", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS fluxo_caixa (id INTEGER PRIMARY KEY, tipo TEXT, descricao TEXT, valor REAL, data_hora TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS caixa_diario (id INTEGER PRIMARY KEY, data_abertura TEXT, data_fechamento TEXT, saldo_inicial REAL, saldo_final REAL, status TEXT DEFAULT 'Fechado', operador TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS movimentacao_estoque (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, quantidade INTEGER, tipo TEXT, motivo TEXT, usuario TEXT, data_hora TEXT, estoque_anterior INTEGER, estoque_posterior INTEGER, venda_id INTEGER)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS isis_memoria (id INTEGER PRIMARY KEY, tipo TEXT, chave TEXT, valor TEXT, pergunta TEXT, resposta TEXT, usuario TEXT, data_hora TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS isis_logs (id INTEGER PRIMARY KEY, comando_recebido TEXT, acao_detectada TEXT, usuario TEXT, resultado TEXT, erro TEXT, data_hora TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS pesquisas_online (id INTEGER PRIMARY KEY, consulta TEXT, resultados TEXT, usuario TEXT, data_hora TEXT, confirmado INTEGER DEFAULT 0)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS encomendas (id INTEGER PRIMARY KEY, cliente TEXT, produto TEXT, quantidade INTEGER, origem TEXT, custo_estimado REAL, preco_sugerido REAL, margem REAL, status TEXT DEFAULT 'Pendente', observacao TEXT, data_criacao TEXT, data_atualizacao TEXT)", commit=True)

    for col, typ in [("categoria", "TEXT"), ("data_atualizacao", "TEXT")]:
        _exec_tolerante(f"ALTER TABLE isis_memoria ADD COLUMN {col} {typ}")
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_isis_logs_data ON isis_logs(data_hora)",
        "CREATE INDEX IF NOT EXISTS idx_pesquisas_online_data ON pesquisas_online(data_hora)",
        "CREATE INDEX IF NOT EXISTS idx_encomendas_status ON encomendas(status)",
    ]:
        _exec_tolerante(idx)

    query_db("CREATE TABLE IF NOT EXISTS historico_precos (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, preco_antigo REAL, preco_novo REAL, custo_antigo REAL, custo_novo REAL, usuario TEXT, data_hora TEXT, motivo TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS inventario_estoque (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, quantidade_sistema INTEGER, quantidade_contada INTEGER, diferenca INTEGER, usuario TEXT, data_hora TEXT, observacao TEXT)", commit=True)

    for col, typ in [("ativo", "INTEGER DEFAULT 1")]:
        _exec_tolerante(f"ALTER TABLE produtos ADD COLUMN {col} {typ}")
    for col, typ in [("dinheiro_sistema", "REAL DEFAULT 0.0"), ("pix_sistema", "REAL DEFAULT 0.0"), ("debito_sistema", "REAL DEFAULT 0.0"), ("credito_sistema", "REAL DEFAULT 0.0"), ("dinheiro_informado", "REAL DEFAULT 0.0"), ("pix_informado", "REAL DEFAULT 0.0"), ("debito_informado", "REAL DEFAULT 0.0"), ("credito_informado", "REAL DEFAULT 0.0"), ("diferenca_caixa", "REAL DEFAULT 0.0")]:
        _exec_tolerante(f"ALTER TABLE caixa_diario ADD COLUMN {col} {typ}")

    for col, typ in [("custo", "REAL DEFAULT 0.0"), ("lucro", "REAL DEFAULT 0.0"), ("estoque_minimo", "INTEGER DEFAULT 0")]:
        _exec_tolerante(f"ALTER TABLE produtos ADD COLUMN {col} {typ}")

    # Colunas do catálogo completo do site (antes duplicadas em backend/product_routes.py).
    for col, typ in [
        ("marca", "TEXT"),
        ("descricao", "TEXT"),
        ("imagem_url", "TEXT"),
        ("imagens_json", "TEXT"),
        ("link_externo", "TEXT"),
        ("selo", "TEXT"),
        ("atualizado_em", "TEXT"),
    ]:
        _exec_tolerante(f"ALTER TABLE produtos ADD COLUMN {col} {typ}")

    # Colunas de pedidos (site) sobre a tabela vendas (antes duplicadas em
    # backend/order_status_routes.py, backend/order_api_guard_inner_routes.py,
    # backend/main.py e backend/user_sync_routes.py).
    for col, typ in [
        ("observacao_pedido", "TEXT"),
        ("estoque_baixado", "INTEGER DEFAULT 0"),
        ("estoque_baixado_em", "TEXT"),
        ("expira_em", "TEXT"),
        ("estoque_reposto_cancelamento", "INTEGER DEFAULT 0"),
        ("estoque_reposto_em", "TEXT"),
        ("origem_sync", "TEXT"),
        ("local_id", "INTEGER"),
    ]:
        _exec_tolerante(f"ALTER TABLE vendas ADD COLUMN {col} {typ}")
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_vendas_local_id ON vendas(local_id)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS pedido_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            usuario TEXT DEFAULT 'Admin',
            observacao TEXT DEFAULT '',
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        commit=True,
    )

    query_db(
        """
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            forma TEXT DEFAULT 'Pix',
            valor REAL DEFAULT 0,
            status TEXT DEFAULT 'Aguardando',
            comprovante TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            usuario TEXT DEFAULT 'Admin',
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        commit=True,
    )
    # Conciliação de valor: o backend é a única fonte de verdade do total do
    # pedido (pedidos.total_final). Estas colunas registram, para cada
    # pagamento recebido, o valor esperado no momento da conciliação e o
    # resultado da comparação (ok/divergente), para que um valor recebido
    # incorreto nunca confirme o pedido silenciosamente e a divergência fique
    # auditável em vez de descartada. Aditivo, com default seguro, não apaga
    # dados de bancos já existentes.
    _exec_tolerante("ALTER TABLE pagamentos ADD COLUMN valor_esperado REAL")
    _exec_tolerante("ALTER TABLE pagamentos ADD COLUMN status_conciliacao TEXT NOT NULL DEFAULT 'nao_avaliado'")
    _exec_tolerante("ALTER TABLE pagamentos ADD COLUMN motivo_divergencia TEXT")

    # Auditoria unificada de mutações (quem mudou o quê, quando), complementar
    # aos históricos específicos já existentes (movimentacao_estoque,
    # historico_precos, pedido_status_log).
    query_db(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entidade TEXT NOT NULL,
            entidade_id TEXT,
            acao TEXT NOT NULL,
            usuario TEXT DEFAULT 'Sistema',
            dados_antes TEXT,
            dados_depois TEXT,
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        commit=True,
    )
    for sql_idx in [
        "CREATE INDEX IF NOT EXISTS idx_audit_log_entidade ON audit_log(entidade, entidade_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_data ON audit_log(data_hora)",
    ]:
        _exec_tolerante(sql_idx)

    # Idempotência: evita que o mesmo pedido/pagamento seja duplicado por
    # reenvio de requisição (dupla submissão de formulário, retry de rede etc).
    query_db(
        """
        CREATE TABLE IF NOT EXISTS idempotency_keys (
            escopo TEXT NOT NULL,
            chave TEXT NOT NULL,
            resposta TEXT NOT NULL,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (escopo, chave)
        )
        """,
        commit=True,
    )
    # payload_hash guarda um hash canônico do pedido associado à chave, para
    # detectar reuso da mesma Idempotency-Key com um carrinho diferente
    # (retorna 409 em vez de reaproveitar a resposta de outro pedido).
    # status distingue uma chave reivindicada (mas ainda em processamento) de
    # uma chave com resposta final salva, permitindo que duas requisições
    # concorrentes com a mesma chave disputem a reivindicação atomicamente.
    _exec_tolerante("ALTER TABLE idempotency_keys ADD COLUMN payload_hash TEXT")
    _exec_tolerante("ALTER TABLE idempotency_keys ADD COLUMN status TEXT NOT NULL DEFAULT 'concluido'")

    # Pedidos (site) são uma entidade própria, separada de vendas (caixa/POS).
    # Os IDs são preservados ao migrar de `vendas` para não quebrar links já
    # emitidos (WhatsApp, e-mails de confirmação etc.).
    query_db(
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            data_venda TEXT,
            data_iso TEXT,
            dia_operacional TEXT,
            subtotal REAL DEFAULT 0.0,
            desconto REAL DEFAULT 0.0,
            taxa REAL DEFAULT 0.0,
            total_final REAL DEFAULT 0.0,
            forma_pagamento TEXT,
            vendedor TEXT,
            status TEXT DEFAULT 'Aguardando pagamento',
            origem TEXT DEFAULT 'site',
            observacao_pedido TEXT,
            estoque_baixado INTEGER DEFAULT 0,
            estoque_baixado_em TEXT,
            estoque_reposto_cancelamento INTEGER DEFAULT 0,
            estoque_reposto_em TEXT,
            expira_em TEXT,
            telefone TEXT,
            estoque_reservado INTEGER DEFAULT 0,
            pix_txid TEXT,
            pix_copia_cola TEXT,
            confirmado_automaticamente INTEGER DEFAULT 0
        )
        """,
        commit=True,
    )
    query_db(
        """
        CREATE TABLE IF NOT EXISTS pedidos_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            codigo_p TEXT,
            nome_p TEXT,
            quantidade INTEGER,
            custo_unitario REAL DEFAULT 0.0,
            valor_unitario REAL DEFAULT 0.0,
            valor_total REAL DEFAULT 0.0
        )
        """,
        commit=True,
    )
    for sql_idx in [
        "CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_dia_operacional ON pedidos(dia_operacional)",
        "CREATE INDEX IF NOT EXISTS idx_pedidos_itens_pedido ON pedidos_itens(pedido_id)",
    ]:
        _exec_tolerante(sql_idx)
    _migrar_pedidos_de_vendas()

    # Classificação do item do pedido: 'fisico' (tem estoque físico, baixa e
    # repõe normalmente), 'sob_encomenda' (estoque físico zero por definição —
    # ver backend/preorder_checkout.py — nunca baixa nem repõe estoque físico,
    # nunca gera movimentação fictícia) ou 'legado_ambiguo' (não sabemos qual
    # dos dois é — ver abaixo). O CHECK trava qualquer outro valor no próprio
    # banco, além da validação em Python (ver TIPOS_ITEM_VALIDOS em
    # backend/order_status_routes.py). Persistida no próprio item no momento
    # da criação do pedido (backend/preorder_checkout.py e
    # backend/site_stock_routes.py — sempre calculada pelo servidor a partir
    # do produto autoritativo, nunca aceita de um campo enviado pelo cliente)
    # para que a confirmação de pagamento
    # (backend/order_status_routes.py::baixar_estoque_do_pedido) nunca precise
    # reconsultar produtos.sob_encomenda depois: o produto pode ter sido
    # renomeado, inativado ou ter sua regra de encomenda alterada no catálogo
    # sem que isso mude o que já foi vendido.
    #
    # Aditivo: pedidos_itens antigos (de antes desta coluna existir) recebem
    # 'legado_ambiguo' pelo DEFAULT abaixo — nunca 'fisico'. Um item
    # 'legado_ambiguo' nunca é tratado como físico nem como sob encomenda: a
    # baixa de estoque na confirmação de pagamento bloqueia (409) esse item
    # para conciliação administrativa em vez de adivinhar. _backfill_tipo_item_
    # pedidos_itens (acima) promove para 'fisico'/'sob_encomenda' só quando há
    # evidência estrutural inequívoca em audit_log (nunca o estoque atual do
    # produto, nunca o nome/texto do produto); qualquer pedido sem essa
    # evidência (ou com evidência conflitante) permanece 'legado_ambiguo'.
    _exec_tolerante(
        "ALTER TABLE pedidos_itens ADD COLUMN tipo_item TEXT NOT NULL DEFAULT 'legado_ambiguo' "
        "CHECK(tipo_item IN ('fisico','sob_encomenda','legado_ambiguo'))"
    )
    _backfill_tipo_item_pedidos_itens()

    query_db(
        """
        CREATE TABLE IF NOT EXISTS campanhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT DEFAULT '',
            tipo TEXT NOT NULL DEFAULT 'banner',
            valor REAL DEFAULT 0,
            codigo_cupom TEXT,
            link TEXT,
            ativo INTEGER DEFAULT 1,
            data_inicio TEXT,
            data_fim TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_campanhas_ativo ON campanhas(ativo, data_inicio, data_fim)")

    for tabela, col, typ in [("vendas", "status", "TEXT DEFAULT 'Concluído'"), ("vendas", "data_iso", "TEXT"), ("vendas", "dia_operacional", "TEXT"), ("fluxo_caixa", "data_iso", "TEXT"), ("fluxo_caixa", "forma_pagamento", "TEXT"), ("fluxo_caixa", "caixa_id", "INTEGER"), ("contas_a_pagar", "categoria", "TEXT DEFAULT 'Outros'")]:
        _exec_tolerante(f"ALTER TABLE {tabela} ADD COLUMN {col} {typ}")

    for tabela, colunas in {"categorias": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "clientes": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "usuarios": [("cpf", "TEXT"), ("endereco", "TEXT"), ("telefone", "TEXT"), ("perfil", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT"), ("senha_salt", "TEXT")], "fornecedores": [("whatsapp", "TEXT"), ("cidade", "TEXT"), ("observacoes", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "contas_a_pagar": [("categoria", "TEXT DEFAULT 'Outros'"), ("cancelado_em", "TEXT")], "vendas": [("status", "TEXT DEFAULT 'Concluído'"), ("data_iso", "TEXT"), ("dia_operacional", "TEXT")], "vendas_itens": [("custo_unitario", "REAL DEFAULT 0.0"), ("valor_unitario", "REAL DEFAULT 0.0"), ("valor_total", "REAL DEFAULT 0.0")], "fluxo_caixa": [("data_iso", "TEXT"), ("forma_pagamento", "TEXT"), ("caixa_id", "INTEGER")], "pedidos": [("telefone", "TEXT"), ("estoque_reservado", "INTEGER DEFAULT 0"), ("pix_txid", "TEXT"), ("pix_copia_cola", "TEXT"), ("confirmado_automaticamente", "INTEGER DEFAULT 0"), ("cupom", "TEXT")]}.items():
        for col, typ in colunas:
            _exec_tolerante(f"ALTER TABLE {tabela} ADD COLUMN {col} {typ}")

    _exec_tolerante("UPDATE vendas SET status='Concluído' WHERE status IS NULL OR status=''")
    _exec_tolerante("UPDATE vendas SET dia_operacional=substr(data_venda,1,10) WHERE COALESCE(dia_operacional,'')='' AND length(COALESCE(data_venda,'')) >= 10")

    for sql_idx in ["CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p)", "CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_codigo_unico ON produtos(codigo_p) WHERE codigo_p IS NOT NULL AND codigo_p != ''", "CREATE INDEX IF NOT EXISTS idx_mov_estoque_codigo ON movimentacao_estoque(codigo_p)", "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)", "CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)", "CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_venda)", "CREATE INDEX IF NOT EXISTS idx_vendas_data_iso ON vendas(data_iso)", "CREATE INDEX IF NOT EXISTS idx_vendas_dia_operacional ON vendas(dia_operacional)", "CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status)", "CREATE INDEX IF NOT EXISTS idx_vendas_itens_venda ON vendas_itens(venda_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_id ON fluxo_caixa(caixa_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_forma ON fluxo_caixa(forma_pagamento)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_tipo ON isis_memoria(tipo)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_chave ON isis_memoria(chave)"]:
        _exec_tolerante(sql_idx)

    admin_res = query_db("SELECT senha_hash FROM usuarios WHERE login='admin'")
    if not admin_res:
        senha_temp = "Mistica@" + secrets.token_hex(4)
        salt = secrets.token_hex(16)
        try:
            query_db("INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)", ("Administrador", "admin", hash_password_pbkdf2(senha_temp, salt.encode("utf-8")), salt, "adm", 1), commit=True)
        except Exception as exc:
            # Corrida entre conexões concorrentes chamando init_db() ao mesmo tempo
            # (ex.: tarefa periódica de expiração de pedidos rodando durante outro
            # init_db()): o SELECT acima não viu o admin ainda, mas outra conexão já
            # o inseriu entre o SELECT e este INSERT. Não é erro: o admin existe.
            if "unique" not in str(exc).lower():
                raise
        else:
            try:
                with open(os.path.join(DOCS_PATH, "mistica_senha_admin_inicial.txt"), "w", encoding="utf-8") as f:
                    f.write("Login: admin\nSenha temporaria: " + senha_temp + "\nTroque esta senha no primeiro acesso.\n")
            except Exception as exc:
                print(f"[DB init] Falha ao gravar senha admin temporaria: {exc}")
    for c in ["Velas", "Incensos", "Cristais", "Óleos"]:
        try:
            query_db("INSERT INTO categorias (nome) VALUES (?)", (c,), commit=True)
        except Exception as exc:
            if "unique" not in str(exc).lower():
                print(f"[migrations] falha ao inserir categoria padrão '{c}': {exc}")

    _criar_tabelas_isis_content_studio()
    _criar_tabelas_mercadopago()

    _BANCOS_MIGRADOS.add(db_path_atual)


def _criar_tabelas_isis_content_studio():
    """Isis 2.0 — Fase 3 (Estúdio Inteligente de Conteúdo).

    Infraestrutura de rascunhos diários (nunca publicação automática — ver
    MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED em backend/isis_content_flags.py).
    Todas as tabelas nascem vazias e as feature flags nascem desligadas: criar
    a estrutura aqui não ativa nenhum comportamento novo.
    """
    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_referencia TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pendente',
            iniciado_em TEXT,
            concluido_em TEXT,
            erro TEXT,
            criado_em TEXT NOT NULL
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE UNIQUE INDEX IF NOT EXISTS ux_isis_content_jobs_data ON isis_content_jobs(data_referencia)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            data_referencia TEXT NOT NULL,
            tipo TEXT NOT NULL,
            frase_original TEXT,
            legenda TEXT,
            legenda_curta TEXT,
            hashtags TEXT,
            texto_alternativo TEXT,
            prompt_visual TEXT,
            produto_id INTEGER,
            produto_codigo TEXT,
            produto_nome TEXT,
            justificativa TEXT,
            custo_estimado REAL DEFAULT 0,
            provedor_texto TEXT,
            provedor_imagem TEXT,
            status TEXT NOT NULL DEFAULT 'rascunho',
            aprovado_por TEXT,
            aprovado_em TEXT,
            rejeitado_por TEXT,
            rejeitado_em TEXT,
            motivo_rejeicao TEXT,
            publicado_em TEXT,
            publicado_por TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_drafts_data ON isis_content_drafts(data_referencia, tipo)")
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_drafts_status ON isis_content_drafts(status)")
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_drafts_job ON isis_content_drafts(job_id)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id INTEGER NOT NULL,
            variante TEXT NOT NULL,
            largura INTEGER,
            altura INTEGER,
            arquivo TEXT,
            mime_type TEXT,
            tamanho_bytes INTEGER,
            hash_sha256 TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (draft_id) REFERENCES isis_content_drafts(id)
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_assets_draft ON isis_content_assets(draft_id)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            descricao TEXT,
            url TEXT,
            confiavel INTEGER DEFAULT 0,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (draft_id) REFERENCES isis_content_drafts(id)
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_sources_draft ON isis_content_sources(draft_id)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_product_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            draft_id INTEGER,
            divulgado_em TEXT NOT NULL,
            motivo TEXT
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_prod_hist_produto ON isis_content_product_history(produto_id, divulgado_em)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id INTEGER NOT NULL,
            acao TEXT NOT NULL,
            usuario TEXT,
            detalhe TEXT,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (draft_id) REFERENCES isis_content_drafts(id)
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_approvals_draft ON isis_content_approvals(draft_id)")

    query_db(
        """
        CREATE TABLE IF NOT EXISTS isis_content_ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_referencia TEXT NOT NULL,
            provedor TEXT NOT NULL,
            tipo TEXT NOT NULL,
            custo_estimado REAL DEFAULT 0,
            unidades REAL DEFAULT 0,
            sucesso INTEGER DEFAULT 1,
            criado_em TEXT NOT NULL
        )
        """,
        commit=True,
    )
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_isis_content_ai_usage_data ON isis_content_ai_usage(data_referencia, provedor)")

    # Sinal explícito de visibilidade do produto para a Isis (distinto de
    # `ativo`, que já existe): produto pode estar ativo no catálogo mas
    # oculto de divulgações automáticas por decisão comercial.
    _exec_tolerante("ALTER TABLE produtos ADD COLUMN isis_oculto INTEGER DEFAULT 0")

    # Notificação administrativa de novos pedidos Pix + fluxo de comprovante
    # (ver backend/pedido_notificacao_routes.py). Nunca reutiliza
    # pedidos.status para "visualizado pelo admin" nem para "cliente clicou
    # no botão do WhatsApp": são sinais operacionais/de auditoria, não
    # financeiros — a confirmação de pagamento continua exclusivamente via
    # POST /api/pagamentos (backend/payment_routes.py), sem alteração.
    for col, typ in [
        ("visualizado_admin_em", "TEXT"),
        ("visualizado_admin_por", "TEXT"),
        ("comprovante_enviado_em", "TEXT"),
        # Marca a expiração automática (backend/order_status_routes.py::
        # expirar_pedidos_pendentes) sem criar um status novo: o pedido
        # continua indo para 'Cancelado' (comportamento já existente e
        # testado, preservado sem alteração), só que agora distinguível de
        # um cancelamento manual por este carimbo aditivo.
        ("expirado_em", "TEXT"),
        # Preparação para confirmação automática futura por provedor externo
        # (ex.: Mercado Pago — não integrado nesta mudança). 'manual_pix' é o
        # único provedor em uso hoje: confirmação sempre feita por um
        # administrador via POST /api/pagamentos.
        ("payment_provider", "TEXT NOT NULL DEFAULT 'manual_pix'"),
        ("provider_payment_id", "TEXT"),
    ]:
        _exec_tolerante(f"ALTER TABLE pedidos ADD COLUMN {col} {typ}")
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_pedidos_visualizado_admin ON pedidos(visualizado_admin_em)")

    # Idempotência de eventos de webhook de provedor de pagamento externo
    # (estrutura preparatória — nenhum provedor integrado nesta mudança; ver
    # backend/payment_webhook_routes.py). evento_id é o identificador do
    # evento no provedor (nunca o pix_txid/chave Pix); o par
    # (provedor, evento_id) é único para que um reenvio do mesmo webhook
    # (comum em integrações assíncronas) nunca seja processado duas vezes.
    query_db(
        """
        CREATE TABLE IF NOT EXISTS webhook_eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provedor TEXT NOT NULL,
            evento_id TEXT NOT NULL,
            tipo TEXT,
            payload_hash TEXT,
            recebido_em TEXT NOT NULL,
            processado_em TEXT,
            UNIQUE(provedor, evento_id)
        )
        """,
        commit=True,
    )


def _criar_tabelas_mercadopago():
    """Integração Mercado Pago (cartão de crédito) preservando o Pix manual
    já existente. Nenhuma tabela aqui é lida por nenhum caminho de código do
    Pix manual; `pedidos`/`pagamentos`/`webhook_eventos`/`idempotency_keys`
    continuam sendo a mesma fonte de verdade para os dois provedores (ver
    backend/payment_routes.py::registrar_pagamento, reaproveitado tanto pelo
    webhook Pix quanto pelo fluxo de cartão do Mercado Pago — nunca uma
    cópia paralela da conciliação/baixa de estoque).

    Índices em pedidos(pix_txid) e pedidos(provider_payment_id): essas
    colunas já existiam (pix_txid desde o PR do Pix manual, provider_payment_id
    como preparação para provedor externo) mas nunca tiveram índice dedicado
    — o lookup do webhook por provider_payment_id ficaria com scan completo
    da tabela à medida que o volume de pedidos cresce.
    """
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_pedidos_pix_txid ON pedidos(pix_txid)")
    _exec_tolerante("CREATE INDEX IF NOT EXISTS idx_pedidos_provider_payment_id ON pedidos(provider_payment_id)")

    # Tentativa de pagamento: um pedido pode ter várias (cartão recusado,
    # cliente tenta outro cartão), mas nunca mais de uma aprovada — essa
    # garantia não vem de uma constraint nesta tabela (ela só registra a
    # tentativa em si, inclusive as recusadas), e sim da transição atômica de
    # pedidos.status em backend/payment_routes.py::_tentar_transicao_status,
    # reaproveitada pelo fluxo de cartão. idempotency_key é única por
    # provedor: reenviar a mesma tentativa (retry de rede, clique duplo)
    # nunca cria uma segunda linha nem gera uma segunda cobrança no provedor.
    # provider_payment_id é único por provedor quando presente (preenchido
    # só depois que o provedor responde) para impedir duas tentativas locais
    # apontando para o mesmo pagamento externo por corrida/reprocessamento.
    query_db(
        """
        CREATE TABLE IF NOT EXISTS tentativas_pagamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            pagamento_id INTEGER,
            provedor TEXT NOT NULL,
            metodo TEXT NOT NULL,
            provider_payment_id TEXT,
            idempotency_key TEXT NOT NULL,
            status_interno TEXT NOT NULL DEFAULT 'processando',
            status_externo TEXT,
            valor REAL NOT NULL,
            parcelas INTEGER DEFAULT 1,
            bandeira TEXT,
            motivo_recusa TEXT,
            payload_sanitizado TEXT,
            evento_notificacao_id TEXT,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT,
            UNIQUE(provedor, idempotency_key)
        )
        """,
        commit=True,
    )
    for sql_idx in [
        "CREATE INDEX IF NOT EXISTS idx_tentativas_pagamento_pedido ON tentativas_pagamento(pedido_id)",
        "CREATE INDEX IF NOT EXISTS idx_tentativas_pagamento_status ON tentativas_pagamento(status_interno)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_tentativas_pagamento_provider_payment "
        "ON tentativas_pagamento(provedor, provider_payment_id) WHERE provider_payment_id IS NOT NULL",
    ]:
        _exec_tolerante(sql_idx)
