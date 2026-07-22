"""Testes de sobrevivência do banco SQLite (Fase 1 - PR 4).

Nunca usa o banco de produção: cada teste aponta `DB_PATH` para um arquivo
temporário isolado (tmp_path), simulando abertura, fechamento, reinício e
recuperação sem tocar em dados reais.
"""

import os
import sqlite3
import threading

import backend.database as backend_database
import config
import database.connection as connection
import database.migrations as migrations
from database.migrations import init_db


def _usar_banco_temporario(monkeypatch, tmp_path, nome="teste_persistencia.db"):
    caminho = str(tmp_path / nome)
    monkeypatch.setattr(connection, "DB_PATH", caminho)
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))
    return caminho


def test_banco_e_criado_automaticamente_ao_inicializar(monkeypatch, tmp_path):
    caminho = _usar_banco_temporario(monkeypatch, tmp_path)
    assert not (tmp_path / "teste_persistencia.db").exists()

    init_db()

    assert (tmp_path / "teste_persistencia.db").exists()
    tabelas = connection.query_db("SELECT name FROM sqlite_master WHERE type='table'")
    nomes = {row[0] for row in tabelas}
    assert "produtos" in nomes
    assert "usuarios" in nomes


def test_reinicializacao_e_idempotente(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-1", "Produto Teste", 10.0, 5),
        commit=True,
    )

    # Simula um segundo start (ex.: outro redeploy) rodando as migrações de novo.
    init_db()
    init_db()

    linhas = connection.query_db("SELECT nome FROM produtos WHERE codigo_p='COD-1'")
    assert len(linhas) == 1
    assert linhas[0][0] == "Produto Teste"


def test_conexao_fecha_e_libera_o_arquivo(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()

    conn = connection.get_connection()
    conn.execute("INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)", ("COD-2", "X", 1.0, 1))
    conn.commit()
    conn.close()

    # Uma nova conexão precisa conseguir abrir o mesmo arquivo sem lock pendente.
    conn2 = sqlite3.connect(connection.DB_PATH, timeout=5)
    total = conn2.execute("SELECT COUNT(*) FROM produtos WHERE codigo_p='COD-2'").fetchone()[0]
    conn2.close()
    assert total == 1


def test_dados_sobrevivem_a_reabertura_simulando_restart(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO clientes (nome, telefone) VALUES (?,?)",
        ("Cliente Persistente", "49999990000"),
        commit=True,
    )

    # "Restart": nenhum estado em memória do processo é reaproveitado, apenas
    # o caminho do arquivo -- uma nova conexão do zero, como após um reboot.
    init_db()
    linhas = connection.query_db("SELECT nome FROM clientes WHERE nome='Cliente Persistente'")
    assert len(linhas) == 1


def test_leitura_imediatamente_apos_escrita(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-3", "Produto Imediato", 20.0, 2),
        commit=True,
    )
    linha = connection.query_db("SELECT quantidade FROM produtos WHERE codigo_p='COD-3'")
    assert linha[0][0] == 2


def test_acesso_simultaneo_de_duas_conexoes_nao_corrompe_o_banco(monkeypatch, tmp_path):
    _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-CONC", "Produto Concorrente", 5.0, 100),
        commit=True,
    )

    erros = []

    def _baixar_estoque():
        try:
            conn = sqlite3.connect(connection.DB_PATH, timeout=10)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "UPDATE produtos SET quantidade = quantidade - 1 WHERE codigo_p='COD-CONC'"
            )
            conn.commit()
            conn.close()
        except Exception as exc:  # pragma: no cover - só have o teste falhar com detalhe
            erros.append(exc)

    threads = [threading.Thread(target=_baixar_estoque) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not erros
    linha = connection.query_db("SELECT quantidade FROM produtos WHERE codigo_p='COD-CONC'")
    assert linha[0][0] == 90


def test_banco_e_recriado_se_arquivo_for_removido_apos_um_restart(monkeypatch, tmp_path):
    caminho = _usar_banco_temporario(monkeypatch, tmp_path)
    init_db()
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-4", "Produto Antes", 1.0, 1),
        commit=True,
    )

    # Simula disco efêmero: o arquivo desaparece entre um restart e outro.
    import os

    os.remove(caminho)
    assert not (tmp_path / "teste_persistencia.db").exists()

    # A aplicação deve conseguir recriar o schema sem quebrar (mesmo que os
    # dados antigos não existam mais -- é exatamente o risco que este PR
    # documenta e monitora via /api/health e os logs de inicialização).
    init_db()
    assert (tmp_path / "teste_persistencia.db").exists()
    linhas = connection.query_db("SELECT * FROM produtos WHERE codigo_p='COD-4'")
    assert linhas == []


