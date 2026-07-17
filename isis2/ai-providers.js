// Isis 2.0 — AI Providers.
//
// Camada de indireção para o "cérebro" da Isis. Fase 1 usa só o provedor
// "rules" (regras internas + busca por termos), que é síncrono, gratuito
// e não depende de rede — por segurança e previsibilidade. Os provedores
// "openai" e "local-llm" são placeholders arquiteturais: registram o
// contrato esperado (generate(prompt, context) -> Promise<string>) sem
// fazer nenhuma chamada de rede nem expor chaves no navegador. Ativação
// real fica para uma fase futura, com a chamada passando por um endpoint
// de backend próprio (nunca a chave de API direto no cliente).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.AIProviders) return;

  const providers = {};

  function register(name, handler) {
    providers[name] = handler;
  }

  register("rules", {
    ready: () => true,
    async generate(_prompt, context) {
      // O provedor "rules" não gera texto livre: delega ao
      // Conversation Manager, que já monta a resposta a partir do
      // catálogo real (Recommendation Engine). Existe aqui só para
      // manter o mesmo contrato dos demais provedores.
      return context?.fallbackText || "";
    },
  });

  register("openai", {
    ready: () => false,
    async generate() {
      throw new Error("Provedor OpenAI ainda não configurado nesta fase. Use o provedor 'rules'.");
    },
  });

  register("local-llm", {
    ready: () => false,
    async generate() {
      throw new Error("Provedor de modelo local ainda não configurado nesta fase. Use o provedor 'rules'.");
    },
  });

  function activeProviderName() {
    const configured = window.misticaSiteConfig?.isis2?.aiProvider;
    return configured && providers[configured]?.ready() ? configured : "rules";
  }

  function getActiveProvider() {
    return providers[activeProviderName()];
  }

  window.Isis2.AIProviders = { register, activeProviderName, getActiveProvider };
})();
