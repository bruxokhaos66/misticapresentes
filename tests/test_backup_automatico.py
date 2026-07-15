import asyncio
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta

import database.backup as backup


NOME_BACKUP_RE = re.compile(r"^backup_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.db$")


def _criar_banco(caminho):
    conexao = sqlite3.connect(str(caminho))
    conexao.execute("PRAGMA journal_mode=WAL")
    conexao.execute("CREATE TABLE dados (id INTEGER PRIMARY KEY, valor TEXT)")
    conexao.execute("INSERT INTO dados (valor) VALUES ('mistica')")
    conexao.commit()
    return conexao


def _configurar(monkeypatch, tmp_path, *, manter=30):
    origem = tmp_path / "mistica_gestao_v20.db"
    diretorio = tmp_path / "backups"
    monkeypatch.setenv("MISTICA_DB_PATH", str(origem))
    monkeypatch.setenv("BACKUP_DIRECTORY", str(diretorio))
    monkeypatch.setenv("BACKUP_KEEP", str(manter))
    monkeypatch.setenv("BACKUP_ENABLED", "true")
    monkeypatch.setattr(backup, "_obter_espaco_livre_bytes", lambda diretorio=None: 1024**3)
    return origem, diretorio


def test_cria_pasta_backup_integro_e_restauravel_com_banco_aberto(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path)
    conexao_aberta = _criar_banco(origem)
    try:
        resultado = backup.executar_backup()
    finally:
        conexao_aberta.close()

    assert resultado["status"] == "ok"
    assert diretorio.is_dir()
    assert NOME_BACKUP_RE.fullmatch(resultado["nome"])
    arquivo = diretorio / resultado["nome"]

    restaurado = sqlite3.connect(str(arquivo))
    try:
        assert restaurado.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restaurado.execute("SELECT valor FROM dados").fetchall() == [("mistica",)]
    finally:
        restaurado.close()


def test_integridade_reprovada_remove_apenas_nova_tentativa(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path)
    _criar_banco(origem).close()
    diretorio.mkdir()
    anterior = diretorio / "backup_2026-07-13_03-00-00.db"
    anterior.write_bytes(b"backup anterior")
    monkeypatch.setattr(backup, "_validar_snapshot", lambda *args, **kwargs: (False, "corrompido"))

    resultado = backup.executar_backup()

    assert resultado["status"] == "erro"
    assert anterior.read_bytes() == b"backup anterior"
    assert backup._arquivos_automaticos(diretorio) == [anterior]
    assert not list(diretorio.glob("*.partial"))


def test_retencao_mantem_exatamente_os_30_mais_recentes_e_nunca_apaga_principal(tmp_path):
    diretorio = tmp_path / "backups"
    diretorio.mkdir()
    for indice in range(35):
        arquivo = diretorio / f"backup_2026-06-{indice + 1:02d}_03-00-00.db"
        arquivo.write_bytes(str(indice).encode())
        os.utime(arquivo, (1_000 + indice, 1_000 + indice))
    principal = diretorio / "mistica_gestao_v20.db"
    principal.write_bytes(b"principal")

    removidos = backup.aplicar_retencao(diretorio, manter=30)

    restantes = backup._arquivos_automaticos(diretorio)
    assert len(removidos) == 5
    assert len(restantes) == 30
    assert {item.read_bytes() for item in restantes} == {str(i).encode() for i in range(5, 35)}
    assert principal.read_bytes() == b"principal"


