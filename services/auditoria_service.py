"""Auditoria semanal segura da Isis.

A auditoria pode corrigir automaticamente apenas pontos seguros:
- estrutura do banco via init_db;
- indices e colunas esperadas;
- normalizacao simples de status vazios;
- checagens de integridade SQLite;
- geracao de relatorio local.

Ela nao altera codigo-fonte automaticamente. Quando encontra problema de codigo,
registra no relatorio para revisao do operador/Codex.
"""
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import py_compile

from config import DOCS_PATH
from database import init_db, query_db, realizar_backup

AUDITORIA_STATE_PATH = Path(DOCS_PATH) / "mistica_auditoria_semanal.json"
AUDITORIA_REPORT_DIR = Path(DOCS_PATH) / "Mistica_Auditorias"
INTERVALO_DIAS = 7

ARQUIVOS_PRINCIPAIS = [
    "app.py",
    "mistica_presentes.py",
    "config.py",
    "database/__init__.py",
    "database/connection.py",
    "database/migrations.py",
    "services/venda_service.py",
    "services/produto_service.py",
    "services/estoque_service.py",
    "services/caixa_service.py",
    "services/isis_service.py",
    "isis/assistant.py",
    "isis/voice.py",
]

TABELAS_OBRIGATORIAS = [
    "produtos", "categorias", "clientes", "vendas", "vendas_itens", "usuarios",
    "logs", "fornecedores", "contas_a_pagar", "fluxo_caixa", "caixa_diario",
    "movimentacao_estoque", "isis_memoria", "isis_logs", "pesquisas_online",
]


