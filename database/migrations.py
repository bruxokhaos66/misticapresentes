import os
import secrets

from config import DOCS_PATH, hash_password_pbkdf2
from .connection import query_db


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
    query_db("CREATE TABLE IF NOT EXISTS site_musicas_ambiente (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL, content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, dados BLOB NOT NULL, criado_em TEXT NOT NULL)", commit=True)
    query_db("CREATE INDEX IF NOT EXISTS idx_site_musicas_ambiente_criado ON site_musicas_ambiente(criado_em)", commit=True)

    for col, typ in [("categoria", "TEXT"), ("data_atualizacao", "TEXT")]:
        try:
            query_db(f"ALTER TABLE isis_memoria ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_isis_logs_data ON isis_logs(data_hora)",
        "CREATE INDEX IF NOT EXISTS idx_pesquisas_online_data ON pesquisas_online_data",
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
    for tabela, col, typ in [("vendas", "status", "TEXT DEFAULT 'Concluído'"), ("vendas", "data_iso", "TEXT"), ("vendas", "dia_operacional", "TEXT"), ("fluxo_caixa", "data_iso", "TEXT"), ("fluxo_caixa", "forma_pagamento", "TEXT"), ("fluxo_caixa", "caixa_id", "INTEGER"), ("contas_a_pagar", "categoria", "TEXT DEFAULT 'Outros'")]:
        try:
            query_db(f"ALTER TABLE {tabela} ADD COLUMN {col} {typ}", commit=True)
        except Exception:
            pass

    for tabela, colunas in {"categorias": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "clientes": [("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "usuarios": [("cpf", "TEXT"), ("endereco", "TEXT"), ("telefone", "TEXT"), ("perfil", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT"), ("senha_salt", "TEXT")], "fornecedores": [("whatsapp", "TEXT"), ("cidade", "TEXT"), ("observacoes", "TEXT"), ("ativo", "INTEGER DEFAULT 1"), ("excluido_em", "TEXT")], "contas_a_pagar": [("categoria", "TEXT DEFAULT 'Outros'"), ("cancelado_em", "TEXT")], "vendas": [("status", "TEXT DEFAULT 'Concluído'"), ("data_iso", "TEXT"), ("dia_operacional", "TEXT")], "vendas_itens": [("custo_unitario", "REAL DEFAULT 0.0"), ("valor_unitario", "REAL DEFAULT 0.0"), ("valor_total", "REAL DEFAULT 0.0")], "fluxo_caixa": [("data_iso", "TEXT"), ("forma_pagamento", "TEXT"), ("caixa_id", "INTEGER")]}.items():
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

    for sql_idx in ["CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p)", "CREATE UNIQUE INDEX IF NOT EXISTS ux_produtos_codigo_unico ON produtos(codigo_p) WHERE codigo_p IS NOT NULL AND codigo_p != ''", "CREATE INDEX IF NOT EXISTS idx_mov_estoque_codigo ON movimentacao_estoque(codigo_p)", "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)", "CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)", "CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data_venda)", "CREATE INDEX IF NOT EXISTS idx_vendas_data_iso ON vendas(data_iso)", "CREATE INDEX IF NOT EXISTS idx_vendas_dia_operacional ON vendas(dia_operacional)", "CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status)", "CREATE INDEX IF NOT EXISTS idx_vendas_itens_venda ON vendas_itens(venda_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_id ON fluxo_caixa(caixa_id)", "CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_forma ON fluxo_caixa(forma_pagamento)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_tipo ON isis_memoria(tipo)", "CREATE INDEX IF NOT EXISTS idx_isis_memoria_chave ON isis_memoria(chave)", "CREATE INDEX IF NOT EXISTS idx_site_musicas_ambiente_criado ON site_musicas_ambiente(criado_em)"]:
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