def test_execucao_concorrente_e_bloqueada(tmp_path, monkeypatch):
    origem, _ = _configurar(monkeypatch, tmp_path)
    _criar_banco(origem).close()
    iniciou = threading.Event()
    liberar = threading.Event()
    copiar_original = backup._copiar_banco_sqlite

    def copiar_lento(*args):
        iniciou.set()
        assert liberar.wait(timeout=5)
        copiar_original(*args)

    monkeypatch.setattr(backup, "_copiar_banco_sqlite", copiar_lento)
    resultados = []
    primeira = threading.Thread(target=lambda: resultados.append(backup.executar_backup()))
    primeira.start()
    assert iniciou.wait(timeout=5)

    segunda = backup.executar_backup()
    liberar.set()
    primeira.join(timeout=5)

    assert segunda == {"status": "ignorado", "motivo": "backup_em_execucao"}
    assert resultados[0]["status"] == "ok"


def test_espaco_baixo_aplica_retencao_e_aborta_com_log(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path, manter=2)
    _criar_banco(origem).close()
    diretorio.mkdir()
    for dia in range(1, 4):
        (diretorio / f"backup_2026-07-{dia:02d}_03-00-00.db").write_bytes(b"antigo")
    monkeypatch.setattr(backup, "_obter_espaco_livre_bytes", lambda diretorio=None: 100 * 1024 * 1024)

    resultado = backup.executar_backup()

    assert resultado["status"] == "erro"
    assert len(backup._arquivos_automaticos(diretorio)) == 2
    log = (diretorio / "backup.log").read_text(encoding="utf-8")
    assert "resultado=aviso_espaco_baixo" in log
    assert "resultado=erro" in log
    assert "espaco livre insuficiente" in log


def test_log_registra_data_tamanho_tempo_resultado_integridade_e_erros(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path)
    _criar_banco(origem).close()

    backup.executar_backup()

    linha = (diretorio / "backup.log").read_text(encoding="utf-8").strip()
    assert datetime.fromisoformat(linha.split(" | ", 1)[0])
    for campo in ("resultado=sucesso", "tamanho_bytes=", "tempo_segundos=", "integridade=ok", "erro=-"):
        assert campo in linha


def test_execucao_agendada_e_idempotente_no_mesmo_dia(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path)
    _criar_banco(origem).close()

    primeira = backup.executar_backup(agendado=True)
    segunda = backup.executar_backup(agendado=True)

    assert primeira["status"] == "ok"
    assert segunda == {"status": "ignorado", "motivo": "ja_executado_hoje"}
    assert len(backup._arquivos_automaticos(diretorio)) == 1


def test_scheduler_calcula_horario_e_dispara_uma_vez(monkeypatch):
    agora = datetime(2026, 7, 14, 2, 30).astimezone()
    monkeypatch.setenv("BACKUP_HOUR", "03")
    monkeypatch.setenv("BACKUP_MINUTE", "00")
    monkeypatch.setenv("BACKUP_ENABLED", "true")
    assert backup.calcular_proximo_backup(agora).hour == 3
    assert backup.calcular_proximo_backup(agora).date() == agora.date()

    chamadas = []

    async def sleep_imediato(segundos):
        assert segundos >= 0
        monkeypatch.setenv("BACKUP_ENABLED", "false")

    monkeypatch.setattr(asyncio, "sleep", sleep_imediato)
    monkeypatch.setattr(backup, "executar_backup", lambda **kwargs: chamadas.append(kwargs) or {"status": "ok"})
    asyncio.run(backup.scheduler_backup())

    assert chamadas == [{"agendado": True}]


def test_scheduler_usa_fuso_de_sao_paulo_sem_dependencia_externa(monkeypatch):
    monkeypatch.setenv("BACKUP_TIMEZONE", "America/Sao_Paulo")
    assert backup._agora_local().utcoffset() == timedelta(hours=-3)


def test_status_nao_expoe_caminhos_internos(tmp_path, monkeypatch):
    origem, diretorio = _configurar(monkeypatch, tmp_path)
    _criar_banco(origem).close()
    backup.executar_backup()

    status = backup.obter_status_backup()
    texto = str(status)
    assert status["quantidade_backups"] == 1
    assert status["status"] == "ok"
    assert status["integridade"] == "ok"
    assert str(tmp_path) not in texto
    assert str(origem) not in texto
