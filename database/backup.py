import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import BACKUP_DIR, DB_PATH, ERROR_LOG_PATH

_NOME_SEGURO_RE = re.compile(r"[^A-Za-z0-9_-]+")
_NOME_BACKUP_AUTOMATICO_RE = re.compile(r"^backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.db$")
_ESPACO_MINIMO_BYTES = 200 * 1024 * 1024
_LOCK_EXPIRA_SEGUNDOS = 6 * 60 * 60
_ESTADO_ARQUIVO = "backup.status.json"
_LOG_ARQUIVO = "backup.log"
_LOCK_ARQUIVO = ".backup.lock"
_HISTORICO_REMOTO_LIMITE = 50
_estado_lock = threading.RLock()


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


# ---------------------------------------------------------------------------
# Backup automatico da API em producao
# ---------------------------------------------------------------------------


def _config_int(nome, padrao, minimo, maximo):
    try:
        valor = int(str(os.environ.get(nome, padrao)).strip())
    except (TypeError, ValueError):
        return padrao
    return valor if minimo <= valor <= maximo else padrao


def backup_habilitado():
    return str(os.environ.get("BACKUP_ENABLED", "true")).strip().lower() in {"1", "true", "yes", "on", "sim"}


def _diretorio_backup_automatico():
    return Path(os.environ.get("BACKUP_DIRECTORY", "/data/backups")).expanduser()


def _db_path_automatico():
    return Path(os.environ.get("MISTICA_DB_PATH") or os.environ.get("DATABASE_PATH") or DB_PATH).expanduser()


def _quantidade_manter():
    return _config_int("BACKUP_KEEP", 30, 1, 10000)


def _agora_local():
    nome_fuso = str(os.environ.get("BACKUP_TIMEZONE", "America/Sao_Paulo")).strip()
    try:
        fuso = ZoneInfo(nome_fuso)
    except (ZoneInfoNotFoundError, ValueError):
        # Windows sem a base IANA e ambientes minimos continuam respeitando o
        # horario brasileiro atual, sem exigir o pacote externo tzdata.
        fuso = timezone(timedelta(hours=-3))
    return datetime.now(fuso)


def _arquivos_automaticos(diretorio):
    try:
        arquivos = [
            item
            for item in Path(diretorio).iterdir()
            if item.is_file() and _NOME_BACKUP_AUTOMATICO_RE.fullmatch(item.name)
        ]
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []
    return sorted(arquivos, key=lambda item: (item.stat().st_mtime, item.name), reverse=True)


def aplicar_retencao(diretorio=None, manter=None):
    """Mantem somente os backups automaticos mais recentes.

    A selecao estrita pelo nome impede que o banco principal, backups manuais,
    logs ou qualquer outro arquivo sejam removidos por esta rotina.
    """
    diretorio = Path(diretorio or _diretorio_backup_automatico())
    manter = _quantidade_manter() if manter is None else max(1, int(manter))
    removidos = []
    for arquivo in _arquivos_automaticos(diretorio)[manter:]:
        try:
            arquivo.unlink()
            removidos.append(arquivo.name)
        except FileNotFoundError:
            continue
    return removidos


def _caminho_existente_para_disco(caminho):
    candidato = Path(caminho).resolve()
    while not candidato.exists() and candidato != candidato.parent:
        candidato = candidato.parent
    return candidato


def _obter_espaco_livre_bytes(diretorio=None):
    diretorio = diretorio or _diretorio_backup_automatico()
    return shutil.disk_usage(_caminho_existente_para_disco(diretorio)).free


def _estado_path(diretorio):
    return Path(diretorio) / _ESTADO_ARQUIVO


def _ler_estado(diretorio):
    try:
        dados = json.loads(_estado_path(diretorio).read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _salvar_estado(diretorio, **alteracoes):
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    with _estado_lock:
        dados = _ler_estado(diretorio)
        registro_remoto = alteracoes.pop("_prepend_remote_upload", None)
        if isinstance(registro_remoto, dict):
            historico = dados.get("remote_uploads", [])
            if not isinstance(historico, list):
                historico = []
            dados["remote_uploads"] = ([registro_remoto] + historico)[:_HISTORICO_REMOTO_LIMITE]
        dados.update(alteracoes)
        temporario = diretorio / f".{_ESTADO_ARQUIVO}.{os.getpid()}.{threading.get_ident()}.tmp"
        temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporario, _estado_path(diretorio))
    return dados


def _registrar_log_automatico(diretorio, *, resultado, integridade, tamanho, tempo_gasto, erro=""):
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    erro_limpo = " ".join(str(erro or "").splitlines()) or "-"
    linha = (
        f"{_agora_local().isoformat(timespec='seconds')} | resultado={resultado} | "
        f"tamanho_bytes={int(tamanho or 0)} | tempo_segundos={tempo_gasto:.3f} | "
        f"integridade={integridade} | erro={erro_limpo}\n"
    )
    with _estado_lock:
        with (diretorio / _LOG_ARQUIVO).open("a", encoding="utf-8") as arquivo:
            arquivo.write(linha)


