from config import BACKUP_DIR as _DEFAULT_BACKUP_DIR
from config import DB_PATH as _DEFAULT_DB_PATH

DB_PATH = _DEFAULT_DB_PATH
BACKUP_DIR = _DEFAULT_BACKUP_DIR


def _resolver_caminhos():
    """Resolve caminho ativo do banco sem sobrescrever monkeypatch de testes.

    Prioridade:
    1. database.DB_PATH, quando alterado diretamente;
    2. database.connection.DB_PATH, quando alterado por testes antigos;
    3. config.DB_PATH, quando alterado por testes/execução;
    4. caminho padrão carregado na importação.
    """
    import config
    from . import backup, connection

    global DB_PATH, BACKUP_DIR

    if DB_PATH != _DEFAULT_DB_PATH:
        ativo_db = DB_PATH
    elif getattr(connection, "DB_PATH", _DEFAULT_DB_PATH) != _DEFAULT_DB_PATH:
        ativo_db = connection.DB_PATH
    elif getattr(config, "DB_PATH", _DEFAULT_DB_PATH) != _DEFAULT_DB_PATH:
        ativo_db = config.DB_PATH
    else:
        ativo_db = DB_PATH

    if BACKUP_DIR != _DEFAULT_BACKUP_DIR:
        ativo_backup = BACKUP_DIR
    elif getattr(backup, "BACKUP_DIR", _DEFAULT_BACKUP_DIR) != _DEFAULT_BACKUP_DIR:
        ativo_backup = backup.BACKUP_DIR
    elif getattr(config, "BACKUP_DIR", _DEFAULT_BACKUP_DIR) != _DEFAULT_BACKUP_DIR:
        ativo_backup = config.BACKUP_DIR
    else:
        ativo_backup = BACKUP_DIR

    DB_PATH = ativo_db
    BACKUP_DIR = ativo_backup
    config.DB_PATH = ativo_db
    config.BACKUP_DIR = ativo_backup
    connection.DB_PATH = ativo_db
    backup.DB_PATH = ativo_db
    backup.BACKUP_DIR = ativo_backup


def get_connection():
    _resolver_caminhos()
    from .connection import get_connection as _get_connection

    return _get_connection()


def query_db(sql, params=(), commit=False):
    _resolver_caminhos()
    from .connection import query_db as _query_db

    return _query_db(sql, params, commit)


def init_db():
    _resolver_caminhos()
    from .migrations import init_db as _init_db

    return _init_db()


def realizar_backup(tag_extra=None):
    _resolver_caminhos()
    from .backup import realizar_backup as _realizar_backup

    return _realizar_backup(tag_extra)


def limpar_backups_antigos():
    _resolver_caminhos()
    from .backup import limpar_backups_antigos as _limpar_backups_antigos

    return _limpar_backups_antigos()


__all__ = [
    "DB_PATH",
    "BACKUP_DIR",
    "init_db",
    "limpar_backups_antigos",
    "get_connection",
    "query_db",
    "realizar_backup",
]
