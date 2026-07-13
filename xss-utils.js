// xss-utils.js — Utilitários centralizados de sanitização para o frontend da Mística.
//
// Expõe window.MisticaXSS com funções específicas para cada contexto de inserção:
//
//   MisticaXSS.text(str)       → texto puro para textContent / aria-label
//   MisticaXSS.attr(str)       → valor seguro para atributos HTML (dupla e simples aspa)
//   MisticaXSS.html(str)       → texto para inserção dentro de innerHTML (entidades HTML)
//   MisticaXSS.url(str)        → URL validada (apenas http/https), ou string vazia
//   MisticaXSS.safeUrlOrEmpty  → alias explícito para validação de URL
//   MisticaXSS.datasetId(str)  → valor seguro para data-* attributes
//
// Este arquivo NÃO define módulos ES. Ele é carregado via <script defer> antes
// de app.js e expõe tudo em window para consumo dos demais scripts.

(function () {
  "use strict";

  var ENTITY_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };

  function text(value) {
    return String(value == null ? "" : value);
  }

  function escapeHtmlEntities(value) {
    return text(value).replace(/[&<>"']/g, function (ch) {
      return ENTITY_MAP[ch];
    });
  }

  /**
   * Valida e normaliza uma URL. Retorna string vazia para protocolos
   * perigosos (javascript:, data:, vbscript:) ou URLs malformadas.
   * Aceita apenas http: e https: como protocolos externos.
   * URLs relativas (que começam com / ou ./ ou ../) são preservadas.
   */
  function safeUrl(value) {
    var raw = text(value).trim();
    if (!raw) return "";

    // URLs relativas são permitidas (começam com /, ./, ../ ou #)
    if (/^[./#]/.test(raw) || !/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(raw)) {
      return raw;
    }

    try {
      var url = new URL(raw);
      if (url.protocol === "http:" || url.protocol === "https:") {
        return url.href;
      }
    } catch (_) {
      // URL malformada
    }

    return "";
  }

  /**
   * Valida uma URL para uso em src de <img>. Além de http/https, aceita
   * data:image/* (para compatibilidade com imagens Base64 quando necessário
   * explicitamente). Em todos os outros contextos, use safeUrl().
   */
  function safeImageUrl(value) {
    var raw = text(value).trim();
    if (!raw) return "";
    if (/^[./#]/.test(raw) || !/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(raw)) {
      return raw;
    }
    try {
      var url = new URL(raw);
      if (url.protocol === "http:" || url.protocol === "https:") {
        return url.href;
      }
      // Permitir data:image/* para imagens inline quando necessário
      if (url.protocol === "data:" && /^data:image\//i.test(raw)) {
        return raw;
      }
    } catch (_) {}
    return "";
  }

  /**
   * Escapa valor para uso seguro dentro de data-* attributes.
   * Equivalente a attr() mas com nome de semântica explícita.
   */
  function datasetId(value) {
    return escapeHtmlEntities(value);
  }

  // Expor globalmente
  window.MisticaXSS = {
    text: text,
    attr: escapeHtmlEntities,
    html: escapeHtmlEntities,
    url: safeUrl,
    imageUrl: safeImageUrl,
    safeUrlOrEmpty: safeUrl,
    datasetId: datasetId,
  };

  // Compat: scripts antigos que definem esc() localmente continuarão
  // funcionando. Scripts novos devem usar MisticaXSS.html().
})();