# ---------------------------------------------------------------------------
# Regressão do SIGBUS visto no CI do commit 46e020a: `_expirar_pedidos_
# periodicamente` (via `backend.database.conectar()`) não pode mais migrar
# nem abrir um caminho diferente do que efetivamente usa, mesmo que
# `database.connection.DB_PATH` esteja temporariamente monkeypatchado por um
# teste concorrente (ver relatório de investigação da falha em
# tests/test_persistencia_banco.py::test_banco_e_recriado_se_arquivo_for_removido_apos_um_restart).
# ---------------------------------------------------------------------------


def test_init_db_sem_argumento_continua_usando_o_global_de_connection(monkeypatch, tmp_path):
    """Retrocompatibilidade: nenhuma chamada existente passa `db_path` --
    `init_db()` sem argumento precisa continuar se comportando exatamente
    como antes, migrando `database.connection.DB_PATH`."""
    caminho = _usar_banco_temporario(monkeypatch, tmp_path)

    init_db()

    assert os.path.exists(caminho)
    tabelas = {row[0] for row in connection.query_db("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "produtos" in tabelas


def test_init_db_com_caminho_explicito_ignora_outro_valor_no_global(monkeypatch, tmp_path):
    """`init_db(caminho)` migra exatamente o caminho informado -- mesmo que
    `database.connection.DB_PATH` aponte, no momento da chamada, para um
    arquivo completamente diferente (simulando a tarefa de fundo chamada
    enquanto outro código monkeypatcha esse global)."""
    caminho_alvo = str(tmp_path / "alvo_explicito.db")
    caminho_outro = str(tmp_path / "outro_arquivo_nao_deve_ser_tocado.db")
    monkeypatch.setattr(connection, "DB_PATH", caminho_outro)
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))

    init_db(caminho_alvo)

    assert os.path.exists(caminho_alvo)
    assert not os.path.exists(caminho_outro)
    # `query_db` sem argumento de caminho continua lendo o global -- que
    # `init_db` deve ter restaurado ao valor original ao terminar.
    assert connection.DB_PATH == caminho_outro


def test_init_db_restaura_o_override_thread_local_mesmo_se_a_migracao_falhar(monkeypatch, tmp_path):
    """Se a migração de um caminho explícito explodir no meio, o override
    thread-local de `database.connection.usar_db_path` não pode ficar
    "vazado" -- uma chamada de `query_db` sem override, na mesma thread logo
    em seguida, precisa voltar a usar `database.connection.DB_PATH`
    normalmente (nunca o caminho que falhou)."""
    _usar_banco_temporario(monkeypatch, tmp_path, nome="original.db")
    init_db()

    caminho_que_falha = str(tmp_path / "outro_caminho_que_falha.db")
    original_aplicar = migrations._aplicar_migracoes

    def _aplicar_migracoes_com_falha(db_path_atual):
        if db_path_atual == caminho_que_falha:
            raise RuntimeError("falha simulada")
        return original_aplicar(db_path_atual)

    monkeypatch.setattr(migrations, "_aplicar_migracoes", _aplicar_migracoes_com_falha)

    with __import__("pytest").raises(RuntimeError):
        init_db(caminho_que_falha)

    assert not os.path.exists(caminho_que_falha)  # falhou antes de tocar o disco

    # O override thread-local não vazou: uma chamada normal de `query_db`
    # (sem passar por `init_db`) volta a usar `database.connection.DB_PATH`.
    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-POS-FALHA", "Prova de restauracao", 1.0, 1),
        commit=True,
    )
    linhas = connection.query_db("SELECT * FROM produtos WHERE codigo_p='COD-POS-FALHA'")
    assert len(linhas) == 1
    assert not os.path.exists(caminho_que_falha)


