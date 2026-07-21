(() => {
  "use strict";

  // Fase 3 — entrega ou retirada no checkout. Este módulo só cuida da UI:
  // coleta a escolha do cliente, calcula uma ESTIMATIVA de frete só para
  // exibição e monta os campos que mobile-sync.js envia no pedido. O valor
  // definitivo de frete/total sempre vem do backend (backend/frete.py) —
  // nunca confiar nesta estimativa para gravar ou cobrar nada.

  const API_BASE = String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const ENDERECO_LOJA = "Mística Presentes — Galeria Ody, nº 2400, sala 07, Centro, Pinhalzinho/SC";
  const PRAZO_ENTREGA = "5 a 10 dias úteis";
  const UF_VALIDAS = new Set([
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
  ]);

  const radiosContainer = document.getElementById("recebimentoPanel");
  const retiradaInfo = document.getElementById("retiradaInfo");
  const enderecoForm = document.getElementById("enderecoEntregaForm");
  const resumoBox = document.getElementById("resumoEntregaBox");
  const confirmacaoBox = document.getElementById("confirmacaoPedidoBox");
  const cepStatus = document.getElementById("cepBuscaStatus");

  const campo = {
    cep: document.getElementById("enderecoCep"),
    rua: document.getElementById("enderecoRua"),
    numero: document.getElementById("enderecoNumero"),
    complemento: document.getElementById("enderecoComplemento"),
    bairro: document.getElementById("enderecoBairro"),
    cidade: document.getElementById("enderecoCidade"),
    uf: document.getElementById("enderecoUf"),
  };
  const emailInput = document.getElementById("recebimentoEmail");
  const cepBuscarBtn = document.getElementById("buscarCepBtn");
  const validacaoEl = document.getElementById("recebimentoValidacao");

  if (!radiosContainer) return; // página sem o checkout (ex.: outra rota estática)

  const CAMPOS_ENDERECO_OBRIGATORIOS = ["cep", "rua", "numero", "bairro", "cidade", "uf"];

  function normalizarTexto(valor) {
    return String(valor || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function estimarFrete(forma, cidade, uf) {
    if (forma !== "entrega") return 0;
    const ufNorm = normalizarTexto(uf).toUpperCase();
    if (ufNorm !== "SC") return 50;
    if (normalizarTexto(cidade) === "pinhalzinho") return 0;
    return 30;
  }

  function formaAtual() {
    const marcado = radiosContainer.querySelector('[data-recebimento-radio]:checked');
    return marcado ? marcado.value : null;
  }

  // Endereço válido = mesmos campos/regras exigidos pelo backend (CEP de 8
  // dígitos, UF na lista de UFs do Brasil, demais campos não vazios) — ver
  // backend/site_stock_routes.py::VendaSiteIn. Nunca duplicar essa lista em
  // outro lugar do frontend.
  function enderecoValido() {
    const completos = CAMPOS_ENDERECO_OBRIGATORIOS.every((chave) => String(campo[chave]?.value || "").trim());
    if (!completos) return false;
    const digitosCep = String(campo.cep?.value || "").replace(/\D/g, "");
    if (digitosCep.length !== 8) return false;
    const uf = String(campo.uf?.value || "").trim().toUpperCase();
    return UF_VALIDAS.has(uf);
  }

  // Única função reutilizável que decide se o cliente já pode prosseguir
  // para o pagamento (Pix ou cartão): retirada libera sem endereço; entrega
  // exige endereço completo e válido. Nenhum outro arquivo deve reimplementar
  // esta regra — mobile-sync.js, app.js e v2-mercadopago-checkout.js sempre
  // consultam window.misticaEntrega.podeProsseguir().
  function podeProsseguir() {
    const forma = formaAtual();
    if (forma === "retirada") return true;
    if (forma === "entrega") return enderecoValido();
    return false;
  }

  function mensagemValidacaoAtual() {
    const forma = formaAtual();
    if (!forma) return "Escolha retirada ou entrega para continuar.";
    if (forma === "entrega" && !enderecoValido()) return "Preencha o endereço completo para continuar.";
    return "";
  }

  // Atualiza o estado habilitado/desabilitado de TODOS os controles que
  // criam pedido ou tentativa de pagamento (Gerar Pix, Pagar com cartão, o
  // próprio botão de trocar para a aba Cartão) e a mensagem de validação
  // visível/anunciada — chamada sempre que a modalidade ou o endereço mudam.
  function atualizarControlesPagamento() {
    const mensagem = mensagemValidacaoAtual();
    if (validacaoEl) {
      validacaoEl.hidden = !mensagem;
      if (mensagem) validacaoEl.textContent = mensagem;
    }

    // O botão "Gerar Pix" também depende do carrinho estar preenchido e do
    // estado de carregamento/já-gerado (ver app.js::updatePixPanelVisibility,
    // gerarPixEstadoAtual) — reaproveitamos aquela função em vez de
    // duplicar a lógica de disabled aqui.
    window.misticaAtualizarBotaoPix?.();
    // Mesma ideia para o botão de cartão: v2-mercadopago-checkout.js já
    // controla o estado de "processando"/duplo clique daquele botão.
    window.misticaAtualizarBotaoCartao?.();

    const toggleCartao = document.querySelector('[data-payment-method="cartao"]');
    if (toggleCartao) {
      const pronto = podeProsseguir();
      toggleCartao.disabled = !pronto;
      toggleCartao.setAttribute("aria-disabled", String(!pronto));
    }
  }

  // Chamada quando alguém tenta prosseguir (Pix ou cartão) sem modalidade
  // válida — nunca cria pedido nem tentativa de pagamento; só orienta o
  // cliente de volta para a seção de recebimento.
  function focarSecaoRecebimento() {
    atualizarControlesPagamento();
    if (validacaoEl) {
      // Força o leitor de tela a anunciar de novo mesmo que a mensagem já
      // estivesse visível (ex.: segunda tentativa sem escolher nada).
      const mensagem = validacaoEl.textContent;
      validacaoEl.textContent = "";
      window.requestAnimationFrame(() => { validacaoEl.textContent = mensagem; });
    }
    radiosContainer.scrollIntoView({ behavior: "smooth", block: "center" });
    radiosContainer.querySelector('[data-recebimento-radio]')?.focus();
  }

  function definirObrigatoriedadeEndereco(obrigatorio) {
    CAMPOS_ENDERECO_OBRIGATORIOS.forEach((chave) => {
      if (campo[chave]) campo[chave].required = obrigatorio;
    });
  }

  function alternarPainel() {
    const forma = formaAtual();
    const isEntrega = forma === "entrega";
    const isRetirada = forma === "retirada";
    if (retiradaInfo) retiradaInfo.hidden = !isRetirada;
    if (enderecoForm) enderecoForm.hidden = !isEntrega;
    definirObrigatoriedadeEndereco(isEntrega);
    if (!isEntrega) {
      Object.values(campo).forEach((el) => { if (el) el.disabled = true; });
    } else {
      Object.values(campo).forEach((el) => { if (el) el.disabled = false; });
    }
    atualizarResumo();
    atualizarControlesPagamento();
  }

  function atualizarResumo() {
    if (!resumoBox) return;
    const forma = formaAtual();
    if (!forma) {
      resumoBox.hidden = true;
      return;
    }
    const subtotal = typeof window.misticaCartTotal === "function" ? window.misticaCartTotal() : Number(document.getElementById("cartTotal")?.dataset.raw || 0);
    const subtotalNumerico = subtotal || 0;
    const cupom = window.misticaCupomEstimativa || null;
    const desconto = cupom ? Number(cupom.desconto || 0) : 0;
    const freteGratis = Boolean(cupom && cupom.freteGratis);
    const frete = freteGratis ? 0 : estimarFrete(forma, campo.cidade?.value, campo.uf?.value);
    const total = Math.max(0, subtotalNumerico - desconto) + frete;
    const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

    resumoBox.hidden = false;
    resumoBox.innerHTML = `
      <div class="resumo-entrega-linha"><span>Subtotal</span><strong>${currency.format(subtotalNumerico)}</strong></div>
      <div class="resumo-entrega-linha"><span>Desconto</span><strong>-${currency.format(desconto)}</strong></div>
      <div class="resumo-entrega-linha"><span>Frete</span><strong>${forma === "retirada" ? "Retirada grátis" : currency.format(frete)}</strong></div>
      <div class="resumo-entrega-linha resumo-entrega-total"><span>Total estimado</span><strong>${currency.format(total)}</strong></div>
      ${forma === "entrega" ? `<p class="resumo-entrega-prazo">Prazo estimado: ${PRAZO_ENTREGA} após a confirmação do pagamento.</p>` : ""}
      <p class="resumo-entrega-nota">O valor final do frete é sempre confirmado pelo servidor ao gerar o pagamento.</p>
    `;
  }

  async function buscarCep() {
    const digitos = String(campo.cep?.value || "").replace(/\D/g, "");
    if (digitos.length !== 8) {
      if (cepStatus) { cepStatus.hidden = false; cepStatus.textContent = "Digite um CEP com 8 dígitos para buscar."; }
      return;
    }
    if (cepStatus) { cepStatus.hidden = false; cepStatus.textContent = "Buscando endereço..."; }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    try {
      const resposta = await fetch(`${API_BASE}/api/cep/${digitos}`, { signal: controller.signal });
      const dados = await resposta.json().catch(() => null);
      if (!resposta.ok || !dados) {
        if (cepStatus) cepStatus.textContent = "CEP não encontrado. Preencha o endereço manualmente.";
        return;
      }
      // Preenche como sugestão editável — o cliente sempre pode revisar/
      // corrigir antes de enviar, e o servidor valida tudo de novo.
      if (campo.rua && !campo.rua.value) campo.rua.value = dados.rua || "";
      if (campo.bairro && !campo.bairro.value) campo.bairro.value = dados.bairro || "";
      if (campo.cidade) campo.cidade.value = dados.cidade || campo.cidade.value;
      if (campo.uf) campo.uf.value = dados.uf || campo.uf.value;
      if (cepStatus) cepStatus.textContent = "Endereço localizado. Confira antes de confirmar.";
      atualizarResumo();
      atualizarControlesPagamento();
    } catch {
      if (cepStatus) cepStatus.textContent = "Não foi possível consultar o CEP agora. Preencha o endereço manualmente.";
    } finally {
      clearTimeout(timeout);
    }
  }

  function obterDadosParaPedido() {
    const forma = formaAtual();
    if (!forma) return null;
    const dados = {
      forma_recebimento: forma,
      email: emailInput?.value?.trim() || undefined,
    };
    if (forma === "entrega") {
      const faltando = CAMPOS_ENDERECO_OBRIGATORIOS.filter((chave) => !String(campo[chave]?.value || "").trim());
      if (faltando.length) {
        throw new Error("Preencha CEP, rua, número, bairro, cidade e UF para entrega.");
      }
      dados.endereco_cep = campo.cep.value.trim();
      dados.endereco_rua = campo.rua.value.trim();
      dados.endereco_numero = campo.numero.value.trim();
      dados.endereco_complemento = campo.complemento?.value?.trim() || undefined;
      dados.endereco_bairro = campo.bairro.value.trim();
      dados.endereco_cidade = campo.cidade.value.trim();
      dados.endereco_uf = campo.uf.value.trim().toUpperCase();
      if (!UF_VALIDAS.has(dados.endereco_uf)) {
        throw new Error("UF inválida. Use a sigla do estado (ex.: SC).");
      }
    }
    return dados;
  }

  function exibirConfirmacao(pedido) {
    if (!confirmacaoBox) return;
    const forma = formaAtual();
    confirmacaoBox.hidden = false;
    const numero = pedido?.id ? `Pedido #${pedido.id}` : "Pedido registrado";
    if (forma === "retirada") {
      confirmacaoBox.innerHTML = `
        <p><strong>${numero}</strong> — Retirada na loja.</p>
        <p>Você será avisado quando o pedido estiver pronto para retirada na ${ENDERECO_LOJA}. Não compareça à loja antes da confirmação de que o pedido está disponível para retirada.</p>
      `;
    } else if (forma === "entrega") {
      confirmacaoBox.innerHTML = `
        <p><strong>${numero}</strong> — Entrega no endereço informado.</p>
        <p>Seu pedido será preparado para envio após a confirmação do pagamento. O prazo estimado é de ${PRAZO_ENTREGA}.</p>
      `;
    } else {
      confirmacaoBox.innerHTML = `<p><strong>${numero}</strong></p>`;
    }
  }

  radiosContainer.querySelectorAll('[data-recebimento-radio]').forEach((radio) => {
    radio.addEventListener("change", alternarPainel);
  });
  Object.values(campo).forEach((el) => el?.addEventListener("input", () => {
    atualizarResumo();
    atualizarControlesPagamento();
  }));
  cepBuscarBtn?.addEventListener("click", buscarCep);

  alternarPainel();
  atualizarControlesPagamento();

  window.misticaEntrega = {
    obterDadosParaPedido,
    atualizarResumo,
    exibirConfirmacao,
    podeProsseguir,
    atualizarControlesPagamento,
    focarSecaoRecebimento,
  };
})();
