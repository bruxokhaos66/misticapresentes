/*
 * Cartão de crédito (Mercado Pago) no checkout do site.
 *
 * Nunca lida com número de cartão/CVV em texto: usa o CardForm oficial do
 * SDK MercadoPago.js v2 (carregado só quando a integração está habilitada),
 * que monta os campos sensíveis como iframes seguros do próprio Mercado
 * Pago. Este arquivo só envia ao backend o token gerado pelo SDK, nunca os
 * dados do cartão.
 *
 * O pedido é sempre criado pelo mesmo caminho já usado pelo Pix
 * (window.misticaCriarPedido, ver mobile-sync.js) -- reaproveita a mesma
 * Idempotency-Key de checkout, então gerar o Pix e depois pagar com cartão
 * (ou vice-versa) para o mesmo carrinho aponta sempre para o MESMO pedido,
 * nunca cria um pedido duplicado.
 */
(function () {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SDK_URL = "https://sdk.mercadopago.com/js/v2";
  const ATTEMPT_KEY_STORAGE_PREFIX = "mistica_mp_tentativa_";

  // Estilo dos Secure Fields (número, validade, CVV) -- iframes do próprio
  // Mercado Pago, então só as propriedades documentadas em
  // github.com/mercadopago/sdk-js/blob/main/docs/fields.md#style têm efeito:
  // color, fontFamily, fontSize, fontStyle, fontVariant, fontWeight, height,
  // margin*, padding*, placeholderColor, textAlign, width. NÃO existe
  // backgroundColor nem estados por CSS (:focus/:valid/:invalid) na API --
  // o fundo/borda de cada campo é resolvido pelo wrapper .mp-secure-field
  // (ver v2-mercadopago-checkout.css), não por aqui. Sem isso, o SDK usa a
  // cor de texto padrão dele (escura), que fica ilegível sobre o fundo
  // escuro do tema premium da Mística.
  const MP_SECURE_FIELD_STYLE = {
    color: "#F7E7BE",
    fontSize: "16px",
    fontWeight: "500",
    fontFamily: "Inter, system-ui, sans-serif",
    placeholderColor: "rgba(247, 231, 190, 0.55)",
  };

  let mpConfig = null; // { enabled, public_key }
  let mpInstance = null;
  let cardForm = null;
  let sdkLoadPromise = null;
  let pedidoAtual = null; // { id, pixTxid, totalFinal } -- o mesmo pedido usado pelo Pix
  let cardFormMontadoParaPedido = null;

  function currency(valor) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(valor || 0);
  }

  function statusEl() {
    return document.getElementById("mpCardStatus");
  }

  function setCardStatus(mensagem, tom) {
    const el = statusEl();
    if (!el) return;
    el.textContent = mensagem || "";
    if (tom) el.setAttribute("data-tone", tom);
    else el.removeAttribute("data-tone");
  }

  function carregarSdk() {
    if (window.MercadoPago) return Promise.resolve();
    if (sdkLoadPromise) return sdkLoadPromise;
    sdkLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SDK_URL;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Não foi possível carregar o SDK do Mercado Pago."));
      document.head.appendChild(script);
    });
    return sdkLoadPromise;
  }

  async function obterConfigPublica() {
    if (mpConfig) return mpConfig;
    try {
      const resposta = await fetch(`${API_BASE}/api/payments/mercadopago/config`, { cache: "no-store" });
      mpConfig = await resposta.json().catch(() => ({ enabled: false }));
    } catch {
      mpConfig = { enabled: false };
    }
    return mpConfig;
  }

  function gerarIdempotencyKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `mp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  // Chave de tentativa de cartão: persistida por pedido para sobreviver a um
  // reload de página enquanto a requisição ainda está em andamento (não
  // perde a proteção de idempotência num F5 no meio do processamento). É
  // limpa assim que uma resposta final (aprovado/pendente/recusado) chega.
  function obterChaveTentativa(pedidoId) {
    const armazenada = sessionStorage.getItem(ATTEMPT_KEY_STORAGE_PREFIX + pedidoId);
    if (armazenada) return armazenada;
    const nova = gerarIdempotencyKey();
    sessionStorage.setItem(ATTEMPT_KEY_STORAGE_PREFIX + pedidoId, nova);
    return nova;
  }

  function limparChaveTentativa(pedidoId) {
    sessionStorage.removeItem(ATTEMPT_KEY_STORAGE_PREFIX + pedidoId);
  }

  // O SDK do Mercado Pago calcula a posição/tamanho dos iframes dos Secure
  // Fields (#mpCardNumber/#mpExpirationDate/#mpSecurityCode) UMA VEZ, no
  // instante em que cardForm() é chamado -- ele não reobserva o layout
  // depois. Se essa chamada acontecer com o painel ainda oculto (hidden,
  // display:none, ou com getBoundingClientRect() zerado porque o layout/
  // scroll ainda não terminou de assentar), os iframes ficam "presos" numa
  // coordenada antiga e nunca recebem clique/digitação -- mesmo que
  // visualmente o container pareça normal depois. Por isso nunca chamamos
  // mpInstance.cardForm(...) sem antes confirmar que o painel já está
  // visível e com layout final (dois requestAnimationFrame garantem que o
  // navegador já aplicou estilo e completou pelo menos um ciclo de layout
  // desde que o painel foi revelado).
  function painelCartaoPronto(painel) {
    if (!painel || painel.hidden) return false;
    const estilo = getComputedStyle(painel);
    if (estilo.display === "none" || estilo.visibility === "hidden") return false;
    const rect = painel.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function aguardarPainelCartaoVisivel(painel) {
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => resolve(painelCartaoPronto(painel)));
      });
    });
  }

  function alternarFormaPagamento(forma) {
    const pixPanel = document.getElementById("pixPaymentPanel");
    const cardPanel = document.getElementById("cardPaymentPanel");
    document.querySelectorAll(".payment-method-btn").forEach(btn => {
      const ativo = btn.getAttribute("data-payment-method") === forma;
      btn.classList.toggle("is-active", ativo);
      btn.setAttribute("aria-selected", ativo ? "true" : "false");
    });
    if (pixPanel) pixPanel.hidden = forma !== "pix";
    if (cardPanel) cardPanel.hidden = forma !== "cartao";
    if (forma === "cartao") montarFormularioCartao().catch(err => setCardStatus(err.message, "erro"));
  }

  async function garantirPedidoAtual() {
    // Reaproveita exatamente a mesma criação de pedido usada pelo Pix
    // (mesma Idempotency-Key de checkout, mesmo carrinho): nunca cria um
    // segundo pedido só porque o cliente escolheu cartão em vez de Pix.
    if (typeof window.misticaCriarPedido !== "function" || typeof window.misticaGetCart !== "function") {
      throw new Error("Carrinho indisponível no momento.");
    }
    const cart = window.misticaGetCart();
    if (!cart.length) throw new Error("Adicione pelo menos um produto ao carrinho antes de pagar.");
    const pedido = await window.misticaCriarPedido(cart);
    pedidoAtual = { id: pedido.id, pixTxid: pedido.pixTxid, totalFinal: pedido.totalFinal };
    return pedidoAtual;
  }

  async function montarFormularioCartao() {
    const cfg = await obterConfigPublica();
    if (!cfg.enabled || !cfg.public_key) return;
    await carregarSdk();
    // trackingDisabled: true -- opção oficial do SDK (mercadopago/sdk-js,
    // README "API": "Enable/disable tracking of generic usage metrics",
    // default false). Candidata mais próxima, documentada pelo próprio
    // fabricante, do script inline de telemetria bloqueado pela CSP
    // (script-src) reportado após a PR #365 -- ver docs/admin/CSP.md,
    // seção "Auditoria do script inline bloqueado (pós-#368)" para o que
    // foi e não foi possível confirmar sobre o efeito real dela aqui.
    // advancedFraudPrevention É DELIBERADAMENTE mantido no default (true,
    // não passado): é uma opção separada, documentada como controle de
    // prevenção de fraude (não de telemetria genérica) -- desativá-la afeta
    // aprovação/risco de fraude e não há evidência de que esteja ligada a
    // este script-src específico.
    if (!mpInstance) mpInstance = new window.MercadoPago(cfg.public_key, { locale: "pt-BR", trackingDisabled: true });

    let pedido;
    try {
      pedido = await garantirPedidoAtual();
    } catch (err) {
      setCardStatus(err.message || "Não foi possível preparar o pagamento agora.", "erro");
      return;
    }

    if (cardFormMontadoParaPedido === pedido.id && cardForm) return; // já montado para este pedido/total

    const cardPanel = document.getElementById("cardPaymentPanel");
    const painelVisivel = await aguardarPainelCartaoVisivel(cardPanel);
    if (!painelVisivel) {
      // O painel foi ocultado (ex.: usuário voltou para Pix) antes do layout
      // se estabilizar -- não monta o SDK às cegas; a próxima vez que
      // "Cartão de crédito" for selecionado, alternarFormaPagamento chama
      // montarFormularioCartao() de novo e este mesmo check roda outra vez.
      return;
    }

    if (cardForm && typeof cardForm.unmount === "function") {
      // Nunca deixa uma instância antiga do CardForm (montada para um
      // pedido/total anterior) presa junto com uma nova -- evita iframes
      // duplicados dentro de #mpCardNumber/#mpExpirationDate/#mpSecurityCode.
      try {
        cardForm.unmount();
      } catch {
        /* instância antiga já pode ter sido descartada pelo próprio SDK */
      }
    }

    cardFormMontadoParaPedido = pedido.id;

    cardForm = mpInstance.cardForm({
      amount: String(pedido.totalFinal || 0),
      // Sem isso, o SDK monta cardNumber/securityCode/expirationDate no modo
      // padrão (iframe: false), que exige <input> nesses três campos -- os
      // <div id="mpCardNumber/mpExpirationDate/mpSecurityCode"> do HTML nunca
      // recebem os Secure Fields (iframes) do Mercado Pago, e por isso
      // ficavam visíveis mas não aceitavam clique/digitação.
      iframe: true,
      autoMount: true,
      form: {
        id: "mpCardForm",
        cardholderName: { id: "mpCardholderName", placeholder: "Nome impresso no cartão" },
        cardNumber: { id: "mpCardNumber", placeholder: "0000 0000 0000 0000", style: MP_SECURE_FIELD_STYLE },
        expirationDate: { id: "mpExpirationDate", placeholder: "MM/AA", style: MP_SECURE_FIELD_STYLE },
        securityCode: { id: "mpSecurityCode", placeholder: "CVV", style: MP_SECURE_FIELD_STYLE },
        installments: { id: "mpInstallments" },
        identificationType: { id: "mpIdentificationType" },
        identificationNumber: { id: "mpDocNumber", placeholder: "CPF" },
        cardholderEmail: { id: "mpCardEmail", placeholder: "seu@email.com" },
        issuer: { id: "mpIssuer" },
      },
      callbacks: {
        onFormMounted: (error) => {
          if (error) {
            console.error("[MercadoPago] onFormMounted retornou erro:", sanitizarErroParaLog(error));
            desabilitarFormularioCartao();
            return;
          }
          // autoMount monta os Secure Fields de forma assíncrona -- dá um
          // instante para os iframes aparecerem no DOM antes de confirmar
          // que o formulário está realmente utilizável (o bug relatado era
          // exatamente onFormMounted sem erro, mas nenhum iframe montado
          // dentro de #mpCardNumber/#mpExpirationDate/#mpSecurityCode).
          window.setTimeout(() => {
            if (!tresIframesSeguraMontados()) {
              console.error("[MercadoPago] onFormMounted sem erro, mas os 3 iframes de Secure Fields não foram encontrados no DOM.");
              desabilitarFormularioCartao();
            }
          }, 300);
        },
        onInstallmentsReceived: () => {
          const nota = document.getElementById("mpInstallmentsNote");
          if (nota) nota.textContent = "Parcelamento sujeito a juros conforme exibido no seletor acima.";
        },
        onSubmit: (event) => {
          event.preventDefault();
          enviarPagamentoCartao();
        },
        onFetching: () => {
          return () => {};
        },
      },
    });
  }

  // Nunca loga o erro do SDK inteiro (pode incluir contexto interno da
  // requisição) -- só uma mensagem curta e sanitizada, sem Public Key,
  // Access Token, token do cartão, número do cartão, CVV, CPF ou e-mail.
  function sanitizarErroParaLog(error) {
    if (!error) return "erro desconhecido";
    const mensagem = typeof error === "string" ? error : (error.message || error.type || "erro desconhecido");
    return String(mensagem).slice(0, 300);
  }

  function tresIframesSeguraMontados() {
    return ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"].every(
      id => document.querySelectorAll(`#${id} iframe`).length === 1,
    );
  }

  function desabilitarFormularioCartao() {
    const botao = document.getElementById("mpCardSubmit");
    if (botao) botao.disabled = true;
    setCardStatus("Não foi possível carregar os campos seguros do cartão. Use o Pix ou tente novamente.", "erro");
  }

  function definirCarregando(carregando) {
    const botao = document.getElementById("mpCardSubmit");
    if (!botao) return;
    botao.disabled = carregando;
    botao.textContent = carregando ? "Processando pagamento..." : "Pagar com cartão";
  }

  async function enviarPagamentoCartao() {
    if (!cardForm || !pedidoAtual) return setCardStatus("Formulário de pagamento não está pronto.", "erro");
    definirCarregando(true);
    setCardStatus("Processando pagamento com segurança pelo Mercado Pago...", "info");

    let dados;
    try {
      dados = cardForm.getCardFormData();
    } catch {
      definirCarregando(false);
      return setCardStatus("Não foi possível ler os dados do cartão. Revise os campos e tente novamente.", "erro");
    }
    if (!dados || !dados.token) {
      definirCarregando(false);
      return setCardStatus("Não foi possível gerar o token do cartão. Revise os dados e tente novamente.", "erro");
    }

    const pedidoId = pedidoAtual.id;
    const idempotencyKey = obterChaveTentativa(pedidoId);
    const corpo = {
      pedido_id: pedidoId,
      txid: pedidoAtual.pixTxid,
      token: dados.token,
      payment_method_id: dados.paymentMethodId,
      installments: Number(dados.installments || 1),
      issuer_id: dados.issuerId || null,
      payer: {
        email: dados.cardholderEmail,
        documento_tipo: dados.identificationType || "CPF",
        documento_numero: dados.identificationNumber,
      },
    };

    let resposta;
    try {
      const requisicao = await fetch(`${API_BASE}/api/payments/mercadopago/card`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(corpo),
      });
      resposta = await requisicao.json().catch(() => ({}));
      if (!requisicao.ok) throw new Error(resposta.detail || resposta.message || "Não foi possível processar o pagamento.");
    } catch (erro) {
      definirCarregando(false);
      // Falha de rede/timeout: NÃO limpa a chave de tentativa -- uma nova
      // tentativa (novo clique, ou reload da página) reaproveita a mesma
      // Idempotency-Key, então o Mercado Pago nunca processa uma segunda
      // cobrança para o mesmo clique.
      setCardStatus(erro.message || "Falha de conexão. Verifique sua internet e tente novamente.", "erro");
      return;
    }

    // Resposta final recebida (aprovado, pendente ou recusado): a tentativa
    // terminou, uma nova tentativa (ex.: outro cartão) deve usar uma chave
    // nova.
    limparChaveTentativa(pedidoId);
    definirCarregando(false);

    if (resposta.status === "aprovado") {
      const parcelasTexto = resposta.parcelas > 1 ? `em ${resposta.parcelas}x` : "à vista";
      setCardStatus(
        `Pagamento aprovado! Pedido #${pedidoId} confirmado (${currency(resposta.valor)} ${parcelasTexto}). ` +
        "O comprovante será enviado e você pode acompanhar o andamento do pedido a qualquer momento.",
        "sucesso",
      );
      window.misticaTrack?.("purchase", { transaction_id: String(pedidoId), currency: "BRL", value: resposta.valor, payment_method: "mercadopago_cartao" });
      // Só limpa o carrinho DEPOIS da confirmação do servidor -- nunca antes
      // (evita perder o carrinho se a cobrança falhar) e nunca com base
      // apenas numa resposta local/otimista do navegador.
      window.clearCart?.();
      if (typeof window.misticaPagamentoCartaoAprovado === "function") {
        window.misticaPagamentoCartaoAprovado(pedidoId, resposta);
      }
      cardFormMontadoParaPedido = null;
      pedidoAtual = null;
    } else if (resposta.status === "pendente") {
      setCardStatus(
        (resposta.mensagem || "Pagamento em análise.") +
        ` Pedido #${pedidoId} — a análise está em andamento, não é necessário pagar novamente agora. Você será avisado assim que for confirmado.`,
        "info",
      );
      if (typeof window.misticaPagamentoCartaoPendente === "function") {
        window.misticaPagamentoCartaoPendente(pedidoId, resposta);
      }
    } else {
      // Recusado/cancelado: nunca gera pedido novo -- o cliente pode tentar
      // outro cartão ou trocar para Pix no mesmo pedido.
      setCardStatus(resposta.mensagem || "Não foi possível aprovar o pagamento. Tente outro cartão ou use o Pix.", "erro");
    }
  }

  async function iniciar() {
    const cfg = await obterConfigPublica();
    const botaoCartao = document.querySelector("[data-mp-toggle]");
    if (!cfg.enabled) {
      if (botaoCartao) botaoCartao.hidden = true;
      return;
    }
    if (botaoCartao) botaoCartao.hidden = false;

    document.querySelectorAll("[data-payment-method]").forEach(btn => {
      btn.addEventListener("click", () => alternarFormaPagamento(btn.getAttribute("data-payment-method")));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }

  window.misticaMercadoPagoCheckout = { alternarFormaPagamento, obterConfigPublica };
})();