def test_conectar_usa_o_mesmo_caminho_para_migrar_e_para_abrir_a_conexao(monkeypatch, tmp_path):
    """`backend.database.conectar()` deve migrar e abrir exatamente o mesmo
    arquivo -- nunca migrar um caminho e conectar em outro."""
    caminho = str(tmp_path / "banco_real_do_backend.db")
    monkeypatch.setattr(config, "DB_PATH", caminho)
    monkeypatch.setattr(backend_database, "DB_PATH", caminho)

    # `backend_database.init_db` é um atributo de módulo compartilhado --
    # `conectar()` chamado por outras threads (débito técnico de
    # `TestClient`s nunca fechados, ativos durante a suíte completa) também
    # passaria por este espião, então filtra por thread para não misturar
    # o caminho delas com o desta chamada.
    thread_id_do_teste = threading.get_ident()
    caminhos_migrados = []
    original_init_db = migrations.init_db

    def _init_db_espiao(db_path=None):
        if threading.get_ident() == thread_id_do_teste:
            caminhos_migrados.append(db_path)
        return original_init_db(db_path)

    monkeypatch.setattr(backend_database, "init_db", _init_db_espiao)

    with backend_database.conectar() as conn:
        conn.execute("SELECT 1")

    assert caminhos_migrados == [caminho]
    assert os.path.exists(caminho)


def test_conectar_nao_e_afetado_por_monkeypatch_em_connection_db_path(monkeypatch, tmp_path):
    """Reproduz de forma determinística a condição de corrida do CI: um
    "teste" (aqui, simulado inline) monkeypatcha `database.connection.DB_PATH`
    para o seu próprio arquivo temporário -- igual a
    `tests/test_persistencia_banco.py::_usar_banco_temporario` faz -- e,
    enquanto esse monkeypatch está ativo, `backend.database.conectar()` (o
    caminho usado por `_expirar_pedidos_periodicamente`) é chamado. Antes da
    correção, `init_db()` (chamado por `conectar()` sem argumento) lia esse
    global e migrava/abria o arquivo do "teste" em vez do caminho real do
    backend. Depois da correção, `conectar()` passa seu próprio `DB_PATH`
    explicitamente, então o arquivo do "teste" nunca deve ser tocado."""
    caminho_backend = str(tmp_path / "banco_real_do_backend.db")
    monkeypatch.setattr(config, "DB_PATH", caminho_backend)
    monkeypatch.setattr(backend_database, "DB_PATH", caminho_backend)

    caminho_do_teste_concorrente = str(tmp_path / "arquivo_do_teste_concorrente.db")
    monkeypatch.setattr(connection, "DB_PATH", caminho_do_teste_concorrente)
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))

    with backend_database.conectar() as conn:
        conn.execute("SELECT 1")

    assert os.path.exists(caminho_backend)
    assert not os.path.exists(caminho_do_teste_concorrente)
    # `conectar()` restaura o global ao terminar -- outro código que leia
    # `database.connection.DB_PATH` sem argumento continua vendo o valor que
    # o "teste concorrente" monkeypatchou.
    assert connection.DB_PATH == caminho_do_teste_concorrente


