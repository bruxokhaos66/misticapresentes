/*
 * Módulo central da categoria "Achados Místicos" (produtos sob encomenda).
 *
 * Concentra num único lugar a regra que identifica um produto sob encomenda e
 * os textos comerciais usados em vários pontos do site (cards, página do
 * produto, carrinho e checkout). Assim evitamos espalhar a lógica de categoria
 * e o prazo de preparação por diversos arquivos.
 *
 * Um produto é considerado "sob encomenda" quando:
 *   - a categoria for "Achados Místicos" (ignorando acentos/maiúsculas), ou
 *   - o selo for "Sob encomenda".
 *
 * Aceita tanto os campos do catálogo já normalizado (category, tag) quanto os
 * nomes crus vindos da API (categoria, selo).
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

  function isSobEncomenda(product) {
    if (!product) return false;
    return normalizar(categoriaDe(product)) === CATEGORIA_NORM
      || normalizar(seloDe(product)) === SELO_NORM;
  }

  global.misticaEncomenda = {
    normalizar: normalizar,
    isSobEncomenda: isSobEncomenda,
    CATEGORIA_ACHADOS: CATEGORIA_ACHADOS,
    SELO_SOB_ENCOMENDA: SELO_SOB_ENCOMENDA,
    // Texto único do prazo de preparação. Editar aqui reflete em todo o site.
    PRAZO_TEXTO: "Prazo estimado de preparação: até 10 dias úteis, além do prazo de transporte.",
    BADGE: "Sob encomenda",
    CARD_NOTE: "Envio após confirmação de disponibilidade",
    // Aviso curto de estoque para não prometer pronta entrega.
    ESTOQUE_NOTE: "Disponibilidade confirmada após o pagamento",
    COMO_FUNCIONA_TITULO: "Como funciona a encomenda",
    COMO_FUNCIONA_TEXTO:
      "Este produto faz parte da seleção especial Achados Místicos e será adquirido especialmente para você após a confirmação do pagamento. A disponibilidade será verificada com o fornecedor e o prazo de preparação será informado durante o acompanhamento do pedido.",
    COMO_FUNCIONA_AVISO:
      "Caso o item fique indisponível, entraremos em contato para oferecer uma alternativa, crédito na loja ou reembolso integral.",
    CHECKOUT_AVISO:
      "Seu pedido contém um ou mais produtos sob encomenda. A disponibilidade será confirmada após o pagamento. Caso algum item fique indisponível, nossa equipe entrará em contato para apresentar alternativas ou realizar o reembolso correspondente.",
    CHECKOUT_CONFIRMA: "Estou ciente de que este pedido contém produto sob encomenda.",
  };
})(typeof window !== "undefined" ? window : this);
