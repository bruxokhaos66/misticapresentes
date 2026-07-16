"""Testes de regressão do procedimento de restore/disaster recovery.

Cobrem o fluxo completo exigido para produção: restore válido, backup
corrompido, checksum inválido, banco incompatível (tabelas essenciais
ausentes), rollback e o fato de que uma validação que falha nunca chega a
tocar no banco em uso.
"""

import sqlite3

import pytest

from database.restore import (
    RestoreError,
    listar_backups_disponiveis,
    reverter_ultimo_restore,
    restaurar_backup,
    validar_candidato_restore,
)


def _criar_banco_completo(caminho, marca="original"):
    conn = sqlite3.connect(str(caminho))
    try:
        for tabela in ("produtos", "clientes", "vendas", "vendas_itens", "usuarios"):
            conn.execute(f"CREATE TABLE {tabela} (id INTEGER PRIMARY KEY, marca TEXT)")
        conn.execute("INSERT INTO produtos (marca) VALUES (?)", (marca,))
        conn.commit()
    finally:
        conn.close()


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
    _criar_banco_completo(backup_path, marca="restaurado")

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
    assert resultado.motivo == "formato_invalido"
    assert _marca_produto(db_path) == "antigo"


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


def test_restore_com_banco_incompativel_tabelas_ausentes(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_incompleto.db"
    _criar_banco_completo(db_path, marca="antigo")

    conn = sqlite3.connect(str(backup_path))
    conn.execute("CREATE TABLE outra_coisa (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

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


def test_rollback_reverte_para_banco_anterior(tmp_path):
    db_path = tmp_path / "producao.db"
    backup_path = tmp_path / "backup_bom.db"
    _criar_banco_completo(db_path, marca="antigo")
    _criar_banco_completo(backup_path, marca="restaurado")

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
    _criar_banco_completo(backup_path, marca="de_outra_instalacao")

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
