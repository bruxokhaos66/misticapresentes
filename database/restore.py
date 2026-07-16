"""Procedimento seguro de restore/disaster recovery do banco SQLite.

Cobre o fluxo completo exigido para produção: seleção de um backup,
validação de checksum e formato, restauração em arquivo temporário,
PRAGMA integrity_check, validação das tabelas essenciais, troca atômica do
banco em uso, preservação de uma cópia do banco anterior e possibilidade de
rollback. Nada aqui restaura diretamente sobre o arquivo em uso: o
candidato é sempre validado por completo num arquivo à parte antes de
qualquer substituição, e a substituição em si preserva o banco anterior
para permitir reverter.

Uso típico (linha de comando, ver scripts/restaurar_backup.py):

    from database.restore import restaurar_backup, reverter_ultimo_restore

    resultado = restaurar_backup("/data/backups/backup_2026-07-15_03-00-00.db")
    ...
    reverter_ultimo_restore()  # desfaz, se necessário
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import BACKUP_DIR, DB_PATH, ERROR_LOG_PATH

_SQLITE_MAGIC = b"SQLite format 3\x00"
_LOCK_ARQUIVO = ".restore.lock"
_LOCK_EXPIRA_SEGUNDOS = 60 * 60
_HISTORICO_ARQUIVO = "restore.historico.json"
_HISTORICO_LIMITE = 50
_lock_estado = threading.RLock()

TABELAS_ESSENCIAIS = [
    "produtos",
    "clientes",
    "vendas",
    "vendas_itens",
    "usuarios",
    "pedidos",
]


class RestoreError(Exception):
    """Falha em qualquer etapa de validação/restauração; nada foi trocado."""


class RestoreValidationError(RestoreError):
    """O candidato a backup não passou numa das validações pré-troca."""


class RestoreRollbackError(RestoreError):
    """Não foi possível reverter para o banco anterior."""


@dataclass
class ResultadoValidacao:
    valido: bool
    motivo: Optional[str] = None
    tabelas_ausentes: list = field(default_factory=list)


@dataclass
class ResultadoRestore:
    status: str
    banco_restaurado: Optional[str] = None
    backup_origem: Optional[str] = None
    checksum_sha256: Optional[str] = None
    copia_anterior: Optional[str] = None
    motivo: Optional[str] = None
    data_hora: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


def _motivo_seguro(exc: Exception) -> str:
    """Categoria segura para logs/auditoria: nunca a mensagem crua da exceção.

    `str(exc)` de erros de sistema de arquivos (FileNotFoundError,
    PermissionError, OSError) costuma incluir o caminho absoluto envolvido
    -- exatamente o tipo de dado que a auditoria de restore não pode
    persistir. Só o nome da classe da exceção é gravado.
    """
    return exc.__class__.__name__


def _fsync_arquivo(caminho: Path) -> None:
    """Força os dados do arquivo para o disco antes de qualquer troca atômica
    depender dele -- sem isso, um `os.replace` bem-sucedido não garante que
    o conteúdo do arquivo temporário já esteja durável em caso de queda de
    energia logo após a troca."""
    fd = os.open(str(caminho), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_diretorio(diretorio: Path) -> None:
    """Força a entrada de diretório (o próprio rename) para o disco."""
    fd = os.open(str(diretorio), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _registrar_falha(mensagem: str) -> None:
    try:
        os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " | Falha em restore de banco\n")
            f.write(mensagem + "\n")
    except Exception:
        pass


@contextmanager
def _lock_exclusivo(diretorio: Path):
    """Impede backup e restore concorrentes sobre o mesmo diretório/banco."""
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = diretorio / _LOCK_ARQUIVO
    descritor = None
    adquirido = False
    for _ in range(2):
        try:
            descritor = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descritor, f"pid={os.getpid()} criado_em={datetime.now().isoformat()}".encode("utf-8"))
            os.fsync(descritor)
            adquirido = True
            break
        except FileExistsError:
            try:
                expirou = time.time() - caminho.stat().st_mtime > _LOCK_EXPIRA_SEGUNDOS
                if expirou:
                    caminho.unlink()
                    continue
            except FileNotFoundError:
                continue
            break
    try:
        yield adquirido
    finally:
        if descritor is not None:
            os.close(descritor)
        if adquirido:
            try:
                caminho.unlink()
            except FileNotFoundError:
                pass


def _checksum_sha256(caminho) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _gravar_checksum_sidecar(caminho: Path, checksum: str) -> None:
    try:
        Path(f"{caminho}.sha256").write_text(f"{checksum}  {caminho.name}\n", encoding="utf-8")
    except OSError:
        pass


def _ler_checksum_esperado(caminho_backup: Path) -> Optional[str]:
    """Lê o arquivo .sha256 irmão do backup (formato `<hash>  <nome>`), se existir."""
    caminho_hash = Path(str(caminho_backup) + ".sha256")
    if not caminho_hash.exists():
        return None
    try:
        conteudo = caminho_hash.read_text(encoding="utf-8").strip()
        return conteudo.split()[0] if conteudo else None
    except OSError:
        return None


def _historico_path(diretorio: Path) -> Path:
    return Path(diretorio) / _HISTORICO_ARQUIVO


def _registrar_historico(diretorio: Path, **entrada) -> None:
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    with _lock_estado:
        caminho = _historico_path(diretorio)
        try:
            historico = json.loads(caminho.read_text(encoding="utf-8"))
            if not isinstance(historico, list):
                historico = []
        except (OSError, ValueError):
            historico = []
        entrada.setdefault("data_hora", datetime.now().isoformat(timespec="seconds"))
        historico = ([entrada] + historico)[:_HISTORICO_LIMITE]
        temporario = diretorio / f".{_HISTORICO_ARQUIVO}.{os.getpid()}.tmp"
        temporario.write_text(json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, caminho)


def obter_historico_restore(diretorio=None) -> list:
    diretorio = Path(diretorio or BACKUP_DIR)
    try:
        historico = json.loads(_historico_path(diretorio).read_text(encoding="utf-8"))
        return historico if isinstance(historico, list) else []
    except (OSError, ValueError):
        return []


def listar_backups_disponiveis(diretorio=None) -> list[dict]:
    """Lista candidatos a restore no diretório de backups, mais recente primeiro."""
    diretorio = Path(diretorio or BACKUP_DIR)
    if not diretorio.exists():
        return []
    candidatos = []
    for item in diretorio.iterdir():
        if not item.is_file() or item.suffix != ".db":
            continue
        candidatos.append(
            {
                "nome": item.name,
                "tamanho_bytes": item.stat().st_size,
                "modificado_em": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                "checksum_disponivel": Path(str(item) + ".sha256").exists(),
            }
        )
    return sorted(candidatos, key=lambda c: c["modificado_em"], reverse=True)


def validar_candidato_restore(
    caminho_backup, checksum_esperado: Optional[str] = None, *, exigir_checksum: bool = True
) -> ResultadoValidacao:
    """Valida um backup candidato sem tocar no banco em uso.

    Confere, nesta ordem: existência do arquivo, checksum SHA-256 (contra o
    `.sha256` irmão ou o valor informado) -- calculado e comparado ANTES de
    abrir o arquivo como banco (a leitura da assinatura SQLite e o
    `sqlite3.connect` só acontecem depois) --, assinatura de arquivo SQLite,
    PRAGMA integrity_check e presença das tabelas essenciais.

    Por padrão (`exigir_checksum=True`) a ausência de um checksum -- nem
    `.sha256` irmão nem `checksum_esperado` informado -- já é motivo de
    reprovação: todo backup produzido por `database/backup.py` sempre grava
    um `.sha256`, então um candidato sem checksum é atípico (cópia manual,
    backup de outra origem) e não deve ser restaurado silenciosamente sem
    verificação. `exigir_checksum=False` existe só para cenários explícitos
    (ex.: testar um arquivo cuja origem já foi validada por outro meio).
    """
    caminho_backup = Path(caminho_backup)
    if not caminho_backup.exists() or not caminho_backup.is_file():
        return ResultadoValidacao(False, "arquivo_nao_encontrado")
    if caminho_backup.stat().st_size <= 0:
        return ResultadoValidacao(False, "arquivo_vazio")

    esperado = checksum_esperado or _ler_checksum_esperado(caminho_backup)
    if esperado:
        real = _checksum_sha256(caminho_backup)
        if real.lower() != str(esperado).lower():
            return ResultadoValidacao(False, "checksum_invalido")
    elif exigir_checksum:
        return ResultadoValidacao(False, "checksum_ausente")

    try:
        with open(caminho_backup, "rb") as f:
            cabecalho = f.read(len(_SQLITE_MAGIC))
    except OSError:
        return ResultadoValidacao(False, "falha_leitura")
    if cabecalho != _SQLITE_MAGIC:
        return ResultadoValidacao(False, "formato_invalido")

    try:
        conn = sqlite3.connect(f"file:{caminho_backup}?mode=ro", uri=True)
        try:
            linha = conn.execute("PRAGMA integrity_check").fetchone()
            if not linha or str(linha[0]).strip().lower() != "ok":
                return ResultadoValidacao(False, "integrity_check_falhou")

            tabelas_existentes = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            ausentes = [t for t in TABELAS_ESSENCIAIS if t not in tabelas_existentes]
            if ausentes:
                return ResultadoValidacao(False, "tabelas_essenciais_ausentes", tabelas_ausentes=ausentes)
        finally:
            conn.close()
    except sqlite3.Error:
        return ResultadoValidacao(False, "banco_incompativel")

    return ResultadoValidacao(True)


def restaurar_backup(
    caminho_backup,
    *,
    db_path=None,
    checksum_esperado: Optional[str] = None,
    exigir_checksum: bool = True,
    usuario: str = "sistema",
) -> ResultadoRestore:
    """Executa o procedimento completo de restore, com troca atômica e rollback disponível.

    Etapas: valida o candidato (checksum, formato, integridade, tabelas
    essenciais) copiando-o para um arquivo temporário isolado; só então
    preserva uma cópia do banco atual e faz a troca atômica (`os.replace`).
    Se qualquer validação falhar, o banco em uso nunca é tocado. Se a troca
    já ocorreu, `reverter_ultimo_restore()` restaura a cópia preservada.
    """
    db_path = Path(db_path or DB_PATH)
    diretorio_estado = db_path.parent
    caminho_backup = Path(caminho_backup)

    with _lock_exclusivo(diretorio_estado) as adquirido:
        if not adquirido:
            return ResultadoRestore(status="erro", motivo="restore_ou_backup_em_execucao")

        temporario = db_path.parent / f".{db_path.name}.restore_{uuid_hex()}.tmp"
        try:
            # 1) e 2)/3) seleção do backup e validação de checksum/formato/integridade
            # acontecem sempre sobre uma CÓPIA à parte -- nunca sobre o arquivo em
            # uso -- para que uma falha de validação jamais afete produção.
            if not caminho_backup.exists():
                return ResultadoRestore(status="erro", motivo="backup_nao_encontrado", backup_origem=str(caminho_backup.name))

            # O `.sha256` irmão (quando existe) fica ao lado do backup
            # ORIGINAL -- lido antes de copiar, porque o arquivo temporário
            # isolado não tem esse sidecar e não deve ganhar uma cópia dele
            # (evita confundir o checksum do candidato com o de qualquer
            # outro arquivo que por acaso caia no mesmo diretório de estado).
            checksum_do_sidecar = checksum_esperado or _ler_checksum_esperado(caminho_backup)

            shutil.copy2(caminho_backup, temporario)

            validacao = validar_candidato_restore(
                temporario, checksum_esperado=checksum_do_sidecar, exigir_checksum=exigir_checksum
            )
            if not validacao.valido:
                return ResultadoRestore(
                    status="erro",
                    motivo=validacao.motivo,
                    backup_origem=caminho_backup.name,
                )

            checksum = _checksum_sha256(temporario)

            # Sincroniza o conteúdo validado para o disco ANTES de qualquer
            # troca depender dele -- sem isso, um os.replace bem-sucedido não
            # garante que os dados já estejam duráveis se o processo/host
            # cair logo em seguida.
            _fsync_arquivo(temporario)

            # 8)/9) cópia do banco anterior antes de qualquer troca -- garante
            # rollback mesmo que o processo seja interrompido logo depois.
            copia_anterior = None
            if db_path.exists():
                copia_anterior = db_path.parent / f"{db_path.name}.antes_do_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(db_path, copia_anterior)
                _fsync_arquivo(copia_anterior)
                # Sem isso, o rollback não teria como verificar o checksum da
                # própria cópia preservada (nenhum backup externo grava esse
                # sidecar para ela) e falharia por "checksum_ausente".
                _gravar_checksum_sidecar(copia_anterior, _checksum_sha256(copia_anterior))

            # Troca atômica: os.replace substitui o alvo de uma vez (mesma
            # partição), nunca deixando o banco em um estado parcialmente
            # escrito visível para outro processo.
            os.replace(temporario, db_path)
            _fsync_diretorio(db_path.parent)

            # Arquivos de WAL/SHM da versão anterior não correspondem ao
            # conteúdo recém-trocado; remover para que a próxima conexão
            # comece um WAL limpo sobre o banco restaurado.
            for sufixo in ("-wal", "-shm"):
                candidato = Path(str(db_path) + sufixo)
                candidato.unlink(missing_ok=True)

            resultado = ResultadoRestore(
                status="ok",
                banco_restaurado=db_path.name,
                backup_origem=caminho_backup.name,
                checksum_sha256=checksum,
                copia_anterior=copia_anterior.name if copia_anterior else None,
            )
            _registrar_historico(
                diretorio_estado,
                acao="restore",
                status="ok",
                backup_origem=caminho_backup.name,
                checksum_sha256=checksum,
                copia_anterior=resultado.copia_anterior,
                usuario=usuario,
            )
            return resultado
        except Exception as exc:
            motivo_seguro = _motivo_seguro(exc)
            _registrar_falha(f"usuario={usuario} backup={caminho_backup.name} erro={motivo_seguro}")
            try:
                _registrar_historico(
                    diretorio_estado,
                    acao="restore",
                    status="erro",
                    backup_origem=caminho_backup.name,
                    motivo=motivo_seguro,
                    usuario=usuario,
                )
            except Exception:
                # Uma falha secundária ao registrar o histórico (ex.: mesmo
                # disco cheio/somente leitura que causou a falha original)
                # nunca pode mascarar o erro real do restore.
                pass
            return ResultadoRestore(status="erro", motivo=f"falha_inesperada:{motivo_seguro}", backup_origem=caminho_backup.name)
        finally:
            temporario.unlink(missing_ok=True)


def reverter_ultimo_restore(db_path=None, *, copia_anterior: Optional[str] = None, usuario: str = "sistema") -> ResultadoRestore:
    """Desfaz o último restore, devolvendo a cópia do banco preservada antes da troca.

    Se `copia_anterior` não for informado, usa a entrada mais recente do
    histórico de restores bem-sucedidos que ainda tenha uma cópia no disco.
    """
    db_path = Path(db_path or DB_PATH)
    diretorio_estado = db_path.parent

    nome_copia = copia_anterior
    if not nome_copia:
        for entrada in obter_historico_restore(diretorio_estado):
            if entrada.get("acao") == "restore" and entrada.get("status") == "ok" and entrada.get("copia_anterior"):
                nome_copia = entrada["copia_anterior"]
                break

    if not nome_copia:
        return ResultadoRestore(status="erro", motivo="nenhuma_copia_anterior_disponivel")

    caminho_copia = diretorio_estado / nome_copia
    if not caminho_copia.exists():
        return ResultadoRestore(status="erro", motivo="copia_anterior_nao_encontrada")

    validacao = validar_candidato_restore(caminho_copia)
    if not validacao.valido:
        return ResultadoRestore(status="erro", motivo=f"copia_anterior_invalida:{validacao.motivo}")

    with _lock_exclusivo(diretorio_estado) as adquirido:
        if not adquirido:
            return ResultadoRestore(status="erro", motivo="restore_ou_backup_em_execucao")
        try:
            temporario = diretorio_estado / f".{db_path.name}.rollback_{uuid_hex()}.tmp"
            shutil.copy2(caminho_copia, temporario)
            _fsync_arquivo(temporario)
            os.replace(temporario, db_path)
            _fsync_diretorio(diretorio_estado)
            for sufixo in ("-wal", "-shm"):
                Path(str(db_path) + sufixo).unlink(missing_ok=True)

            resultado = ResultadoRestore(status="ok", banco_restaurado=db_path.name, backup_origem=nome_copia)
            _registrar_historico(
                diretorio_estado,
                acao="rollback",
                status="ok",
                copia_anterior=nome_copia,
                usuario=usuario,
            )
            return resultado
        except Exception as exc:
            motivo_seguro = _motivo_seguro(exc)
            _registrar_falha(f"rollback usuario={usuario} copia={nome_copia} erro={motivo_seguro}")
            return ResultadoRestore(status="erro", motivo=f"falha_inesperada:{motivo_seguro}")


def uuid_hex() -> str:
    import uuid

    return uuid.uuid4().hex