def _agora_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def carregar_estado_auditoria():
    try:
        if AUDITORIA_STATE_PATH.exists():
            return json.loads(AUDITORIA_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def salvar_estado_auditoria(estado):
    try:
        AUDITORIA_STATE_PATH.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def deve_executar_auditoria_semanal():
    estado = carregar_estado_auditoria()
    ultima = estado.get("ultima_execucao")
    if not ultima:
        return True
    try:
        dt = datetime.strptime(ultima, "%Y-%m-%d %H:%M:%S")
        return datetime.now() - dt >= timedelta(days=INTERVALO_DIAS)
    except Exception:
        return True


def registrar_execucao_auditoria(relatorio):
    estado = carregar_estado_auditoria()
    estado["ultima_execucao"] = _agora_iso()
    estado["ultimo_status"] = relatorio.get("status", "desconhecido")
    estado["ultimo_relatorio"] = relatorio.get("arquivo_relatorio", "")
    estado["problemas"] = len(relatorio.get("problemas", []))
    estado["correcoes"] = len(relatorio.get("correcoes", []))
    salvar_estado_auditoria(estado)


def _adicionar(lista, texto):
    if texto not in lista:
        lista.append(texto)


def verificar_integridade_banco(problemas, avisos):
    try:
        res = query_db("PRAGMA integrity_check")
        valor = str(res[0][0]) if res else "sem retorno"
        if valor.lower() != "ok":
            _adicionar(problemas, "SQLite integrity_check retornou: " + valor)
        else:
            _adicionar(avisos, "Banco SQLite passou no integrity_check.")
    except Exception as e:
        _adicionar(problemas, "Falha ao executar integrity_check: " + str(e))


def verificar_tabelas(problemas, avisos):
    try:
        existentes = {r[0] for r in query_db("SELECT name FROM sqlite_master WHERE type='table'")}
        faltando = [t for t in TABELAS_OBRIGATORIAS if t not in existentes]
        if faltando:
            _adicionar(problemas, "Tabelas ausentes: " + ", ".join(faltando))
        else:
            _adicionar(avisos, "Todas as tabelas obrigatorias existem.")
    except Exception as e:
        _adicionar(problemas, "Falha ao verificar tabelas: " + str(e))


def verificar_dados_basicos(problemas, avisos):
    checagens = [
        ("Produtos sem codigo ou nome", "SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND (codigo_p IS NULL OR codigo_p='' OR nome IS NULL OR nome='')"),
        ("Vendas sem status", "SELECT COUNT(*) FROM vendas WHERE status IS NULL OR status=''"),
        ("Caixas abertos simultaneos", "SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'"),
        ("Fluxos sem caixa_id", "SELECT COUNT(*) FROM fluxo_caixa WHERE caixa_id IS NULL"),
    ]
    for nome, sql in checagens:
        try:
            total = int(query_db(sql)[0][0] or 0)
            if nome == "Caixas abertos simultaneos" and total > 1:
                _adicionar(problemas, f"{nome}: {total}")
            elif nome != "Caixas abertos simultaneos" and total > 0:
                _adicionar(avisos, f"{nome}: {total}")
        except Exception as e:
            _adicionar(problemas, f"Falha na checagem '{nome}': {e}")


def aplicar_correcoes_seguras(correcoes, problemas):
    try:
        realizar_backup()
        _adicionar(correcoes, "Backup criado antes da auditoria.")
    except Exception as e:
        _adicionar(problemas, "Nao consegui criar backup antes da auditoria: " + str(e))

    try:
        init_db()
        _adicionar(correcoes, "Estrutura do banco, colunas e indices conferidos pelo init_db().")
    except Exception as e:
        _adicionar(problemas, "Falha ao rodar init_db(): " + str(e))

    correcoes_sql = [
        ("Normalizar status vazio de vendas", "UPDATE vendas SET status='Concluído' WHERE status IS NULL OR status=''"),
        ("Normalizar produtos ativos", "UPDATE produtos SET ativo=1 WHERE ativo IS NULL"),
        ("Normalizar categorias ativas", "UPDATE categorias SET ativo=1 WHERE ativo IS NULL"),
        ("Normalizar clientes ativos", "UPDATE clientes SET ativo=1 WHERE ativo IS NULL"),
    ]
    for nome, sql in correcoes_sql:
        try:
            query_db(sql, commit=True)
            _adicionar(correcoes, nome)
        except Exception as e:
            _adicionar(problemas, f"Falha em correcao segura '{nome}': {e}")


def verificar_arquivos_codigo(problemas, avisos):
    raiz = Path(__file__).resolve().parents[1]
    for rel in ARQUIVOS_PRINCIPAIS:
        caminho = raiz / rel
        if not caminho.exists():
            _adicionar(problemas, "Arquivo principal ausente: " + rel)
            continue
        try:
            py_compile.compile(str(caminho), doraise=True)
        except Exception as e:
            _adicionar(problemas, f"Erro de sintaxe/compilacao em {rel}: {e}")
    _adicionar(avisos, "Arquivos principais conferidos quanto a existencia e compilacao.")


def salvar_relatorio(relatorio):
    try:
        AUDITORIA_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        nome = "auditoria_isis_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
        caminho = AUDITORIA_REPORT_DIR / nome
        caminho.write_text(formatar_relatorio_auditoria(relatorio), encoding="utf-8")
        relatorio["arquivo_relatorio"] = str(caminho)
    except Exception as e:
        relatorio.setdefault("problemas", []).append("Falha ao salvar relatorio: " + str(e))


def executar_auditoria_sistema(corrigir=True, origem="manual"):
    relatorio = {
        "data_hora": _agora_iso(),
        "origem": origem,
        "status": "ok",
        "problemas": [],
        "avisos": [],
        "correcoes": [],
        "arquivo_relatorio": "",
    }

    if corrigir:
        aplicar_correcoes_seguras(relatorio["correcoes"], relatorio["problemas"])

    verificar_integridade_banco(relatorio["problemas"], relatorio["avisos"])
    verificar_tabelas(relatorio["problemas"], relatorio["avisos"])
    verificar_dados_basicos(relatorio["problemas"], relatorio["avisos"])
    verificar_arquivos_codigo(relatorio["problemas"], relatorio["avisos"])

    if relatorio["problemas"]:
        relatorio["status"] = "atencao"
    salvar_relatorio(relatorio)
    registrar_execucao_auditoria(relatorio)
    return relatorio


def formatar_relatorio_auditoria(relatorio):
    linhas = []
    linhas.append("RELATORIO DE AUDITORIA DA ISIS")
    linhas.append("Data/Hora: " + str(relatorio.get("data_hora", "")))
    linhas.append("Origem: " + str(relatorio.get("origem", "")))
    linhas.append("Status: " + str(relatorio.get("status", "")))
    linhas.append("")

    linhas.append("CORRECOES SEGURAS APLICADAS:")
    correcoes = relatorio.get("correcoes", [])
    linhas.extend(["- " + c for c in correcoes] if correcoes else ["- Nenhuma correcao automatica necessaria."])
    linhas.append("")

    linhas.append("PROBLEMAS ENCONTRADOS:")
    problemas = relatorio.get("problemas", [])
    linhas.extend(["- " + p for p in problemas] if problemas else ["- Nenhum problema critico encontrado."])
    linhas.append("")

    linhas.append("AVISOS E OBSERVACOES:")
    avisos = relatorio.get("avisos", [])
    linhas.extend(["- " + a for a in avisos] if avisos else ["- Sem avisos."])
    linhas.append("")

    if relatorio.get("arquivo_relatorio"):
        linhas.append("Arquivo do relatorio: " + relatorio["arquivo_relatorio"])
    return "\n".join(linhas)


def resumo_curto_auditoria(relatorio):
    status = relatorio.get("status", "ok")
    qtd_prob = len(relatorio.get("problemas", []))
    qtd_corr = len(relatorio.get("correcoes", []))
    arquivo = relatorio.get("arquivo_relatorio", "")
    if qtd_prob:
        return f"Auditoria concluida com atencao: {qtd_prob} problema(s) e {qtd_corr} correcao(oes) segura(s). Relatorio: {arquivo}"
    return f"Auditoria concluida sem problema critico. {qtd_corr} correcao(oes) segura(s). Relatorio: {arquivo}"
