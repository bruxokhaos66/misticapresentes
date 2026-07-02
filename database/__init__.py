from config import BACKUP_DIR as _CONFIG_BACKUP_DIR
from config import DB_PATH as _CONFIG_DB_PATH

DB_PATH = _CONFIG_DB_PATH
BACKUP_DIR = _CONFIG_BACKUP_DIR


def _sincronizar_config():
    """Mantém compatibilidade com testes e serviços que alteram database.DB_PATH."""
    import config
    from . import backup, connection

    config.DB_PATH = DB_PATH
    config.BACKUP_DIR = BACKUP_DIR
    connection.DB_PATH = DB_PATH
    backup.DB_PATH = DB_PATH
    backup.BACKUP_DIR = BACKUP_DIR


def get_connection():
    _sincronizar_config()
    from .connection import get_connection as _get_connection

    return _get_connection()


def query_db(sql, params=(), commit=False):
    _sincronizar_config()
    from .connection import query_db as _query_db

    return _query_db(sql, params, commit)


def init_db():
    _sincronizar_config()
    from .migrations import init_db as _init_db

    return _init_db()


def realizar_backup(tag_extra=None):
    _sincronizar_config()
    from .backup import realizar_backup as _realizar_backup

    return _realizar_backup(tag_extra)


def limpar_backups_antigos():
    _sincronizar_config()
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