def test_init_db_em_outra_thread_nao_contamina_query_db_direto_desta_thread(monkeypatch, tmp_path):
    """Reproduz o mecanismo exato de uma regressão descoberta durante o
    desenvolvimento desta correção: uma primeira versão fazia `init_db`
    reatribuir `database.connection.DB_PATH` diretamente (protegida por um
    lock) -- isso corrigia o SIGBUS original, mas quebrava
    `tests/test_venda_caixa.py::test_abrir_caixa_e_atomico_nao_duplica_caixa_aberto`
    na suíte completa: qualquer código em OUTRA thread que leia
    `query_db`/`get_connection` diretamente (sem passar por `init_db`), como
    `services/caixa_service.py`, podia ver transitoriamente o caminho da
    migração de outra thread enquanto o lock estava seguro (o lock só protege
    `init_db()` contra `init_db()`, nunca contra leituras diretas do global).

    Este teste prova que a versão final -- com override thread-local via
    `database.connection.usar_db_path` -- não sofre disso: enquanto uma
    thread de fundo está presa no meio de `init_db(caminho_fundo)`, uma
    chamada direta a `query_db` NESTA thread continua vendo
    `database.connection.DB_PATH` (o caminho desta thread), nunca
    `caminho_fundo`."""
    caminho_fundo = str(tmp_path / "tarefa_de_fundo.db")
    caminho_principal = _usar_banco_temporario(monkeypatch, tmp_path, nome="banco_desta_thread.db")
    init_db()

    entrou_na_migracao_de_fundo = threading.Event()
    pode_continuar_migracao_de_fundo = threading.Event()

    original_aplicar = migrations._aplicar_migracoes

    def _aplicar_migracoes_com_barreira(db_path_atual):
        if db_path_atual == caminho_fundo:
            entrou_na_migracao_de_fundo.set()
            pode_continuar_migracao_de_fundo.wait(timeout=5)
        return original_aplicar(db_path_atual)

    monkeypatch.setattr(migrations, "_aplicar_migracoes", _aplicar_migracoes_com_barreira)

    thread_fundo = threading.Thread(target=lambda: migrations.init_db(caminho_fundo))
    thread_fundo.start()
    try:
        assert entrou_na_migracao_de_fundo.wait(timeout=5)

        # Enquanto a thread de fundo está presa "dentro" da migração de
        # `caminho_fundo` (com o override thread-local dela ativo), uma
        # chamada direta de `query_db` NESTA thread -- exatamente como
        # `services/caixa_service.py` faz -- não pode ser afetada.
        connection.query_db(
            "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
            ("COD-ISOLADO", "Prova de isolamento", 9.0, 1),
            commit=True,
        )
        linhas = connection.query_db("SELECT * FROM produtos WHERE codigo_p='COD-ISOLADO'")
        assert len(linhas) == 1
    finally:
        pode_continuar_migracao_de_fundo.set()
        thread_fundo.join(timeout=5)

    # A linha gravada durante a corrida foi parar no banco correto desta
    # thread (`caminho_principal`), nunca no arquivo da tarefa de fundo.
    conn_fundo = sqlite3.connect(caminho_fundo)
    vazou_para_o_arquivo_da_thread_de_fundo = conn_fundo.execute(
        "SELECT COUNT(*) FROM produtos WHERE codigo_p='COD-ISOLADO'"
    ).fetchone()[0]
    conn_fundo.close()
    assert vazou_para_o_arquivo_da_thread_de_fundo == 0
    assert connection.DB_PATH == caminho_principal


def test_conectar_nao_bloqueia_esperando_init_db_concorrente_em_outra_thread(monkeypatch, tmp_path):
    """Sem lock global (só override thread-local), `backend.database.conectar()`
    chamado enquanto outra thread está presa no meio de uma migração
    (`init_db(caminho_fundo)`) não precisa esperar essa outra thread liberar --
    as duas migrações são independentes, não seriais."""
    caminho_fundo = str(tmp_path / "tarefa_de_fundo_2.db")
    caminho_principal = str(tmp_path / "conectar_principal.db")
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))
    monkeypatch.setattr(config, "DB_PATH", caminho_principal)
    monkeypatch.setattr(backend_database, "DB_PATH", caminho_principal)

    entrou_na_migracao_de_fundo = threading.Event()
    pode_continuar_migracao_de_fundo = threading.Event()

    original_aplicar = migrations._aplicar_migracoes

    def _aplicar_migracoes_com_barreira(db_path_atual):
        if db_path_atual == caminho_fundo:
            entrou_na_migracao_de_fundo.set()
            pode_continuar_migracao_de_fundo.wait(timeout=5)
        return original_aplicar(db_path_atual)

    monkeypatch.setattr(migrations, "_aplicar_migracoes", _aplicar_migracoes_com_barreira)

    thread_fundo = threading.Thread(target=lambda: migrations.init_db(caminho_fundo))
    thread_fundo.start()
    try:
        assert entrou_na_migracao_de_fundo.wait(timeout=5)

        # Não bloqueia: completa mesmo com a thread de fundo ainda travada.
        with backend_database.conectar() as conn:
            conn.execute("SELECT 1")
        assert os.path.exists(caminho_principal)
    finally:
        pode_continuar_migracao_de_fundo.set()
        thread_fundo.join(timeout=5)

    assert os.path.exists(caminho_fundo)
    for caminho in (caminho_principal, caminho_fundo):
        conn = sqlite3.connect(caminho)
        tabelas = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "produtos" in tabelas
        assert "usuarios" in tabelas


