import hashlib
import os
import re
import sqlite3
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from config import BACKUP_DIR, DB_PATH, ERROR_LOG_PATH

_NOME_SEGURO_RE = re.compile(r"[^A-Za-z0-9_-]+")


class BackupInvalidoError(Exception):
    """O snapshot foi criado mas não passou na validação de integridade."""


def _registrar_falha_backup(erro):
    try:
        os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " | Falha no backup automatico\n")
            f.write(str(erro) + "\n")
            f.write(traceback.format_exc())
    except Exception as exc_log:
        print(f"[Backup] Falha ao registrar log: {exc_log}")


def _sanitizar_componente(texto, default="backup"):
    limpo = _NOME_SEGURO_RE.sub("", str(texto or ""))
    return limpo or default


def _gerar_caminho_backup(destino_dir, prefixo, tag_extra, extensao):
    """Monta um nome de arquivo seguro (sem traversal) e sem colisão no destino."""
    prefixo = _sanitizar_componente(prefixo)
    extensao = _sanitizar_componente(extensao, default="db")
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    if tag_extra:
        tag = f"{tag}_{_sanitizar_componente(tag_extra)}"

    destino_dir_resolvido = Path(destino_dir).resolve()
    sufixo = ""
    contador = 0
    while True:
        nome = f"{prefixo}_{tag}{sufixo}.{extensao}"
        caminho = destino_dir_resolvido / nome
        if not caminho.exists():
            break
        contador += 1
        sufixo = f"_{contador}"

    if caminho.parent != destino_dir_resolvido:
        # Nunca deve acontecer com o sanitizador acima, mas garante em dobro
        # que o backup não pode escapar do diretório de destino.
        raise ValueError("Nome de backup inválido: fora do diretório de destino")

    return nome, str(caminho)


def _mesmo_arquivo(a, b):
    try:
        return os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b)
    except OSError:
        return False


def _validar_snapshot(caminho, origem_path=None):
    """Confere que o snapshot é um SQLite íntegro e independente da origem.

    Retorna (True, None) se válido, ou (False, motivo) caso contrário. Nunca
    apaga nem altera nada — quem chama decide o que fazer com o resultado.
    """
    if not os.path.exists(caminho):
        return False, "arquivo de backup não encontrado"
    if os.path.getsize(caminho) <= 0:
        return False, "arquivo de backup vazio"
    if origem_path and _mesmo_arquivo(caminho, origem_path):
        return False, "backup aponta para o mesmo arquivo da origem"

    try:
        conn = sqlite3.connect(caminho)
        try:
            linha = conn.execute("PRAGMA integrity_check").fetchone()
            if not linha or str(linha[0]).strip().lower() != "ok":
                return False, "PRAGMA integrity_check não retornou 'ok'"
            conn.execute("SELECT COUNT(*) FROM sqlite_master")
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, f"falha ao abrir/validar o backup: {exc}"

    return True, None


def _checksum_sha256(caminho):
    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _gravar_checksum(caminho, nome, checksum):
    try:
        with open(f"{caminho}.sha256", "w", encoding="utf-8") as f:
            f.write(f"{checksum}  {nome}\n")
    except OSError:
        pass


def criar_backup_seguro(origem_path, destino_dir, prefixo, tag_extra=None, extensao="db"):
    """Cria um snapshot consistente de um banco SQLite (mesmo em modo WAL).

    Usa `sqlite3.Connection.backup()` (API oficial do SQLite) em vez de copiar
    o arquivo diretamente, valida a integridade do snapshot resultante e
    calcula seu checksum SHA-256.

    Retorna um dict com `caminho`, `nome`, `tamanho_bytes` e `checksum_sha256`.
    Levanta `BackupInvalidoError` (ou a exceção original de I/O/SQLite) se o
    backup não puder ser criado ou validado — nesse caso, o próprio arquivo
    inválido recém-criado é removido, mas nenhum backup anterior é tocado.
    """
    os.makedirs(destino_dir, exist_ok=True)
    if not os.path.exists(origem_path):
        raise FileNotFoundError("Banco de origem não encontrado")

    nome, caminho = _gerar_caminho_backup(destino_dir, prefixo, tag_extra, extensao)

    if _mesmo_arquivo(origem_path, caminho) or os.path.abspath(origem_path) == os.path.abspath(caminho):
        raise ValueError("Destino do backup não pode ser o mesmo arquivo de origem")

    try:
        src = sqlite3.connect(origem_path)
        try:
            dst = sqlite3.connect(caminho)
            try:
                with dst:
                    src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        valido, motivo = _validar_snapshot(caminho, origem_path)
        if not valido:
            raise BackupInvalidoError(motivo or "backup inválido")

        checksum = _checksum_sha256(caminho)
    except Exception:
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass
        raise

    _gravar_checksum(caminho, nome, checksum)

    return {
        "caminho": caminho,
        "nome": nome,
        "tamanho_bytes": os.path.getsize(caminho),
        "checksum_sha256": checksum,
    }


def realizar_backup(tag_extra=None):
    try:
        info = criar_backup_seguro(DB_PATH, BACKUP_DIR, "mistica_auto", tag_extra=tag_extra)
        limpar_backups_antigos()
        return info["caminho"]
    except Exception as e:
        _registrar_falha_backup(e)
        return None


def limpar_backups_antigos():
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        limite = datetime.now() - timedelta(days=30)
        for arq in os.listdir(BACKUP_DIR):
            cam = os.path.join(BACKUP_DIR, arq)
            if os.path.isfile(cam) and arq.startswith("mistica_auto_"):
                if datetime.fromtimestamp(os.path.getmtime(cam)) < limite:
                    os.remove(cam)
    except Exception as e:
        _registrar_falha_backup(e)
