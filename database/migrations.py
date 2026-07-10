import os
import secrets

from config import DOCS_PATH, hash_password_pbkdf2
from .connection import query_db


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


def init_db():
    query_db("CREATE TABLE IF NOT EXISTS produtos (id INTEGER PRIMARY KEY, codigo_p TEXT, nome TEXT, preco REAL, quantidade INTEGER, categoria TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nome TEXT UNIQUE)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, cpf TEXT, endereco TEXT, nascimento TEXT)", commit=True)
    for col, typ in [("telefone", "TEXT"), ("cpf", "TEXT"), ("endereco", "TEXT"), ("nascimento", "TEXT")]:
        try:
            query_db(f"ALTER TABLE clientes ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    query_db("CREATE TABLE IF NOT EXISTS vendas (id INTEGER PRIMARY KEY, cliente TEXT, data_venda TEXT, subtotal REAL, desconto REAL, taxa REAL, total_final REAL, forma_pagamento TEXT, vendedor TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nome TEXT, cpf TEXT, endereco TEXT, telefone TEXT, login TEXT UNIQUE, senha_hash TEXT, perfil TEXT)", commit=True)
    try:
        query_db("ALTER TABLE usuarios ADD COLUMN senha_salt TEXT", commit=True)
    except Exception:
        pass

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
        try:
            query_db(f"ALTER TABLE clientes ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    try:
        query_db("UPDATE clientes SET telefone=COALESCE(NULLIF(telefone,''), telephone) WHERE telephone IS NOT NULL", commit=True)
    except Exception:
        pass
    try:
        query_db("ALTER TABLE usuarios ADD COLUMN telephone TEXT", commit=True)
    except Exception:
        pass
    try:
        query_db("UPDATE usuarios SET telefone=COALESCE(NULLIF(telefone,''), telephone) WHERE telephone IS NOT NULL", commit=True)
    except Exception:
        pass

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
        try:
            query_db(f"ALTER TABLE isis_memoria ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_isis_logs_data ON isis_logs(data_hora)",
        "CREATE INDEX IF NOT EXISTS idx_pesquisas_online_data ON pesquisas_online(data_hora)",
        "CREATE INDEX IF NOT EXISTS idx_encomendas_status ON encomendas(status)",
    ]:
        try:
            query_db(idx, commit=True)
        except Exception:
            pass

    query_db("CREATE TABLE IF NOT EXISTS historico_precos (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, preco_antigo REAL, preco_novo REAL, custo_antigo REAL, custo_novo REAL, usuario TEXT, data_hora TEXT, motivo TEXT)", commit=True)
    query_db("CREATE TABLE IF NOT EXISTS inventario_estoque (id INTEGER PRIMARY KEY, codigo_p TEXT, produto TEXT, quantidade_sistema INTEGER, quantidade_contada INTEGER, diferenca INTEGER, usuario TEXT, data_hora TEXT, observacao TEXT)", commit=True)

    for col, typ in [("ativo", "INTEGER DEFAULT 1")]:
        try:
            query_db(f"ALTER TABLE produtos ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    for col, typ in [("dinheiro_sistema", "REAL DEFAULT 0.0"), ("pix_sistema", "REAL DEFAULT 0.0"), ("debito_sistema", "REAL DEFAULT 0.0"), ("credito_sistema", "REAL DEFAULT 0.0"), ("dinheiro_informado", "REAL DEFAULT 0.0"), ("pix_informado", "REAL DEFAULT 0.0"), ("debito_informado", "REAL DEFAULT 0.0"), ("credito_informado", "REAL DEFAULT 0.0"), ("diferenca_caixa", "REAL DEFAULT 0.0")]:
        try:
            query_db(f"ALTER TABLE caixa_diario ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass

    for col, typ in [("custo", "REAL DEFAULT 0.0"), ("lucro", "REAL DEFAULT 0.0"), ("estoque_minimo", "INTEGER DEFAULT 0")]:
        try:
            query_db(f"ALTER TABLE produtos ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass

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
        try:
            query_db(f"ALTER TABLE produtos ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass

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
        try:
            query_db(f"ALTER TABLE vendas ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    try:
        query_db("CREATE INDEX IF NOT EXISTS idx_vendas_local_id ON vendas(local_id)", commit=True)
    except Exception:
        pass

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
        try:
            query_db(sql_idx, commit=True)
        except Exception:
            pass

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
        try:
            query_db(sql_idx, commit=True)
        except Exception:
            pass
    _migrar_pedidos_de_vendas()

    for tabela, col, typ in [("vendas", "status", "TEXT DEFAULT 'Concluído'"), ("vendas", "data_iso", "TEXT"), ("vendas", "dia_operacional", "TEXT"), ("fluxo_caixa", "data_iso", "TEXT"), ("fluxo_caixa", "forma_pagamento", "TEXT"), ("fluxo_caixa", "caixa_id", "INTEGER"), ("contas_a_pagar", "categoria", "TEXT DEFAULT 'Outros'")]:
        try:
            query_db(f"ALTER TABLE {tabela} ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass

    for tabela, colunas in {"categorias": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "clientes": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "usuarios": [("cpf", "TEXT"), ("endereco", "TEXT"), ("telefone", "TEXT"), ("perfil", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT"), ("senha_salt", "TEXT")], "fornecedores": [("whatsapp", "TEXT"), ("cidade", "TEXT"), ("observacoes", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "contas_a_pagar": [("categoria", "TEXT DEFAULT 'Outros'"), ("cancelado_em", "TEXT")], "vendas": [("status", "TEXT DEFAULT 'Concluído'"), ("data_iso", "TEXT"), ("dia_operacional", "TEXT")], "vendas_itens": [("custo_unitario", "REAL DEFAULT 0.0"), ("valor_unitario", "REAL DEFAULT 0.0"), ("valor_total", "REAL DEFAULT 0.0")], "fluxo_caixa": [("data_iso", "TEXT"), ("forma_pagamento", "TEXT"), ("caixa_id", "INTEGER")], "pedidos": [("telefone", "TEXT"), ("estoque_reservado", "INTEGER DEFAULT 0"), ("pix_txid", "TEXT"), ("pix_copia_cola", "TEXT"), ("confirmado_automaticamente", "INTEGER DEFAULT 0")]}.items():
        for col, typ in colunas:
            try:
                query_db(f"ALTER TABLE {tabela} ADD COLUMN {col} {typ}", commit=True)
            except Exception:
                pass

    try:
        query_db("UPDATE vendas SET status='Concluído' WHERE status IS NULL OR status=''", commit=True)
    except Exception:
        pass
    try:
        query_db("UPDATE vendas SET dia_operacional=substr(data_venda,1,10) WHERE COALESCE(dia_operacional,'')='' AND length(COALESCE(data_venda,'')) >= 10", commit=True)
    except Exception:
        pass

    for sql_idx in ["CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p)", "CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_codigo_unico ON produtos(codigo_p) WHERE codigo_p IS NOT NULL AND codigo_p != ''", "CREATE INDEX IF NOT EXISTS idx_mov_estoque_codigo ON movimentacao_estoque(codigo_p)", "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)", "CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)", "CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_venda)", "CREATE INDEX IF NOT EXISTS idx_vendas_data_iso ON vendas(data_iso)", "CREATE INDEX IF NOT EXISTS idx_vendas_dia_operacional ON vendas(dia_operacional)", "CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status)", "CREATE INDEX IF NOT EXISTS idx_vendas_itens_venda ON vendas_itens(venda_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_id ON fluxo_caixa(caixa_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_forma ON fluxo_caixa(forma_pagamento)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_tipo ON isis_memoria(tipo)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_chave ON isis_memoria(chave)"]:
        try:
            query_db(sql_idx, commit=True)
        except Exception:
            pass

    admin_res = query_db("SELECT senha_hash FROM usuarios WHERE login='admin'")
    if not admin_res:
        senha_temp = "Mistica@" + secrets.token_hex(4)
        salt = secrets.token_hex(16)
        query_db("INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)", ("Administrador", "admin", hash_password_pbkdf2(senha_temp, salt.encode("utf-8")), salt, "adm", 1), commit=True)
        try:
            with open(os.path.join(DOCS_PATH, "mistica_senha_admin_inicial.txt"), "w", encoding="utf-8") as f:
                f.write("Login: admin\nSenha temporaria: " + senha_temp + "\nTroque esta senha no primeiro acesso.\n")
        except Exception as exc:
            print(f"[DB init] Falha ao gravar senha admin temporaria: {exc}")
    for c in ["Velas", "Incensos", "Cristais", "Óleos"]:
        try:
            query_db("INSERT INTO categorias (nome) VALUES (?)", (c,), commit=True)
        except Exception:
            pass