@contextmanager
def _lock_exclusivo(diretorio):
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    caminho = diretorio / _LOCK_ARQUIVO
    descritor = None
    adquirido = False
    for _ in range(2):
        try:
            descritor = os.open(str(caminho), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descritor, f"pid={os.getpid()} criado_em={_agora_local().isoformat()}".encode("utf-8"))
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


def _copiar_banco_sqlite(origem, temporario):
    """Cria snapshot consistente; VACUUM INTO e o fallback seguro oficial."""
    origem_conn = sqlite3.connect(str(origem), timeout=30)
    try:
        metodo_backup = getattr(origem_conn, "backup", None)
        if callable(metodo_backup):
            try:
                destino_conn = sqlite3.connect(str(temporario), timeout=30)
                try:
                    metodo_backup(destino_conn, pages=0, sleep=0.05)
                finally:
                    destino_conn.close()
            except (AttributeError, NotImplementedError):
                Path(temporario).unlink(missing_ok=True)
                literal = origem_conn.execute("SELECT quote(?)", (str(temporario),)).fetchone()[0]
                origem_conn.execute(f"VACUUM INTO {literal}")
        else:
            literal = origem_conn.execute("SELECT quote(?)", (str(temporario),)).fetchone()[0]
            origem_conn.execute(f"VACUUM INTO {literal}")
    finally:
        origem_conn.close()


def executar_backup(*, agendado=False):
    """Executa um backup de producao completo, idempotente e nao destrutivo.

    A funcao nunca substitui o banco principal nem um backup existente. O
    retorno e um dicionario adequado para logs/testes; falhas operacionais sao
    registradas e retornadas sem derrubar a aplicacao.
    """
    inicio = time.monotonic()
    diretorio = _diretorio_backup_automatico()
    origem = _db_path_automatico()
    diretorio.mkdir(parents=True, exist_ok=True)

    with _lock_exclusivo(diretorio) as adquirido:
        if not adquirido:
            duracao = time.monotonic() - inicio
            _registrar_log_automatico(
                diretorio,
                resultado="ignorado_lock_ativo",
                integridade="nao_executada",
                tamanho=0,
                tempo_gasto=duracao,
                erro="outro backup esta em execucao",
            )
            return {"status": "ignorado", "motivo": "backup_em_execucao"}

        agora = _agora_local()
        estado = _ler_estado(diretorio)
        data_agendada = agora.date().isoformat()
        if agendado and estado.get("ultima_data_agendada") == data_agendada:
            return {"status": "ignorado", "motivo": "ja_executado_hoje"}

        if agendado:
            _salvar_estado(diretorio, ultima_data_agendada=data_agendada)

        destino = diretorio / f"backup_{agora.strftime('%Y-%m-%d_%H-%M-%S')}.db"
        temporario = diretorio / f".{destino.name}.{uuid.uuid4().hex}.partial"
        try:
            if not origem.is_file():
                raise FileNotFoundError("banco principal nao encontrado")
            if origem.resolve() == destino.resolve():
                raise ValueError("destino do backup coincide com o banco principal")

            livre = _obter_espaco_livre_bytes(diretorio)
            if livre < _ESPACO_MINIMO_BYTES:
                _registrar_log_automatico(
                    diretorio,
                    resultado="aviso_espaco_baixo",
                    integridade="nao_executada",
                    tamanho=0,
                    tempo_gasto=time.monotonic() - inicio,
                    erro=f"espaco livre inferior a {_ESPACO_MINIMO_BYTES} bytes",
                )
                aplicar_retencao(diretorio)
                livre = _obter_espaco_livre_bytes(diretorio)
                if livre < _ESPACO_MINIMO_BYTES:
                    raise OSError("espaco livre insuficiente apos aplicar retencao")

            if destino.exists():
                valido, motivo = _validar_snapshot(str(destino), str(origem))
                if valido:
                    return {"status": "ignorado", "motivo": "backup_ja_existe", "nome": destino.name}
                destino.unlink(missing_ok=True)
                raise BackupInvalidoError(motivo or "backup existente invalido")

            _copiar_banco_sqlite(origem, temporario)
            valido, motivo = _validar_snapshot(str(temporario), str(origem))
            if not valido:
                raise BackupInvalidoError(motivo or "integrity_check falhou")
            os.replace(temporario, destino)
            tamanho = destino.stat().st_size
            removidos = aplicar_retencao(diretorio)
            duracao = time.monotonic() - inicio
            momento = _agora_local().isoformat(timespec="seconds")
            _salvar_estado(
                diretorio,
                ultimo_backup=destino.name,
                ultimo_tamanho_bytes=tamanho,
                ultimo_backup_em=momento,
                status="ok",
                integridade="ok",
                ultimo_erro=None,
                tempo_segundos=round(duracao, 3),
            )
            _registrar_log_automatico(
                diretorio,
                resultado="sucesso",
                integridade="ok",
                tamanho=tamanho,
                tempo_gasto=duracao,
            )
            # Segunda camada independente: somente arquivos ja validados,
            # publicados e registrados chegam ao uploader. A tarefa remota e
            # supervisionada fora deste fluxo, portanto rede, retries e falhas
            # nunca bloqueiam nem invalidam o backup local.
            try:
                from database.backup_remote import trigger_remote_sync

                trigger_remote_sync(
                    destino,
                    save_state=lambda **changes: _salvar_estado(diretorio, **changes),
                )
            except Exception as exc:
                # Ate uma falha ao registrar o erro remoto deve ser isolada:
                # neste ponto o backup local ja esta valido e publicado.
                try:
                    _salvar_estado(
                        diretorio,
                        remote_enabled=True,
                        remote_provider=str(os.environ.get("BACKUP_PROVIDER", "r2")).strip().lower() or "r2",
                        remote_status="erro",
                        last_remote_error=str(exc) or exc.__class__.__name__,
                    )
                except Exception:
                    pass
            return {
                "status": "ok",
                "nome": destino.name,
                "tamanho_bytes": tamanho,
                "integridade": "ok",
                "removidos": removidos,
            }
        except Exception as exc:
            temporario.unlink(missing_ok=True)
            # Somente o arquivo desta tentativa pode ser removido. Backups
            # anteriores e o banco principal jamais entram nesta limpeza.
            if destino.exists() and isinstance(exc, BackupInvalidoError):
                destino.unlink(missing_ok=True)
            duracao = time.monotonic() - inicio
            erro = str(exc) or exc.__class__.__name__
            _salvar_estado(
                diretorio,
                status="erro",
                integridade="falhou" if isinstance(exc, BackupInvalidoError) else "nao_executada",
                ultimo_erro=erro,
                tempo_segundos=round(duracao, 3),
            )
            _registrar_log_automatico(
                diretorio,
                resultado="erro",
                integridade="falhou" if isinstance(exc, BackupInvalidoError) else "nao_executada",
                tamanho=0,
                tempo_gasto=duracao,
                erro=erro,
            )
            return {"status": "erro", "erro": erro}


