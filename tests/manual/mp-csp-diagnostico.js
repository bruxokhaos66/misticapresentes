"use strict";
// Script externo (não inline) de propósito: a própria CSP embutida nesta
// página proíbe script-src 'unsafe-inline', então este código teria sido
// bloqueado por ela mesma se estivesse dentro de um <script> sem src=.

// Só lê campos do próprio evento de violação de CSP -- nunca lê o DOM dos
// Secure Fields (que são iframes cross-origin do Mercado Pago e o
// navegador já impede leitura de conteúdo deles) nem qualquer valor de
// formulário. Não há caminho, neste listener, para capturar cartão/CVV/
// token/CPF/e-mail.
document.addEventListener("securitypolicyviolation", function (event) {
  var linha = document.createElement("tr");
  [
    event.effectiveDirective,
    event.blockedURI,
    event.sourceFile || "",
    event.lineNumber || "",
    event.columnNumber || "",
    event.sample || "",
  ].forEach(function (valor) {
    var td = document.createElement("td");
    td.textContent = String(valor);
    linha.appendChild(td);
  });
  document.querySelector("#violacoes tbody").appendChild(linha);
});

document.getElementById("montar").addEventListener("click", function () {
  var publicKey = document.getElementById("publicKey").value.trim();
  var status = document.getElementById("statusMontagem");
  if (!publicKey) {
    status.textContent = "Informe uma Public Key de teste antes de montar.";
    return;
  }
  status.textContent = "Carregando SDK...";

  var script = document.createElement("script");
  script.src = "https://sdk.mercadopago.com/js/v2";
  script.onload = function () {
    try {
      var mp = new window.MercadoPago(publicKey, { locale: "pt-BR", trackingDisabled: true });
      var cardForm = mp.cardForm({
        amount: "10.00",
        iframe: true,
        autoMount: true,
        form: {
          id: "form-checkout",
          cardNumber: { id: "form-checkout__cardNumber", placeholder: "Número do cartão" },
          expirationDate: { id: "form-checkout__expirationDate", placeholder: "MM/AA" },
          securityCode: { id: "form-checkout__securityCode", placeholder: "CVV" },
          cardholderName: { id: "form-checkout__cardholderName" },
          issuer: { id: "form-checkout__issuer" },
          installments: { id: "form-checkout__installments" },
          identificationType: { id: "form-checkout__identificationType" },
          identificationNumber: { id: "form-checkout__identificationNumber" },
          cardholderEmail: { id: "form-checkout__cardholderEmail" },
        },
        callbacks: {
          onFormMounted: function (error) {
            status.textContent = error ? ("onFormMounted com erro: " + error) : "CardForm montado. Rode o checklist acima.";
          },
        },
      });
      window.__cardFormDiagnostico = cardForm; // inspeção manual via DevTools, se necessário
    } catch (erro) {
      status.textContent = "Erro ao montar CardForm: " + (erro && erro.message ? erro.message : String(erro));
    }
  };
  script.onerror = function () {
    status.textContent = "Falha ao carregar o SDK (verifique acesso de rede a sdk.mercadopago.com).";
  };
  document.head.appendChild(script);
});
