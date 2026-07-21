(() => {
  "use strict";

  // Endereço de cobrança do cartão (reformulação do checkout). Só ativa
  // quando "Cartão de crédito" está selecionado -- nunca é exigido para
  // Pix. Reaproveita a MESMA validação de CEP/UF do endereço de entrega
  // (window.misticaEntrega, checkout-entrega-retirada.js) e o mesmo proxy
  // de CEP no backend (backend/cep_routes.py) -- nenhuma lógica paralela.
  // Nunca persiste nada em localStorage/sessionStorage: o endereço só existe
  // em memória enquanto o cliente preenche o formulário de cartão.

  const API_BASE = String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const UF_VALIDAS = new Set([
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
  ]);
  const CAMPOS_OBRIGATORIOS = ["cep", "rua", "numero", "bairro", "cidade", "uf"];

  const bloco = document.getElementById("billingAddressBlock");
  if (!bloco) return; // página sem o checkout de cartão

  const reuseRow = document.getElementById("billingReuseRow");
  const reuseCheckbox = document.getElementById("billingReuseEntrega");
  const reuseNota = document.getElementById("billingReuseNota");
  const camposWrap = document.getElementById("billingAddressFields");
  const cepStatus = document.getElementById("billingCepStatus");
  const buscarCepBtn = document.getElementById("billingBuscarCepBtn");

  const campo = {
    cep: document.getElementById("billingCep"),
    rua: document.getElementById("billingRua"),
    numero: document.getElementById("billingNumero"),
    complemento: document.getElementById("billingComplemento"),
    bairro: document.getElementById("billingBairro"),
    cidade: document.getElementById("billingCidade"),
    uf: document.getElementById("billingUf"),
  };

  function formaRecebimentoAtual() {
    const marcado = document.querySelector('[data-recebimento-radio]:checked');
    return marcado ? marcado.value : null;
  }

  function metodoCartaoAtivo() {
    const btn = document.querySelector('[data-payment-method="cartao"]');
    return Boolean(btn && btn.classList.contains("is-active"));
  }

  function reaproveitarEntrega() {
    return formaRecebimentoAtual() === "entrega" && Boolean(reuseCheckbox && reuseCheckbox.checked);
  }

  function camposPreenchidosOk() {
    const completos = CAMPOS_OBRIGATORIOS.every((chave) => String(campo[chave]?.value || "").trim());
    if (!completos) return false;
    const digitosCep = String(campo.cep?.value || "").replace(/\D/g, "");
    if (digitosCep.length !== 8) return false;
    const uf = String(campo.uf?.value || "").trim().toUpperCase();
    return UF_VALIDAS.has(uf);
  }

  // Consultada por v2-mercadopago-checkout.js antes de habilitar/enviar o
  // pagamento com cartão -- mesma ideia de window.misticaEntrega.
  // podeProsseguir(): retirada com cartão SEMPRE exige o endereço de
  // cobrança explícito (não há endereço de entrega para reaproveitar);
  // entrega libera assim que "usar o mesmo endereço" está marcado.
  function enderecoCobrancaValido() {
    if (!metodoCartaoAtivo()) return true; // Pix nunca exige isso
    if (reaproveitarEntrega()) return true;
    return camposPreenchidosOk();
  }

  function obterEnderecoCobranca() {
    if (!metodoCartaoAtivo()) return undefined;
    if (reaproveitarEntrega()) return { usar_mesmo_da_entrega: true };
    return {
      usar_mesmo_da_entrega: false,
      cep: campo.cep.value.trim(),
      rua: campo.rua.value.trim(),
      numero: campo.numero.value.trim(),
      complemento: campo.complemento?.value?.trim() || undefined,
      bairro: campo.bairro.value.trim(),
      cidade: campo.cidade.value.trim(),
      uf: campo.uf.value.trim().toUpperCase(),
    };
  }

  function atualizarVisibilidade() {
    const ativo = metodoCartaoAtivo();
    bloco.hidden = !ativo;
    if (!ativo) return;

    const forma = formaRecebimentoAtual();
    const isEntrega = forma === "entrega";
    reuseRow.hidden = !isEntrega;
    reuseNota.hidden = isEntrega;
    const mostrarCampos = !isEntrega || !reuseCheckbox.checked;
    camposWrap.hidden = !mostrarCampos;
    CAMPOS_OBRIGATORIOS.forEach((chave) => { if (campo[chave]) campo[chave].required = mostrarCampos; });
    window.misticaAtualizarBotaoCartao?.();
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
      if (campo.rua && !campo.rua.value) campo.rua.value = dados.rua || "";
      if (campo.bairro && !campo.bairro.value) campo.bairro.value = dados.bairro || "";
      if (campo.cidade) campo.cidade.value = dados.cidade || campo.cidade.value;
      if (campo.uf) campo.uf.value = dados.uf || campo.uf.value;
      if (cepStatus) cepStatus.textContent = "Endereço localizado. Confira antes de confirmar.";
      window.misticaAtualizarBotaoCartao?.();
    } catch {
      if (cepStatus) cepStatus.textContent = "Não foi possível consultar o CEP agora. Preencha o endereço manualmente.";
    } finally {
      clearTimeout(timeout);
    }
  }

  reuseCheckbox?.addEventListener("change", atualizarVisibilidade);
  buscarCepBtn?.addEventListener("click", buscarCep);
  Object.values(campo).forEach((el) => el?.addEventListener("input", () => window.misticaAtualizarBotaoCartao?.()));
  document.querySelectorAll('[data-recebimento-radio]').forEach((radio) => radio.addEventListener("change", atualizarVisibilidade));
  document.querySelectorAll('[data-payment-method]').forEach((btn) => btn.addEventListener("click", () => {
    // O clique dispara alternarFormaPagamento (v2-mercadopago-checkout.js)
    // que só troca classes/hidden de forma síncrona -- microtask garante
    // que a leitura de is-active abaixo já reflete o método recém-clicado.
    queueMicrotask(atualizarVisibilidade);
  }));

  atualizarVisibilidade();

  window.misticaEnderecoCobranca = { obterEnderecoCobranca, enderecoCobrancaValido, atualizarVisibilidade };
})();