def calcular_proximo_backup(agora=None):
    agora = agora or _agora_local()
    hora = _config_int("BACKUP_HOUR", 3, 0, 23)
    minuto = _config_int("BACKUP_MINUTE", 0, 0, 59)
    proximo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if proximo <= agora:
        proximo += timedelta(days=1)
    return proximo


async def scheduler_backup():
    """Scheduler interno diario; o lock e o estado evitam duplicidade."""
    import asyncio

    while backup_habilitado():
        agora = _agora_local()
        proximo = calcular_proximo_backup(agora)
        await asyncio.sleep(max(0.0, (proximo - agora).total_seconds()))
        await asyncio.to_thread(executar_backup, agendado=True)


def obter_status_backup():
    diretorio = _diretorio_backup_automatico()
    arquivos = _arquivos_automaticos(diretorio)
    estado = _ler_estado(diretorio)
    ultimo = arquivos[0] if arquivos else None
    habilitado = backup_habilitado()
    remoto_habilitado = str(os.environ.get("BACKUP_REMOTE_ENABLED", "false")).strip().lower() in {
        "1", "true", "yes", "on", "sim"
    }
    return {
        "ultimo_backup": ultimo.name if ultimo else None,
        "tamanho_bytes": ultimo.stat().st_size if ultimo else None,
        "data": datetime.fromtimestamp(ultimo.stat().st_mtime, tz=_agora_local().tzinfo).isoformat(timespec="seconds") if ultimo else None,
        "quantidade_backups": len(arquivos),
        "espaco_livre_bytes": _obter_espaco_livre_bytes(diretorio),
        "proximo_backup": calcular_proximo_backup().isoformat(timespec="seconds") if habilitado else None,
        "status": estado.get("status", "aguardando" if habilitado else "desabilitado"),
        "ultimo_erro": estado.get("ultimo_erro"),
        "integridade": estado.get("integridade"),
        "remote_enabled": remoto_habilitado,
        "last_remote_backup": estado.get("last_remote_backup"),
        "remote_provider": estado.get("remote_provider") or (
            str(os.environ.get("BACKUP_PROVIDER", "r2")).strip().lower() if remoto_habilitado else None
        ),
        "remote_status": estado.get("remote_status", "aguardando") if remoto_habilitado else "desabilitado",
        "last_remote_error": estado.get("last_remote_error"),
        "last_remote_size": estado.get("last_remote_size"),
        "last_remote_hash": estado.get("last_remote_hash"),
    }


def obter_historico_backup_remoto():
    """Historico sanitizado; credenciais e caminhos nunca sao persistidos."""
    estado = _ler_estado(_diretorio_backup_automatico())
    uploads = estado.get("remote_uploads", [])
    return {"uploads": uploads if isinstance(uploads, list) else []}
