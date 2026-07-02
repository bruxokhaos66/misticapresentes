import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from config import BACKUP_DIR, DB_PATH, DOCS_PATH, hash_password_pbkdf2


SCHEMA_VERSION = 2


def get_connection():
    """Abre uma conexão SQLite segura para uso desktop/local."""
    pasta = os.path.dirname(DB_PATH)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def query_db(sql, params=(), commit=False):
    """Executa SQL parametrizado e retorna linhas quando não for commit."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        if commit:
            conn.commit()
            return cur.lastrowid
        return cur.fetchall()
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()


def _colunas(conn, tabela):
    try:
        return {linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
    except Exception:
        return set()


def _add_coluna(conn, tabela, coluna, definicao):
    if coluna not in _colunas(conn, tabela):
        conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def _criar_tabelas(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT,
            endereco TEXT,
            telefone TEXT,
            perfil TEXT NOT NULL DEFAULT 'operador',
            login TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            senha_salt TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT,
            excluido_em TEXT
        );

        CREATE TABLE IF NOT EXISTS login_tentativas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            sucesso INTEGER NOT NULL DEFAULT 0,
            ip TEXT,
            data_hora TEXT NOT NULL,
            bloqueado_ate TEXT
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            acao TEXT,
            detalhes TEXT,
            data_hora TEXT
        );

        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            ativo INTEGER NOT NULL DEFAULT 1,
            excluido_em TEXT
        );

        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_p TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            custo REAL NOT NULL DEFAULT 0,
            lucro REAL NOT NULL DEFAULT 0,
            preco REAL NOT NULL DEFAULT 0,
            quantidade INTEGER NOT NULL DEFAULT 0,
            estoque_minimo INTEGER NOT NULL DEFAULT 0,
            categoria TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            cpf TEXT,
            nascimento TEXT,
            observacao TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT,
            email TEXT,
            categoria TEXT,
            observacao TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT,
            data_venda TEXT,
            data_iso TEXT,
            subtotal REAL NOT NULL DEFAULT 0,
            desconto REAL NOT NULL DEFAULT 0,
            taxa REAL NOT NULL DEFAULT 0,
            total_final REAL NOT NULL DEFAULT 0,
            forma_pagamento TEXT,
            vendedor TEXT,
            status TEXT NOT NULL DEFAULT 'Concluído'
        );

        CREATE TABLE IF NOT EXISTS vendas_itens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            codigo_p TEXT,
            nome_p TEXT,
            quantidade INTEGER NOT NULL DEFAULT 0,
            custo_unitario REAL NOT NULL DEFAULT 0,
            valor_unitario REAL NOT NULL DEFAULT 0,
            valor_total REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(venda_id) REFERENCES vendas(id)
        );

        CREATE TABLE IF NOT EXISTS movimentacao_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_p TEXT,
            produto TEXT,
            quantidade INTEGER NOT NULL DEFAULT 0,
            tipo TEXT,
            motivo TEXT,
            usuario TEXT,
            data_hora TEXT,
            estoque_anterior INTEGER NOT NULL DEFAULT 0,
            estoque_posterior INTEGER NOT NULL DEFAULT 0,
            venda_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS inventario_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_p TEXT,
            produto TEXT,
            quantidade_sistema INTEGER NOT NULL DEFAULT 0,
            quantidade_contada INTEGER NOT NULL DEFAULT 0,
            diferenca INTEGER NOT NULL DEFAULT 0,
            usuario TEXT,
            data_hora TEXT,
            observacao TEXT
        );

        CREATE TABLE IF NOT EXISTS caixa_diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_abertura TEXT,
            saldo_inicial REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Aberto',
            operador TEXT,
            data_fechamento TEXT,
            saldo_final REAL,
            dinheiro_sistema REAL DEFAULT 0,
            pix_sistema REAL DEFAULT 0,
            debito_sistema REAL DEFAULT 0,
            credito_sistema REAL DEFAULT 0,
            dinheiro_informado REAL DEFAULT 0,
            pix_informado REAL DEFAULT 0,
            debito_informado REAL DEFAULT 0,
            credito_informado REAL DEFAULT 0,
            diferenca_caixa REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS fluxo_caixa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            descricao TEXT,
            valor REAL NOT NULL DEFAULT 0,
            data_hora TEXT,
            data_iso TEXT,
            caixa_id INTEGER,
            forma_pagamento TEXT,
            FOREIGN KEY(caixa_id) REFERENCES caixa_diario(id)
        );

        CREATE TABLE IF NOT EXISTS contas_a_pagar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            valor REAL NOT NULL DEFAULT 0,
            data_vencimento TEXT,
            categoria TEXT,
            status TEXT NOT NULL DEFAULT 'Pendente',
            cancelado_em TEXT
        );

        CREATE TABLE IF NOT EXISTS historico_precos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_p TEXT,
            produto TEXT,
            preco_antigo REAL,
            preco_novo REAL,
            custo_antigo REAL,
            custo_novo REAL,
            usuario TEXT,
            data_hora TEXT,
            motivo TEXT
        );

        CREATE TABLE IF NOT EXISTS isis_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT,
            modo TEXT,
            usuario TEXT,
            resposta TEXT,
            erro TEXT,
            data_hora TEXT
        );
        """
    )


