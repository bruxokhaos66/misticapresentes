"""Testes de regressão do procedimento de restore/disaster recovery.

Cobrem o fluxo completo exigido para produção: restore válido, backup
corrompido, checksum ausente/inválido, banco incompatível (tabelas
essenciais ausentes), erro antes/depois da troca, restore com o banco em
uso por outra conexão, duas tentativas concorrentes, rollback e o fato de
que uma validação que falha nunca chega a tocar no banco em uso.
"""

import hashlib
import sqlite3
import threading

import pytest

from database.restore import (
    RestoreError,
    listar_backups_disponiveis,
    reverter_ultimo_restore,
    restaurar_backup,
    validar_candidato_restore,
)

TABELAS_ESSENCIAIS_TESTE = ("produtos", "clientes", "vendas", "vendas_itens", "usuarios", "pedidos")


def _criar_banco_completo(caminho, marca="original"):
    conn = sqlite3.connect(str(caminho))
    try:
        for tabela in TABELAS_ESSENCIAIS_TESTE:
            conn.execute(f"CREATE TABLE {tabela} (id INTEGER PRIMARY KEY, marca TEXT)")
        conn.execute("INSERT INTO produtos (marca) VALUES (?)", (marca,))
        conn.commit()
    finally:
        conn.close()


def _gravar_sidecar_checksum(caminho):
    """Simula o `.sha256` que `database/backup.py` sempre grava ao lado de um backup real."""
    digest = hashlib.sha256(caminho.read_bytes()).hexdigest()
    caminho.with_name(caminho.name + ".sha256").write_text(f"{digest}  {caminho.name}\n", encoding="utf-8")
    return digest


def _criar_backup_valido(caminho, marca="restaurado"):
    _criar_banco_completo(caminho, marca=marca)
    _gravar_sidecar_checksum(caminho)


def _marca_produto(caminho):
    conn = sqlite3.connect(str(caminho))
    try:
        return conn.execute("SELECT marca FROM produtos LIMIT 1").fetchone()[0]
    finally:
        conn.close()


def test_restore_valido_troca_banco_e_preserva_copia_anterior(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_path, marca="restaurado")

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "ok"
    assert _marca_produto(db_path) == "restaurado"
    assert resultado.copia_anterior is not None
    assert (db_path.parent / resultado.copia_anterior).exists()
    assert _marca_produto(db_path.parent / resultado.copia_anterior) == "antigo"