def test_bancos_migrados_normaliza_path_e_str_para_a_mesma_chave_de_cache(monkeypatch, tmp_path):
    """`_BANCOS_MIGRADOS` guarda strings normalizadas via `os.fspath` --
    chamar `init_db` com `str` e depois com `Path` equivalente para o mesmo
    arquivo não deve gerar duas entradas de cache nem forçar remigração
    desnecessária."""
    caminho_str = str(tmp_path / "cache_equivalente.db")
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))

    init_db(caminho_str)
    assert caminho_str in migrations._BANCOS_MIGRADOS

    from pathlib import Path

    # Se `_aplicar_migracoes` seguir além do `return` do cache hit, ela
    # chama `query_db` (via módulo `migrations`) para recriar o schema --
    # espionar essa chamada é o jeito confiável de provar "cache hit, não
    # reexecutou", já que a própria checagem de cache mora dentro de
    # `_aplicar_migracoes`. `query_db` é monkeypatchado no módulo inteiro
    # (compartilhado pelo processo), então o espião só conta chamadas feitas
    # por ESTA thread -- a suíte completa roda outras threads de fundo
    # (débito técnico de `TestClient`s nunca fechados, ver seção da PR) que
    # também chamam `query_db` de forma legítima para o caminho delas, e não
    # podem contaminar esta asserção.
    thread_id_do_teste = threading.get_ident()
    chamadas = []
    original_query_db = migrations.query_db

    def _query_db_espiao(*a, **k):
        if threading.get_ident() == thread_id_do_teste:
            chamadas.append((a, k))
        return original_query_db(*a, **k)

    monkeypatch.setattr(migrations, "query_db", _query_db_espiao)

    init_db(Path(caminho_str))

    assert chamadas == []  # cache hit: não reexecuta nenhuma instrução DDL
    # A chave de cache é sempre o `str` normalizado -- nunca um objeto
    # `Path` bruto, que geraria uma segunda entrada para o mesmo arquivo
    # físico e forçaria remigração indevida na próxima chamada com `str`.
    assert caminho_str in migrations._BANCOS_MIGRADOS
    assert Path(caminho_str) not in migrations._BANCOS_MIGRADOS


def test_bancos_migrados_invalida_cache_quando_arquivo_e_removido(monkeypatch, tmp_path):
    """Continua funcionando com caminho explícito: remover o arquivo do
    disco precisa invalidar o cache, mesmo quando o caminho foi passado por
    parâmetro em vez de vir do global."""
    caminho = str(tmp_path / "sera_removido.db")
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))

    init_db(caminho)
    assert caminho in migrations._BANCOS_MIGRADOS

    os.remove(caminho)

    # Mesmo cuidado da observação acima: filtra por thread para não contar
    # chamadas de tarefas de fundo concorrentes na suíte completa.
    thread_id_do_teste = threading.get_ident()
    chamadas = []
    original_aplicar = migrations._aplicar_migracoes

    def _aplicar_migracoes_espiao(p):
        if threading.get_ident() == thread_id_do_teste:
            chamadas.append(p)
        return original_aplicar(p)

    monkeypatch.setattr(migrations, "_aplicar_migracoes", _aplicar_migracoes_espiao)

    init_db(caminho)

    assert chamadas == [caminho]  # cache miss: remigrou de fato
    assert os.path.exists(caminho)