def _migrar_colunas(conn):
    colunas = {
        "usuarios": {
            "cpf": "TEXT",
            "endereco": "TEXT",
            "telefone": "TEXT",
            "senha_salt": "TEXT",
            "ativo": "INTEGER NOT NULL DEFAULT 1",
            "criado_em": "TEXT",
            "excluido_em": "TEXT",
        },
        "produtos": {
            "ativo": "INTEGER NOT NULL DEFAULT 1",
            "estoque_minimo": "INTEGER NOT NULL DEFAULT 0",
            "criado_em": "TEXT",
        },
        "vendas": {
            "data_iso": "TEXT",
            "subtotal": "REAL NOT NULL DEFAULT 0",
            "desconto": "REAL NOT NULL DEFAULT 0",
            "taxa": "REAL NOT NULL DEFAULT 0",
            "status": "TEXT NOT NULL DEFAULT 'Concluído'",
        },
        "fluxo_caixa": {
            "data_iso": "TEXT",
            "caixa_id": "INTEGER",
            "forma_pagamento": "TEXT",
        },
        "contas_a_pagar": {
            "cancelado_em": "TEXT",
        },
        "caixa_diario": {
            "dinheiro_sistema": "REAL DEFAULT 0",
            "pix_sistema": "REAL DEFAULT 0",
            "debito_sistema": "REAL DEFAULT 0",
            "credito_sistema": "REAL DEFAULT 0",
            "dinheiro_informado": "REAL DEFAULT 0",
            "pix_informado": "REAL DEFAULT 0",
            "debito_informado": "REAL DEFAULT 0",
            "credito_informado": "REAL DEFAULT 0",
            "diferenca_caixa": "REAL DEFAULT 0",
        },
    }
    for tabela, defs in colunas.items():
        for coluna, definicao in defs.items():
            _add_coluna(conn, tabela, coluna, definicao)


def _criar_indices(conn):
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p);
        CREATE INDEX IF NOT EXISTS idx_produtos_ativo_nome ON produtos(ativo, nome);
        CREATE INDEX IF NOT EXISTS idx_vendas_data_iso ON vendas(data_iso);
        CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status);
        CREATE INDEX IF NOT EXISTS idx_vendas_itens_venda ON vendas_itens(venda_id);
        CREATE INDEX IF NOT EXISTS idx_fluxo_caixa_caixa ON fluxo_caixa(caixa_id);
        CREATE INDEX IF NOT EXISTS idx_contas_status ON contas_a_pagar(status);
        CREATE INDEX IF NOT EXISTS idx_login_tentativas_login ON login_tentativas(login, data_hora);
        """
    )


def _seed_inicial(conn):
    categorias = ["Incensos", "Velas", "Pedras", "Aromas", "Presentes", "Outros"]
    for nome in categorias:
        conn.execute("INSERT OR IGNORE INTO categorias (nome, ativo) VALUES (?, 1)", (nome,))

    existe_admin = conn.execute("SELECT 1 FROM usuarios WHERE login='admin' LIMIT 1").fetchone()
    if not existe_admin:
        import secrets

        senha = secrets.token_urlsafe(12)
        salt = secrets.token_hex(16)
        senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
        conn.execute(
            """
            INSERT INTO usuarios (nome, perfil, login, senha_hash, senha_salt, ativo, criado_em)
            VALUES (?,?,?,?,?,?,?)
            """,
            ("Administrador", "adm", "admin", senha_hash, salt, 1, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        try:
            caminho = os.path.join(DOCS_PATH, "mistica_senha_admin_inicial.txt")
            with open(caminho, "w", encoding="utf-8") as arq:
                arq.write("Usuário inicial: admin\n")
                arq.write(f"Senha temporária: {senha}\n")
                arq.write("Troque esta senha depois do primeiro acesso.\n")
        except Exception:
            pass


def init_db():
    """Cria/migra o banco local e garante as tabelas necessárias para inicialização limpa."""
    conn = get_connection()
    try:
        _criar_tabelas(conn)
        _migrar_colunas(conn)
        _criar_indices(conn)
        _seed_inicial(conn)
        conn.execute(f"PRAGMA user_version = {int(SCHEMA_VERSION)}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def realizar_backup(rotulo=None):
    """Cria backup simples do banco atual, quando existir.

    `rotulo` é opcional para manter compatibilidade com chamadas antigas da interface.
    """
    if not os.path.exists(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    sufixo = f"_{str(rotulo).strip()}" if rotulo else ""
    sufixo = "".join(ch for ch in sufixo if ch.isalnum() or ch in {"_", "-"})
    nome = f"mistica_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}{sufixo}.db"
    destino = os.path.join(BACKUP_DIR, nome)
    shutil.copy2(DB_PATH, destino)
    return destino


def limpar_backups_antigos(max_backups=20):
    """Mantém apenas os backups mais recentes."""
    if not os.path.isdir(BACKUP_DIR):
        return 0
    arquivos = sorted(
        Path(BACKUP_DIR).glob("mistica_backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removidos = 0
    for antigo in arquivos[int(max_backups):]:
        try:
            antigo.unlink()
            removidos += 1
        except Exception:
            pass
    return removidos