def test_restore_com_backup_corrompido_nao_altera_banco_atual(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_corrompido.db"
    _criar_banco_completo(db_path, marca="antigo")
    backup_path.write_bytes(b"nao e um sqlite valido")

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo in {"formato_invalido", "checksum_ausente"}
    assert _marca_produto(db_path) == "antigo"


def test_restore_com_checksum_ausente_falha_por_padrao(tmp_path):
    """Backup sem `.sha256` (nunca gerado por database/backup.py) é reprovado por
    padrão -- restaurar sem qualquer verificação de integridade não é o
    comportamento padrão, mesmo que o arquivo em si seja um SQLite válido."""
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_sem_checksum.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_banco_completo(backup_path, marca="restaurado")  # sem sidecar .sha256

    validacao = validar_candidato_restore(backup_path)
    assert not validacao.valido
    assert validacao.motivo == "checksum_ausente"

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")
    assert resultado.status == "erro"
    assert resultado.motivo == "checksum_ausente"
    assert _marca_produto(db_path) == "antigo"


def test_restore_com_checksum_ausente_permitido_explicitamente(tmp_path):
    """`exigir_checksum=False` é uma escolha explícita do chamador, não o padrão."""
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_sem_checksum.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_banco_completo(backup_path, marca="restaurado")

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste", exigir_checksum=False)

    assert resultado.status == "ok"
    assert _marca_produto(db_path) == "restaurado"


def test_restore_com_checksum_invalido_e_rejeitado(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_banco_completo(backup_path, marca="restaurado")

    resultado = restaurar_backup(
        backup_path, db_path=db_path, checksum_esperado="0" * 64, usuario="teste"
    )

    assert resultado.status == "erro"
    assert resultado.motivo == "checksum_invalido"
    assert _marca_produto(db_path) == "antigo"


def test_restore_com_checksum_correto_para_arquivo_incompativel(tmp_path):
    """O checksum bater não dispensa a validação de tabelas essenciais: um
    arquivo SQLite válido, com checksum correto para o que ele realmente é,
    ainda é reprovado se não tiver o schema esperado."""
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_incompativel.db"
    _criar_banco_completo(db_path, marca="antigo")

    conn = sqlite3.connect(str(backup_path))
    conn.execute("CREATE TABLE outra_coisa (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    checksum_real = _gravar_sidecar_checksum(backup_path)

    resultado = restaurar_backup(backup_path, db_path=db_path, checksum_esperado=checksum_real, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo == "tabelas_essenciais_ausentes"
    assert _marca_produto(db_path) == "antigo"


def test_restore_com_banco_incompativel_tabelas_ausentes(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_incompleto.db"
    _criar_banco_completo(db_path, marca="antigo")

    conn = sqlite3.connect(str(backup_path))
    conn.execute("CREATE TABLE outra_coisa (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    _gravar_sidecar_checksum(backup_path)

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo == "tabelas_essenciais_ausentes"
    assert _marca_produto(db_path) == "antigo"


def test_restore_falhou_integrity_check(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_ruim.db"
    _criar_banco_completo(db_path, marca="antigo")

    # Cabeçalho válido de SQLite, mas conteúdo interno inválido: passa na
    # checagem de assinatura de arquivo, mas nunca no integrity_check.
    with open(backup_path, "wb") as f:
        f.write(b"SQLite format 3\x00" + b"\x00" * 4096)
    _gravar_sidecar_checksum(backup_path)

    validacao = validar_candidato_restore(backup_path)
    assert not validacao.valido
    assert validacao.motivo in {"integrity_check_falhou", "banco_incompativel"}

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")
    assert resultado.status == "erro"
    assert _marca_produto(db_path) == "antigo"


def test_restore_de_arquivo_inexistente(tmp_path):
    db_path = tmp_path / "producao.db"
    _criar_banco_completo(db_path, marca="antigo")

    resultado = restaurar_backup(tmp_path / "nao_existe.db", db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo == "backup_nao_encontrado"
    assert _marca_produto(db_path) == "antigo"


def test_restore_com_erro_no_swap_preserva_banco_atual(tmp_path, monkeypatch):
    """Se `os.replace` falhar no momento da troca, o banco em uso deve permanecer
    intacto -- a cópia de segurança já foi feita antes, então nada se perde,
    e a falha de swap não deixa o sistema num estado pior do que estava."""
    import database.restore as restore_mod

    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_path, marca="restaurado")

    original_replace = restore_mod.os.replace

    def _replace_falho(origem, destino):
        # Só falha a troca do banco em si -- os.replace interno usado para
        # gravar o histórico de auditoria (arquivo diferente) continua
        # funcionando normalmente, como aconteceria numa falha real restrita
        # ao dispositivo/partição do banco.
        if str(destino) == str(db_path):
            raise OSError("falha simulada no swap")
        return original_replace(origem, destino)

    monkeypatch.setattr(restore_mod.os, "replace", _replace_falho)

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo == "falha_inesperada:OSError"
    assert _marca_produto(db_path) == "antigo"


def test_restore_nao_expoe_caminho_absoluto_em_erro(tmp_path, monkeypatch):
    """A mensagem de erro registrada em caso de falha nunca deve conter o
    caminho absoluto do backup/banco -- só a categoria da exceção."""
    import database.restore as restore_mod

    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_path, marca="restaurado")

    def _copy2_falho(origem, destino, *a, **k):
        raise OSError(f"[Errno 13] Permission denied: '{destino}'")

    monkeypatch.setattr(restore_mod.shutil, "copy2", _copy2_falho)

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert str(tmp_path) not in (resultado.motivo or "")
    assert "producao.db" not in (resultado.motivo or "")


def test_restore_com_banco_ativo_em_outra_conexao(tmp_path):
    """Uma conexão de leitura já aberta no banco atual não deve impedir nem
    corromper a troca atômica: a conexão antiga mantém seu próprio
    descritor de arquivo (semântica POSIX de os.replace), e a próxima
    conexão aberta após a troca já enxerga o banco restaurado."""
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_path, marca="restaurado")

    conexao_ativa = sqlite3.connect(str(db_path))
    conexao_ativa.execute("SELECT 1").fetchone()
    try:
        resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")
        assert resultado.status == "ok"
    finally:
        conexao_ativa.close()

    assert _marca_produto(db_path) == "restaurado"


def test_duas_tentativas_de_restore_concorrentes_apenas_uma_vence(tmp_path):
    """O lock exclusivo em disco impede que dois restores rodem ao mesmo
    tempo sobre o mesmo banco -- só um deve conseguir trocar o arquivo."""
    db_path = tmp_path / "producao.db"
    backup_a = tmp_path / "backup_a.db"
    backup_b = tmp_path / "backup_b.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_a, marca="veio_de_a")
    _criar_backup_valido(backup_b, marca="veio_de_b")

    resultados = []

    def _restaurar(caminho):
        resultados.append(restaurar_backup(caminho, db_path=db_path, usuario="concorrente"))

    t1 = threading.Thread(target=_restaurar, args=(backup_a,))
    t2 = threading.Thread(target=_restaurar, args=(backup_b,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    status = [r.status for r in resultados]
    assert status.count("ok") == 1
    assert status.count("erro") == 1
    erro = next(r for r in resultados if r.status == "erro")
    assert erro.motivo == "restore_ou_backup_em_execucao"
    assert _marca_produto(db_path) in {"veio_de_a", "veio_de_b"}


def test_rollback_reverte_para_banco_anterior(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_backup_valido(backup_path, marca="restaurado")

    resultado_restore = restaurar_backup(backup_path, db_path=db_path, usuario="teste")
    assert resultado_restore.status == "ok"
    assert _marca_produto(db_path) == "restaurado"

    resultado_rollback = reverter_ultimo_restore(db_path=db_path, usuario="teste")

    assert resultado_rollback.status == "ok"
    assert _marca_produto(db_path) == "antigo"


def test_rollback_sem_restore_anterior_retorna_erro(tmp_path):
    db_path = tmp_path / "producao.db"
    _criar_banco_completo(db_path, marca="antigo")

    resultado = reverter_ultimo_restore(db_path=db_path, usuario="teste")

    assert resultado.status == "erro"
    assert resultado.motivo == "nenhuma_copia_anterior_disponivel"
    assert _marca_produto(db_path) == "antigo"


def test_restore_em_outra_instalacao_caminho_db_diferente(tmp_path):
    """Simula restaurar um backup gerado numa instalação em outro `db_path`."""
    instalacao_origem = tmp_path / "origem"
    instalacao_origem.mkdir()
    backup_path = instalacao_origem / "backup.db"
    _criar_backup_valido(backup_path, marca="de_outra_instalacao")

    instalacao_destino = tmp_path / "destino"
    instalacao_destino.mkdir()
    db_path = instalacao_destino / "producao.db"
    _criar_banco_completo(db_path, marca="local")

    resultado = restaurar_backup(backup_path, db_path=db_path, usuario="teste")

    assert resultado.status == "ok"
    assert _marca_produto(db_path) == "de_outra_instalacao"


def test_listar_backups_disponiveis(tmp_path):
    diretorio = tmp_path / "backups"
    diretorio.mkdir()
    _criar_banco_completo(diretorio / "backup_1.db", marca="um")
    _criar_banco_completo(diretorio / "backup_2.db", marca="dois")

    listagem = listar_backups_disponiveis(diretorio)

    nomes = {item["nome"] for item in listagem}
    assert nomes == {"backup_1.db", "backup_2.db"}
