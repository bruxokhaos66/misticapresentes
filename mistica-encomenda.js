/*
 * Módulo central da regra de produtos sob encomenda.
 *
 * A API agora fornece `sob_encomenda` e `limite_encomenda`. Esses campos são
 * a fonte principal. A categoria "Achados Místicos" e o selo "Sob encomenda"
 * permanecem apenas como compatibilidade para cadastros antigos.
 */
(function (global) {
  "use strict";

  function normalizar(value) {
    return String(value == null ? "" : value)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  var CATEGORIA_ACHADOS = "Achados Místicos";
  var SELO_SOB_ENCOMENDA = "Sob encomenda";
  var CATEGORIA_NORM = normalizar(CATEGORIA_ACHADOS);
  var SELO_NORM = normalizar(SELO_SOB_ENCOMENDA);

  function categoriaDe(product) {
    if (!product) return "";
    return product.category != null ? product.category : product.categoria;
  }

  function seloDe(product) {
    if (!product) return "";
    if (product.tag != null && product.tag !== "") return product.tag;
    if (product.selo != null && product.selo !== "") return product.selo;
    return "";
  }

  function valorExplicito(product) {
    if (!product) return null;
    if (typeof product.sobEncomenda === "boolean") return product.sobEncomenda;
    if (typeof product.sob_encomenda === "boolean") return product.sob_encomenda;
    if (product.sob_encomenda === 1 || product.sob_encomenda === "1") return true;
    if (product.sob_encomenda === 0 || product.sob_encomenda === "0") return false;
    return null;
  }

  function isSobEncomenda(product) {
    if (!product) return false;
    var explicito = valorExplicito(product);
    if (explicito !== null) return explicito;
    return normalizar(categoriaDe(product)) === CATEGORIA_NORM
      || normalizar(seloDe(product)) === SELO_NORM;
  }

  function limiteDe(product) {
    if (!product) return 10;
    var raw = product.limiteEncomenda != null
      ? product.limiteEncomenda
      : product.limite_encomenda;
    var numero = Number(raw);
    return Number.isInteger(numero) && numero > 0 ? numero : 10;
  }

  global.misticaEncomenda = {
    normalizar: normalizar,
    isSobEncomenda: isSobEncomenda,
    limiteDe: limiteDe,
    CATEGORIA_ACHADOS: CATEGORIA_ACHADOS,
    SELO_SOB_ENCOMENDA: SELO_SOB_ENCOMENDA,
    PRAZO_TEXTO: "Prazo estimado de preparação: até 10 dias úteis, além do prazo de transporte.",
    BADGE: "Sob encomenda",
    CARD_NOTE: "Envio após confirmação de disponibilidade",
    ESTOQUE_NOTE: "Disponibilidade confirmada após o pagamento",
    COMO_FUNCIONA_TITULO: "Como funciona a encomenda",
    COMO_FUNCIONA_TEXTO:
      "Este produto será adquirido especialmente para você após a confirmação do pagamento. A disponibilidade será verificada com o fornecedor e o prazo de preparação será informado durante o acompanhamento do pedido.",
    COMO_FUNCIONA_AVISO:
      "Caso o item fique indisponível, entraremos em contato para oferecer uma alternativa, crédito na loja ou reembolso integral.",
    CHECKOUT_AVISO:
      "Seu pedido contém um ou mais produtos sob encomenda. A disponibilidade será confirmada após o pagamento. Caso algum item fique indisponível, nossa equipe entrará em contato para apresentar alternativas ou realizar o reembolso correspondente.",
    CHECKOUT_CONFIRMA: "Estou ciente de que este pedido contém produto sob encomenda.",
  };
})(typeof window !== "undefined" ? window : this);
