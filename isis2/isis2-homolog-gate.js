// Isis 2.0 — portão de homologação controlada.
//
// Único caminho capaz de ligar isis2.enabled/escola/refinamento no MESMO
// domínio de produção, para uma allowlist fechada de contas autorizadas,
// sem tocar nas flags estáticas de site-config.js (que continuam false em
// produção -- ver isis2/README.md, seção "Homologação controlada").
//
// A autorização é decidida inteiramente pelo servidor
// (backend/isis2_homolog.py::obter_homolog_config): este script só chama
// GET /api/isis2/homolog-config com o cookie de sessão já existente
// (mistica_painel_sessao ou mistica_aluno_sessao, ambos HttpOnly, nunca
// lidos por JavaScript) e aplica a resposta. Não lê -- e não pode ser
// convencido a ler -- query string, hash, atributo HTML, header
// customizado, localStorage ou sessionStorage. Qualquer resposta que não
// seja explicitamente {enabled:true, homologacao:true, ...} (erro de
// rede, API indisponível, JSON inesperado, status != 200) mantém a Isis
// 2.0 desativada: este arquivo nunca define enabled=true por omissão.
(() => {
  if (window.__MISTICA_ISIS2_HOMOLOG_GATE__) return;
  window.__MISTICA_ISIS2_HOMOLOG_GATE__ = true;

  const VERSION = "20260717-isis2-homolog-fase-homologacao";
  const cfg = window.misticaSiteConfig || {};

  function injetarLoader() {
    if (document.getElementById("misticaIsis2LoaderScript")) return;
    const script = document.createElement("script");
    script.id = "misticaIsis2LoaderScript";
    script.src = `isis2/isis2-loader.js?v=${VERSION}`;
    script.defer = true;
    document.head.appendChild(script);
  }

  // Produção estática: se site-config.js já habilitou isis2 por conta
  // própria (nunca deve acontecer em produção -- ver isis2/README.md),
  // respeita o valor estático e não faz nenhuma chamada de rede extra.
  if (cfg.isis2?.enabled === true) {
    injetarLoader();
    return;
  }

  const apiBase = String(cfg.apiBaseUrl || "").replace(/\/$/, "");
  // Fail-safe: sem apiBaseUrl configurado, não há como validar autorização
  // no servidor -- a Isis 2.0 permanece desativada.
  if (!apiBase) return;

  function ativarHomologacao(dados) {
    // Nunca mescla parcialmente: ou os quatro campos exigidos vêm true do
    // servidor, ou nada é ligado.
    const autorizado =
      dados &&
      dados.enabled === true &&
      dados.homologacao === true;
    if (!autorizado) return;

    window.misticaSiteConfig = window.misticaSiteConfig || {};
    window.misticaSiteConfig.isis2 = {
      enabled: true,
      homologacao: true,
      escola: {
        enabled: dados.escola === true,
        refinamento: {
          enabled: dados.escola === true && dados.refinamento === true,
        },
      },
    };
    window.__MISTICA_ISIS2_HOMOLOG_ATIVO__ = true;
    injetarLoader();
    mostrarIndicadorHomologacao();
  }

  function mostrarIndicadorHomologacao() {
    if (document.getElementById("misticaIsis2HomologBadge")) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `isis2/isis2-homolog-badge.css?v=${VERSION}`;
    document.head.appendChild(link);

    const badge = document.createElement("div");
    badge.id = "misticaIsis2HomologBadge";
    badge.setAttribute("role", "status");
    badge.setAttribute("aria-live", "polite");
    badge.textContent = "Isis em homologação";
    const montar = () => document.body.appendChild(badge);
    if (document.body) montar();
    else document.addEventListener("DOMContentLoaded", montar, { once: true });
  }

  fetch(`${apiBase}/api/isis2/homolog-config`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  })
    .then(resposta => (resposta.ok ? resposta.json() : null))
    .then(dados => ativarHomologacao(dados))
    .catch(() => {
      // Fail-safe: qualquer falha de rede/parse mantém a Isis 2.0
      // desativada -- nunca ativa por padrão.
    });
})();
