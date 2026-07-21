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

  // -----------------------------------------------------------------------
  // Máquina de estado do CardToken (uso único, nunca reaproveitado).
  //
  // O CardToken gerado pelo SDK do Mercado Pago é descartável: só pode ser
  // enviado em UMA tentativa de pagamento. Este arquivo NUNCA guarda o
  // token numa variável de módulo entre tentativas -- ele só existe como
  // variável local dentro de enviarPagamentoCartao(), do instante em que o
  // SDK o cria (createCardToken(), método oficial documentado em
  // mercadopago/sdk-js, docs/card-form.md) até o instante em que a
  // requisição ao backend é iniciada, quando a referência local é
  // descartada (setada como null) antes mesmo do fetch responder -- nunca
  // depois. Isso vale igualmente para sucesso, recusa, HTTP 400/422/500,
  // timeout, falha de rede ou resposta que não possa ser interpretada: em
  // nenhum desses casos o mesmo token é reenviado. Uma nova tentativa
  // (outro clique, outro cartão, voltar do Pix) sempre passa de novo por
  // createCardToken(), nunca por getCardFormData() sozinho (que só relê o
  // que já foi tokenizado, podendo devolver um token já consumido).
  const TOKEN_ESTADO = {
    SEM_TOKEN: "sem_token",
    TOKENIZANDO: "tokenizando",
    TOKEN_PRONTO: "token_pronto",
    ENVIANDO: "enviando",
    TOKEN_CONSUMIDO: "token_consumido",
    AGUARDANDO_NOVA_TOKENIZACAO: "aguardando_nova_tokenizacao",
  };
  let tokenEstado = TOKEN_ESTADO.SEM_TOKEN;
  // Callback pendente de createCardToken() em andamento (onCardTokenReceived
  // é a única forma oficial de saber quando o SDK terminou) -- nunca mais
  // de uma tokenização em voo por vez (ver trava síncrona em
  // enviarPagamentoCartao/cartaoProcessando).
  let resolverTokenPendente = null;

  function currency(valor) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(valor || 0);
  }

  // ---------------------------------------------------------------------
  // Normalização de mensagens de erro exibidas ao cliente.
  //
  // Bug corrigido: em vários pontos deste arquivo (principalmente na
  // resposta não-2xx de POST /api/payments/mercadopago/card) o código fazia
  // `new Error(resposta.detail || resposta.message || "...")`. Quando o
  // backend responde com um erro de validação do FastAPI/Pydantic (HTTP
  // 422), `detail` NÃO é uma string -- é um array de objetos
  // `{loc, msg, type, input}`. `new Error(arrayDeObjetos).message` vira a
  // string "[object Object]" (via Array.prototype.toString ->
  // Object.prototype.toString em cada item), que então era exibida
  // diretamente ao cliente. O mesmo padrão (objeto/array jogado direto na
  // tela) podia se repetir em qualquer outro ponto que exibisse um erro sem
  // normalizar primeiro.
  //
  // normalizarMensagemErro() é o único ponto que decide o que aparece na
  // tela para qualquer erro (string, Error, objeto, array ou corpo de
  // resposta HTTP já parseado como JSON): extrai a primeira mensagem
  // amigável disponível, nunca devolve "[object Object]"/JSON bruto, nunca
  // deixa passar algo que pareça token/credencial/dado de cartão, e cai no
  // fallback genérico quando nada aproveitável é encontrado.
  // ---------------------------------------------------------------------

  const FALLBACK_ERRO_PAGAMENTO =
    "Não foi possível processar o pagamento. Revise os dados e tente novamente ou escolha Pix.";

  // Só os poucos casos em que vale a pena traduzir um código técnico
  // conhecido que eventualmente chegue em inglês/bruto até aqui -- a
  // tradução principal de status_detail já acontece no backend
  // (mensagem_amigavel_pagamento, backend/pedido_comercial.py), que é
  // sempre a fonte preferida (ver ordem de campos em extrairMensagemAmigavel).
  const MAPA_ERROS_TECNICOS = {
    "invalid user identification number": "CPF inválido. Confira o número informado.",
    "cc_rejected_bad_filled_card_number": "Número do cartão inválido. Confira e tente novamente.",
    "cc_rejected_bad_filled_date": "Validade do cartão inválida.",
    "cc_rejected_bad_filled_security_code": "Código de segurança (CVV) inválido.",
    "cc_rejected_bad_filled_other": "Revise os dados do cartão e tente novamente.",
    "cc_rejected_insufficient_amount": "Saldo ou limite insuficiente no cartão.",
    "cc_rejected_high_risk": "Pagamento não autorizado por critérios de segurança.",
    "cc_rejected_call_for_authorize": "Cartão requer autorização do emissor para este valor.",
    "cc_rejected_card_disabled": "Cartão desabilitado. Fale com o emissor ou use outro cartão.",
    "cc_rejected_duplicated_payment": "Pagamento duplicado detectado para este pedido.",
    "cc_rejected_max_attempts": "Número máximo de tentativas excedido para este cartão.",
    "cc_rejected_other_reason": "O pagamento não foi autorizado. Tente outro cartão ou use o Pix.",
  };

  // Nunca exibir algo que pareça token/segredo/número de cartão/CPF/endereço
  // de verdade -- não proíbe palavras genéricas como "cartão"/"CPF"/
  // "endereço" em mensagens amigáveis normais (isso o próprio backend já
  // escreve em PT-BR), só bloqueia o formato de um DADO sensível de verdade:
  // token longo, chave pública/Access Token do Mercado Pago, número com
  // cara de cartão (13-19 dígitos) ou de CPF (11 dígitos, com ou sem
  // pontuação), header de autenticação, ou um logradouro com número (ex.:
  // "Rua das Flores, 123").
  const PADRAO_CONTEUDO_SENSIVEL =
    /(access[_-]?token|authorization\s*:|bearer\s+\S+|APP_USR-\S+|TEST-\S{10,}|\b\d{13,19}\b|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b(rua|av\.?|avenida|alameda|travessa|rodovia|estrada)\s+[^,\d]{2,40},?\s*(n[ºo°]?\.?\s*)?\d{1,6}\b)/i;

  // Nunca exibir HTML bruto (corpo de erro de proxy/servidor devolvido como
  // text/html em vez de JSON, por exemplo).
  const PADRAO_HTML = /<\/?[a-z][\s\S]*>/i;

  // Erros crus de rede/JS (TypeError do fetch, "is not a function" etc.)
  // não são mensagens pensadas para o cliente final -- nunca exibir o texto
  // técnico em inglês, sempre cair no fallback correspondente.
  const PADRAO_ERRO_TECNICO_JS =
    /(failed to fetch|networkerror|network request failed|is not a function|is not defined|cannot read propert|unexpected token|typeerror|syntaxerror)/i;

  function extrairMensagemAmigavel(valor, profundidade) {
    if (valor == null || profundidade > 4) return null;
    if (typeof valor === "string") {
      const texto = valor.trim();
      return texto || null;
    }
    if (typeof valor !== "object") return null; // number/boolean/function não viram mensagem
    if (Array.isArray(valor)) {
      for (const item of valor) {
        const msg = extrairMensagemAmigavel(item, profundidade + 1);
        if (msg) return msg;
      }
      return null;
    }
    if (valor instanceof Error) {
      if (valor.message && !PADRAO_ERRO_TECNICO_JS.test(valor.message)) {
        const direta = extrairMensagemAmigavel(valor.message, profundidade + 1);
        if (direta) return direta;
      }
      return extrairMensagemAmigavel(valor.cause, profundidade + 1);
    }
    // Ordem pedida: message; mensagem; detail; error; error_description;
    // cause; status_detail -- mais "msg", formato dos erros de validação
    // do FastAPI/Pydantic ([{msg: "..."}]).
    const CAMPOS = ["message", "mensagem", "detail", "error", "error_description", "cause", "status_detail", "msg"];
    for (const campo of CAMPOS) {
      if (campo in valor) {
        const msg = extrairMensagemAmigavel(valor[campo], profundidade + 1);
        if (msg) return msg;
      }
    }
    return null;
  }

  function sanitizarMensagemFinal(mensagem) {
    // Pydantic v2 prefixa erros de ValueError com "Value error, " -- os
    // validators deste projeto (ex.: EnderecoCobrancaIn) já escrevem a
    // mensagem em PT-BR, só sobra remover o prefixo técnico em inglês.
    const semPrefixo = mensagem.replace(/^value error,\s*/i, "").trim();
    if (!semPrefixo) return FALLBACK_ERRO_PAGAMENTO;
    const chave = semPrefixo.toLowerCase();
    if (MAPA_ERROS_TECNICOS[chave]) return MAPA_ERROS_TECNICOS[chave];
    if (PADRAO_CONTEUDO_SENSIVEL.test(semPrefixo)) return FALLBACK_ERRO_PAGAMENTO;
    if (PADRAO_ERRO_TECNICO_JS.test(semPrefixo)) return FALLBACK_ERRO_PAGAMENTO;
    if (PADRAO_HTML.test(semPrefixo)) return FALLBACK_ERRO_PAGAMENTO; // parece HTML bruto
    if (/^\s*[[{]/.test(semPrefixo)) return FALLBACK_ERRO_PAGAMENTO; // parece JSON bruto
    if (semPrefixo.length > 220) return FALLBACK_ERRO_PAGAMENTO; // stack trace/corpo bruto grande demais
    if (semPrefixo === "[object Object]" || /^\[object /.test(semPrefixo)) return FALLBACK_ERRO_PAGAMENTO;
    return semPrefixo;
  }

  function normalizarMensagemErro(erro, fallbackPersonalizado) {
    const extraida = extrairMensagemAmigavel(erro, 0);
    if (!extraida) return fallbackPersonalizado || FALLBACK_ERRO_PAGAMENTO;
    const sanitizada = sanitizarMensagemFinal(extraida);
    return sanitizada === FALLBACK_ERRO_PAGAMENTO && fallbackPersonalizado ? fallbackPersonalizado : sanitizada;
  }

  // ---------------------------------------------------------------------
  // Estado do seletor de parcelas (#mpInstallments).
  //
  // Bug corrigido: o <select id="mpInstallments" required> do HTML nunca
  // tinha nenhum estado próprio -- nascia vazio (sem <option>, sem
  // "disabled", sem texto) e só ficava utilizável se e quando o SDK do
  // Mercado Pago conseguisse identificar o cartão e preencher as opções
  // sozinho. `onInstallmentsReceived` ignorava por completo o primeiro
  // argumento (erro) da callback oficial do SDK -- então, sempre que a
  // consulta de parcelas falhava (BIN não reconhecido, bandeira sem
  // parcelamento configurado, resposta de erro da API do Mercado Pago,
  // rede lenta), o campo ficava vazio para sempre, sem nenhum aviso: para
  // quem está comprando, um <select> sem nenhuma opção e sem rótulo visível
  // é indistinguível de "o campo não existe".
  //
  // As funções abaixo controlam o texto/estado disabled do campo em cada
  // fase (antes do cartão ser identificado, consultando, com opções,
  // sem opções, com erro) -- nunca inventam as próprias opções de
  // parcelamento: quem preenche os <option> reais é sempre o SDK oficial
  // (fluxo oficial do CardForm, com `installments: { id: "mpInstallments" }`
  // na config), esta função só cuida do placeholder/estado ao redor disso.
  // ---------------------------------------------------------------------

  const PARCELAS_MSG = {
    inicial: "Informe o cartão para ver as parcelas",
    carregando: "Consultando parcelas…",
    erro: "Não foi possível consultar as opções de parcelamento. Verifique os dados do cartão ou tente novamente.",
    vazio: "Este cartão não possui opções de parcelamento disponíveis para esta compra.",
    opcoes: "Parcelamento sujeito a juros conforme exibido no seletor acima.",
  };

  let parcelasProntas = false; // true só quando o select tem opção(ões) real(is) selecionável(is)

  function elementoParcelas() {
    return document.getElementById("mpInstallments");
  }

  function limparOpcoesPlaceholder(select) {
    // Remove só as opções marcadas como placeholder por esta função --
    // nunca mexe em <option> reais inseridas pelo SDK (fluxo oficial).
    Array.from(select.querySelectorAll('option[data-placeholder="true"]')).forEach(op => op.remove());
  }

  function definirEstadoParcelas(estado) {
    const select = elementoParcelas();
    const nota = document.getElementById("mpInstallmentsNote");
    if (!select) return;
    parcelasProntas = false;
    if (estado === "opcoes") {
      // Não recria as <option> (são do SDK) -- só remove um eventual
      // placeholder deixado por um estado anterior e libera o campo.
      limparOpcoesPlaceholder(select);
      select.disabled = select.options.length === 0;
      parcelasProntas = select.options.length > 0;
    } else {
      select.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.setAttribute("data-placeholder", "true");
      placeholder.value = "";
      placeholder.textContent = PARCELAS_MSG[estado] || PARCELAS_MSG.inicial;
      placeholder.disabled = true;
      placeholder.selected = true;
      select.appendChild(placeholder);
      select.disabled = true;
    }
    select.setAttribute("aria-busy", estado === "carregando" ? "true" : "false");
    select.setAttribute("aria-describedby", "mpInstallmentsNote");
    if (nota) nota.textContent = PARCELAS_MSG[estado] || "";
    recalcularBotaoCartao();
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
    // Alternar entre Pix e cartão nunca reaproveita um token pendente --
    // não há nenhuma tentativa de pagamento em andamento neste ponto
    // (cartaoProcessando trava o clique de envio, não a troca de aba), mas
    // o estado é sempre realinhado para "sem_token" por clareza: a próxima
    // vez que "Cartão de crédito" for selecionado, um novo submit sempre
    // passa de novo por createCardToken().
    if (!cartaoProcessando) tokenEstado = TOKEN_ESTADO.SEM_TOKEN;
    // O rótulo do indicador de etapas (#checkoutSteps) refletia sempre
    // "Pagamento Pix", mesmo com "Cartão de crédito" selecionado -- nunca
    // mais mostra um método que o cliente não escolheu.
    const stepLabel = document.getElementById("checkoutStepPagamentoLabel");
    if (stepLabel) stepLabel.textContent = forma === "cartao" ? "Pagamento cartão" : "Pagamento Pix";
    // Nunca deixa uma mensagem de resultado de uma tentativa anterior
    // (ex.: "Pagamento aprovado! Pedido #32...") visível ao reabrir o
    // formulário de cartão para um pedido diferente/novo -- sem isso, o
    // texto ficava preso na tela mesmo com o formulário limpo, dando a
    // falsa impressão de que o pagamento atual já foi concluído.
    setCardStatus("");
    window.misticaEnderecoCobranca?.atualizarVisibilidade?.();
    if (forma === "cartao") montarFormularioCartao().catch(err => setCardStatus(normalizarMensagemErro(err), "erro"));
  }

  async function garantirPedidoAtual() {
    // Fase 3: mesma checagem única usada pelo Pix (window.misticaEntrega.
    // podeProsseguir(), definida em checkout-entrega-retirada.js) — nenhum
    // pedido/tentativa de pagamento com cartão é criado sem modalidade de
    // recebimento válida. O botão de cartão e a aba "Cartão de crédito" já
    // ficam desabilitados nesse caso; este guard cobre qualquer acionamento
    // alternativo.
    if (typeof window.misticaEntrega?.podeProsseguir === "function" && !window.misticaEntrega.podeProsseguir()) {
      window.misticaEntrega.focarSecaoRecebimento?.();
      throw new Error("Escolha retirada ou entrega para continuar.");
    }
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
      setCardStatus(normalizarMensagemErro(err, "Não foi possível preparar o pagamento agora."), "erro");
      return;
    }
    // O valor só é conhecido depois que o pedido existe -- atualiza o texto
    // do botão ("Pagar R$ XX,XX com cartão") assim que totalFinal chega,
    // nunca antes (nunca mostra um valor calculado no navegador).
    recalcularBotaoCartao();

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
    // Uma instância nova do CardForm nunca herda token/callback pendente da
    // anterior -- qualquer tokenização em voo da instância antiga (ex.:
    // onCardTokenReceived que ainda não respondeu) é descartada aqui.
    resolverTokenPendente = null;
    tokenEstado = TOKEN_ESTADO.SEM_TOKEN;

    cardFormMontadoParaPedido = pedido.id;
    // Nunca deixa opções de parcelas de uma montagem anterior (outro
    // pedido/cartão) visíveis enquanto o novo CardForm ainda não
    // identificou o cartão atual.
    definirEstadoParcelas("inicial");

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
        // Sinal OFICIAL de "o número do cartão mudou" (mercadopago/sdk-js,
        // docs/card-form.md: "onBinChange | bin: string | Callback
        // triggered when BIN has changed") -- é este o hook correto para
        // nunca reaproveitar a lista de parcelas de um cartão anterior
        // enquanto a nova consulta de installments (disparada pelo próprio
        // SDK em seguida) ainda não respondeu. BIN incompleto (cartão ainda
        // sendo digitado) volta para o estado inicial; BIN completo entra
        // em "consultando" até onInstallmentsReceived responder.
        onBinChange: (bin) => {
          if (!bin || String(bin).length < 6) {
            definirEstadoParcelas("inicial");
            return;
          }
          definirEstadoParcelas("carregando");
        },
        // (error, data) -- `data` é `{ paging, results: [...] }`
        // (mercadopago/sdk-js, docs/card-form.md), NUNCA um array solto.
        // Usado só como reforço de "bandeira não reconhecida" (onBinChange
        // já cobre a troca do número do cartão).
        onPaymentMethodsReceived: (error, data) => {
          const resultados = data && Array.isArray(data.results) ? data.results : [];
          if (error || resultados.length === 0) {
            definirEstadoParcelas("inicial");
          }
        },
        // (error, data) -- `data` é `{ merchant_account_id?, payer_costs: [...] }`
        // (mercadopago/sdk-js, docs/card-form.md), NUNCA um array solto. O
        // bug relatado ("parcelas não aparecem") vinha deste handler
        // ignorar completamente o parâmetro de erro -- quando a consulta de
        // parcelamento falhava, nada acontecia e o campo ficava vazio para
        // sempre, sem nenhuma mensagem. Agora todo erro é sanitizado antes
        // de aparecer na tela (nunca o objeto/JSON bruto do SDK), e a
        // ausência de opções (payer_costs vazio) é detectada corretamente.
        onInstallmentsReceived: (error, data) => {
          if (error) {
            console.error("[MercadoPago] onInstallmentsReceived retornou erro:", sanitizarErroParaLog(error));
            definirEstadoParcelas("erro");
            return;
          }
          const opcoes = data && Array.isArray(data.payer_costs) ? data.payer_costs : [];
          if (opcoes.length === 0) {
            definirEstadoParcelas("vazio");
            return;
          }
          // As <option> reais já foram inseridas pelo próprio SDK no
          // <select id="mpInstallments"> (fluxo oficial do CardForm) --
          // aqui só removemos o placeholder e liberamos o campo.
          definirEstadoParcelas("opcoes");
        },
        // Callback genérica de erro do CardForm (ex.: falha ao consultar
        // métodos/emissores) -- sem handler, esses erros do SDK ficavam
        // silenciosos ou podiam vazar como objeto bruto em outro ponto.
        onError: (error) => {
          console.error("[MercadoPago] CardForm onError:", sanitizarErroParaLog(error));
          setCardStatus(normalizarMensagemErro(error), "erro");
        },
        // Callback OFICIAL de createCardToken() (mercadopago/sdk-js,
        // docs/card-form.md: "createCardToken() ... Trigger onCardTokenReceived
        // callback"). Nunca é chamado diretamente pelo cliente -- é o único
        // jeito de saber quando o SDK terminou de gerar um token NOVO;
        // getCardFormData() sozinho não garante isso (só relê o último
        // estado interno do CardForm, que pode ser um token já consumido
        // numa tentativa anterior).
        onCardTokenReceived: (error, data) => {
          if (!resolverTokenPendente) return; // callback tardio/sem tokenização em andamento -- ignora
          const { resolve, reject } = resolverTokenPendente;
          resolverTokenPendente = null;
          if (error) reject(error);
          else resolve(data && data.token);
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

  // Solicita ao SDK um CardToken NOVO (nunca reaproveita o último token
  // criado). createCardToken() é o método oficial documentado -- entrega o
  // resultado via callback onCardTokenReceived (registrado acima); algumas
  // versões do SDK também retornam uma Promise com o mesmo resultado, então
  // honramos as duas formas com segurança (nunca resolve duas vezes).
  function solicitarNovoToken() {
    return new Promise((resolve, reject) => {
      if (resolverTokenPendente) {
        reject(new Error("Já existe uma tokenização em andamento."));
        return;
      }
      resolverTokenPendente = { resolve, reject };
      let talvezPromise;
      try {
        talvezPromise = cardForm.createCardToken();
      } catch (erro) {
        resolverTokenPendente = null;
        reject(erro);
        return;
      }
      if (talvezPromise && typeof talvezPromise.then === "function") {
        talvezPromise.then(
          (resultado) => {
            if (!resolverTokenPendente) return; // já resolvido por onCardTokenReceived
            resolverTokenPendente = null;
            resolve(resultado && resultado.token);
          },
          (erro) => {
            if (!resolverTokenPendente) return;
            resolverTokenPendente = null;
            reject(erro);
          },
        );
      }
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

  let cartaoProcessando = false;

  function definirCarregando(carregando) {
    cartaoProcessando = carregando;
    const botao = document.getElementById("mpCardSubmit");
    if (!botao) return;
    // Fase 3: mesmo depois de terminar o carregamento, o botão só volta a
    // ficar habilitado se a modalidade de recebimento continuar válida —
    // window.misticaEntrega.podeProsseguir() é a única fonte dessa checagem.
    const prontoEntrega = typeof window.misticaEntrega?.podeProsseguir !== "function" || window.misticaEntrega.podeProsseguir();
    // Endereço de cobrança (novo): retirada com cartão sempre exige os
    // campos explícitos; entrega libera assim que "usar o mesmo endereço"
    // está marcado — window.misticaEnderecoCobranca é a única fonte dessa
    // checagem (checkout-billing-address.js).
    const prontoCobranca = typeof window.misticaEnderecoCobranca?.enderecoCobrancaValido !== "function" || window.misticaEnderecoCobranca.enderecoCobrancaValido();
    // Nunca permite enviar o pagamento enquanto o seletor de parcelas ainda
    // não tem uma opção válida selecionável -- sem isso, um clique no botão
    // durante a consulta de installments enviaria installments=1 (ou
    // undefined) só porque o valor real ainda não chegou do SDK.
    const parcelasOk = !cardForm || parcelasProntas;
    botao.disabled = carregando || !prontoEntrega || !prontoCobranca || !parcelasOk;
    botao.setAttribute("aria-disabled", String(botao.disabled));
    // O valor cobrado é sempre pedidos.total_final (nunca calculado no
    // navegador) -- só aparece no botão depois que o pedido já existe
    // (pedidoAtual criado em garantirPedidoAtual/montarFormularioCartao).
    const valorTexto = pedidoAtual?.totalFinal != null ? ` ${currency(pedidoAtual.totalFinal)}` : "";
    if (carregando) {
      botao.textContent = "Processando pagamento...";
    } else if (!parcelasOk) {
      botao.textContent = "Carregando opções de parcelamento…";
    } else {
      botao.textContent = `Pagar${valorTexto} com cartão`;
    }
  }

  // Reavalia o botão de cartão quando a modalidade/endereço mudam (chamado
  // por checkout-entrega-retirada.js), sem duplicar a lógica de "carregando"
  // já controlada acima.
  function recalcularBotaoCartao() {
    definirCarregando(cartaoProcessando);
  }
  window.misticaAtualizarBotaoCartao = recalcularBotaoCartao;

  async function enviarPagamentoCartao() {
    // Trava síncrona ANTES de qualquer await: um segundo clique/Enter/evento
    // de submit que chegue enquanto esta função ainda está em andamento
    // (mesmo antes da primeira pausa assíncrona) é ignorado aqui -- nunca
    // gera uma segunda tokenização nem um segundo POST para o mesmo clique.
    if (cartaoProcessando) return;
    if (!cardForm || !pedidoAtual) return setCardStatus("Formulário de pagamento não está pronto.", "erro");
    if (typeof window.misticaEnderecoCobranca?.enderecoCobrancaValido === "function" && !window.misticaEnderecoCobranca.enderecoCobrancaValido()) {
      return setCardStatus("Preencha o endereço de cobrança do cartão para continuar.", "erro");
    }
    definirCarregando(true);
    setCardStatus("Processando pagamento com segurança pelo Mercado Pago...", "info");

    // Cada tentativa gera um CardToken NOVO pelo SDK -- nunca reaproveita
    // getCardFormData().token isolado (pode refletir uma tokenização
    // anterior já consumida). dadosFormulario só fornece o que não é o
    // token (parcelas, bandeira, emissor, CPF, e-mail); o token em si vem
    // sempre de solicitarNovoToken() logo abaixo.
    let token;
    let dadosFormulario;
    try {
      tokenEstado = TOKEN_ESTADO.TOKENIZANDO;
      token = await solicitarNovoToken();
      dadosFormulario = cardForm.getCardFormData();
    } catch {
      tokenEstado = TOKEN_ESTADO.SEM_TOKEN;
      definirCarregando(false);
      return setCardStatus("Não foi possível gerar o token do cartão. Revise os dados e tente novamente.", "erro");
    }
    if (!token) {
      tokenEstado = TOKEN_ESTADO.SEM_TOKEN;
      definirCarregando(false);
      return setCardStatus("Não foi possível gerar o token do cartão. Revise os dados e tente novamente.", "erro");
    }
    tokenEstado = TOKEN_ESTADO.TOKEN_PRONTO;

    // Nunca usa "installments = 1" como fallback silencioso para mascarar
    // um valor ausente/inválido -- só é aceito 1 parcela quando o Mercado
    // Pago de fato ofereceu (e o cliente confirmou) essa opção no seletor.
    const installmentsSelecionadas = Number(dadosFormulario.installments);
    if (!Number.isInteger(installmentsSelecionadas) || installmentsSelecionadas <= 0) {
      tokenEstado = TOKEN_ESTADO.SEM_TOKEN;
      definirCarregando(false);
      return setCardStatus("Complete os dados do cartão para consultar as parcelas.", "erro");
    }

    const pedidoId = pedidoAtual.id;
    const idempotencyKey = obterChaveTentativa(pedidoId);
    const corpo = {
      pedido_id: pedidoId,
      txid: pedidoAtual.pixTxid,
      token,
      payment_method_id: dadosFormulario.paymentMethodId,
      installments: installmentsSelecionadas,
      issuer_id: dadosFormulario.issuerId || null,
      payer: {
        email: dadosFormulario.cardholderEmail,
        documento_tipo: dadosFormulario.identificationType || "CPF",
        documento_numero: dadosFormulario.identificationNumber,
        endereco_cobranca: window.misticaEnderecoCobranca?.obterEnderecoCobranca?.(),
      },
    };

    // A partir daqui o token é CONSUMIDO -- a referência local é descartada
    // antes mesmo de a requisição terminar. Nenhum código depois deste
    // ponto tem mais acesso ao valor do token (nem em caso de sucesso, nem
    // de recusa, nem de erro de rede/timeout/parsing): uma nova tentativa
    // sempre volta ao topo desta função e passa de novo por
    // solicitarNovoToken().
    token = null;
    tokenEstado = TOKEN_ESTADO.ENVIANDO;

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
      tokenEstado = TOKEN_ESTADO.TOKEN_CONSUMIDO;
      if (!requisicao.ok) {
        // resposta.detail pode ser uma STRING (HTTPException comum do
        // backend) OU um ARRAY de objetos {loc,msg,type} quando o FastAPI
        // rejeita o corpo por validação do Pydantic (HTTP 422) -- é esse
        // segundo formato que, sem normalizar, virava "[object Object]" na
        // tela do cliente (new Error(array).message == "[object Object]").
        //
        // "codigo": "cartao_token_invalido" (HTTP 422, ver
        // backend/mercadopago_routes.py) é uma resposta FINAL e definitiva
        // do Mercado Pago -- nenhuma cobrança ocorreu, o token já enviado
        // está consumido/inválido. Libera a Idempotency-Key aqui (e só
        // aqui, dentre os casos não-2xx) para a próxima tentativa, com um
        // token novo, não colidir com o hash da tentativa anterior.
        if (resposta && resposta.codigo === "cartao_token_invalido") {
          limparChaveTentativa(pedidoId);
        }
        throw new Error(normalizarMensagemErro(resposta, "Não foi possível processar o pagamento."));
      }
    } catch (erro) {
      tokenEstado = TOKEN_ESTADO.AGUARDANDO_NOVA_TOKENIZACAO;
      definirCarregando(false);
      // Falha de rede/timeout/parsing (ou qualquer outra rejeição que não
      // seja "cartao_token_invalido", já tratada acima): NÃO limpa a chave
      // de tentativa -- uma nova tentativa (novo clique, ou reload da
      // página) reaproveita a mesma Idempotency-Key, então o Mercado Pago
      // nunca processa uma segunda cobrança para o mesmo clique. Em nenhum
      // caso o token consumido acima é reenviado -- a próxima tentativa
      // sempre gera um token novo.
      setCardStatus(normalizarMensagemErro(erro, "Falha de conexão. Verifique sua internet e tente novamente."), "erro");
      return;
    }

    // Resposta final recebida (aprovado, pendente ou recusado): a tentativa
    // terminou, uma nova tentativa (ex.: outro cartão) deve usar uma chave
    // nova.
    limparChaveTentativa(pedidoId);
    tokenEstado = TOKEN_ESTADO.AGUARDANDO_NOVA_TOKENIZACAO;
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
      window.misticaEntrega?.exibirConfirmacao?.({ id: pedidoId });
      window.clearCart?.();
      if (typeof window.misticaPagamentoCartaoAprovado === "function") {
        window.misticaPagamentoCartaoAprovado(pedidoId, resposta);
      }
      cardFormMontadoParaPedido = null;
      pedidoAtual = null;
    } else if (resposta.status === "pendente") {
      setCardStatus(
        normalizarMensagemErro(resposta.mensagem, "Pagamento em análise.") +
        ` Pedido #${pedidoId} — a análise está em andamento, não é necessário pagar novamente agora. Você será avisado assim que for confirmado.`,
        "info",
      );
      if (typeof window.misticaPagamentoCartaoPendente === "function") {
        window.misticaPagamentoCartaoPendente(pedidoId, resposta);
      }
    } else {
      // Recusado/cancelado: nunca gera pedido novo -- o cliente pode tentar
      // outro cartão ou trocar para Pix no mesmo pedido.
      setCardStatus(
        normalizarMensagemErro(resposta.mensagem, "Não foi possível aprovar o pagamento. Tente outro cartão ou use o Pix."),
        "erro",
      );
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

  window.misticaMercadoPagoCheckout = {
    alternarFormaPagamento,
    obterConfigPublica,
    // Expostas só para os testes unitários (tests/mercadopago-cardform-*.test.js)
    // -- são funções puras/estado de UI, nunca lidam com token/dados de
    // cartão/credenciais.
    normalizarMensagemErro,
    definirEstadoParcelas,
  };
})();
