(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  const intents = [
    { key: "protecao", label: "Proteção", terms: ["prote", "defesa", "olho", "energia pesada", "arruda", "sálvia", "salvia", "limpeza"] },
    { key: "limpeza", label: "Limpeza energética", terms: ["limpeza", "limpar", "defum", "banho", "erva", "incenso", "sal"] },
    { key: "presente", label: "Presente", terms: ["presente", "lembrança", "lembranca", "kit", "especial", "aniversario", "aniversário"] },
    { key: "relaxar", label: "Relaxamento", terms: ["relax", "calma", "sono", "descanso", "aroma", "lavanda", "difusor"] },
    { key: "amor", label: "Amor e harmonia", terms: ["amor", "harmonia", "casal", "rosa", "autoestima"] },
    { key: "prosperidade", label: "Prosperidade", terms: ["prosper", "dinheiro", "abund", "sucesso", "canela"] },
    { key: "cristais", label: "Cristais", terms: ["cristal", "pedra", "quartzo", "ametista", "pirita"] },
    { key: "velas", label: "Velas", terms: ["vela", "ritual", "chama", "intenção", "intencao"] },
    { key: "incensos", label: "Incensos", terms: ["incenso", "aroma", "defumação", "defumacao"] },
  ];

  const kitRecipes = {
    protecao: { title: "Kit Proteção", intro: "Para proteção e fortalecimento energético, eu sugiro uma combinação simples e forte:", slots: [{ label: "Incenso de proteção", terms: ["incenso", "arruda", "sálvia", "salvia", "prote"] }, { label: "Vela ritualística", terms: ["vela", "prote", "ritual", "branca", "preta"] }, { label: "Cristal de proteção", terms: ["cristal", "pedra", "quartzo", "turmalina", "olho"] }] },
    limpeza: { title: "Kit Limpeza Energética", intro: "Para limpar e renovar a energia do ambiente, este kit funciona muito bem:", slots: [{ label: "Defumação ou incenso", terms: ["incenso", "defum", "sálvia", "salvia", "limpeza"] }, { label: "Banho de ervas", terms: ["banho", "erva", "limpeza"] }, { label: "Vela de harmonização", terms: ["vela", "branca", "harmonia", "limpeza"] }] },
    presente: { title: "Kit Presente Místico", intro: "Para presentear com significado, eu montaria uma sugestão assim:", slots: [{ label: "Produto principal", terms: ["cristal", "pedra", "difusor", "vela", "presente"] }, { label: "Aroma especial", terms: ["incenso", "aroma", "essência", "essencia", "óleo", "oleo"] }, { label: "Complemento simbólico", terms: ["guia", "chaveiro", "pingente", "kit", "presente"] }] },
    relaxar: { title: "Kit Relaxamento", intro: "Para relaxar e deixar o ambiente mais leve, eu sugiro:", slots: [{ label: "Aroma relaxante", terms: ["lavanda", "aroma", "difusor", "essência", "essencia"] }, { label: "Incenso suave", terms: ["incenso", "calma", "relax", "sono"] }, { label: "Cristal ou vela", terms: ["ametista", "cristal", "vela", "calma"] }] },
    prosperidade: { title: "Kit Prosperidade", intro: "Para intenção de prosperidade e abundância, eu montaria:", slots: [{ label: "Elemento de prosperidade", terms: ["canela", "prosper", "abund", "dinheiro"] }, { label: "Vela de intenção", terms: ["vela", "dourada", "amarela", "prosper"] }, { label: "Cristal de abundância", terms: ["pirita", "citrino", "cristal", "pedra"] }] },
    amor: { title: "Kit Amor e Harmonia", intro: "Para amor, harmonia e autocuidado, eu sugiro:", slots: [{ label: "Aroma ou incenso", terms: ["rosa", "amor", "incenso", "aroma"] }, { label: "Vela de harmonia", terms: ["vela", "rosa", "harmonia", "amor"] }, { label: "Cristal afetivo", terms: ["quartzo rosa", "quartzo", "cristal", "amor"] }] },
  };

  function clean(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
  function money(value) { try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; } }
  async function fetchProducts() { try { const response = await fetch(`${API_BASE}/api/produtos?limite=500`); if (!response.ok) throw new Error(`API ${response.status}`); const data = await response.json(); if (!Array.isArray(data)) return []; return data.map(item => ({ id: `api-${item.id}`, apiId: item.id, codigo: item.codigo_p || String(item.id), name: item.nome || "Produto", category: item.categoria || "Produtos", description: item.descricao || "Produto da Mística Presentes.", price: Number(item.preco || 0), stock: Number(item.quantidade || 0), tag: item.selo || "", imageUrl: item.imagem_url || "", images: Array.isArray(item.imagens) ? item.imagens : [] })); } catch { return Array.isArray(products) ? products : []; } }
  function productText(product) { return clean(`${product.name} ${product.category} ${product.description} ${product.tag || ""}`); }
  function detectIntent(text) { const query = clean(text); return intents.find(intent => intent.terms.some(term => query.includes(clean(term)))) || null; }
  function scoreProduct(product, intent, query) { const text = productText(product); let score = 0; if (intent) score += intent.terms.filter(term => text.includes(clean(term))).length * 4; clean(query).split(/\s+/).filter(word => word.length > 2).forEach(word => { if (text.includes(word)) score += 1; }); if (Number(product.stock || 0) > 0) score += 2; if (product.tag) score += 1; return score; }
  function suggestProducts(list, query) { const intent = detectIntent(query); return [...list].map(product => ({ product, score: scoreProduct(product, intent, query) })).filter(row => row.score > 0).sort((a, b) => b.score - a.score).slice(0, 5).map(row => row.product); }
  function bestProductForSlot(list, slot, usedIds) { return [...list].filter(product => Number(product.stock || 0) > 0 && !usedIds.has(String(product.id))).map(product => ({ product, score: slot.terms.filter(term => productText(product).includes(clean(term))).length })).filter(row => row.score > 0).sort((a, b) => b.score - a.score || Number(a.product.price || 0) - Number(b.product.price || 0))[0]?.product || null; }
  function buildKit(list, intentKey) { const recipe = kitRecipes[intentKey]; if (!recipe) return null; const used = new Set(); const items = recipe.slots.map(slot => { const product = bestProductForSlot(list, slot, used); if (product) used.add(String(product.id)); return { slot, product }; }).filter(row => row.product); if (!items.length) return null; return { ...recipe, items, total: items.reduce((sum, row) => sum + Number(row.product.price || 0), 0) }; }
  function addIsisMessage(role, html) { const chat = document.getElementById("isisChat"); if (!chat) return; const div = document.createElement("div"); div.className = `isis-message isis-${role}`; div.innerHTML = html; chat.appendChild(div); chat.scrollTop = chat.scrollHeight; }
  function addProductToCart(product) { if (typeof addToCart !== "function") return; const local = Array.isArray(products) ? products.find(item => String(item.id) === String(product.id) || String(item.apiId) === String(product.apiId)) : null; if (!local) return alert("Produto ainda não sincronizado na vitrine. Aguarde a sincronização e tente novamente."); const input = document.getElementById(`qty-${safeId(local.id)}`); if (input) input.value = "1"; addToCart(local.id); }
  function addKitToCart(kitKey, sourceList) { const kit = buildKit(sourceList || products || [], kitKey); if (!kit) return alert("Não consegui montar este kit com estoque disponível agora."); kit.items.forEach(row => addProductToCart(row.product)); }
  function renderKit(kit, key) { if (!kit) return ""; const rows = kit.items.map(row => `<li><strong>${row.slot.label}</strong><span>${row.product.name} • ${money(row.product.price)}</span></li>`).join(""); return `<article class="isis-kit-card"><strong>${kit.title}</strong><p>${kit.intro}</p><ul>${rows}</ul><strong>Total sugerido: ${money(kit.total)}</strong><button class="btn" type="button" data-isis-add-kit="${key}">Adicionar kit ao carrinho</button></article>`; }
  function renderSuggestions(query, suggestions, kit) { if (!suggestions.length && !kit) { addIsisMessage("bot", "Não encontrei um produto exato agora. Posso te encaminhar pelo WhatsApp para a loja verificar opções disponíveis."); return; } const cards = suggestions.map(product => `<article class="isis-product-card"><strong>${product.name}</strong><span>${product.category || "Produto"} • ${money(product.price)}</span><small>${Number(product.stock || 0) > 0 ? "Disponível" : "Sob consulta"}${product.tag ? " • " + product.tag : ""}</small><p>${product.description || "Produto selecionado pela Mística Presentes."}</p><div class="isis-product-actions"><button class="btn btn-small" type="button" data-isis-add="${product.id}">Adicionar</button><a class="btn btn-small btn-ghost" href="produto.html?id=${encodeURIComponent(product.id)}">Ver página</a></div></article>`).join(""); const intent = detectIntent(query); const intro = intent ? `Encontrei sugestões para <strong>${intent.label}</strong>:` : "Encontrei estes produtos que combinam com sua busca:"; const kitHtml = intent ? renderKit(kit, intent.key) : ""; addIsisMessage("bot", `${intro}${kitHtml}<div class="isis-product-grid">${cards}</div>`); }
  async function handleQuestion(text) { addIsisMessage("user", text); const list = await fetchProducts(); const intent = detectIntent(text); const kit = intent ? buildKit(list, intent.key) : null; const suggestions = suggestProducts(list, text); window.__isisLastProducts = list; renderSuggestions(text, suggestions, kit); }

  function installForm() {
    const form = document.getElementById("isisForm");
    const input = document.getElementById("isisInput");
    if (!form || !input || form.dataset.isisCommerce === "1") return;
    form.dataset.isisCommerce = "1";
    form.addEventListener("submit", event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const value = input.value.trim();
      if (!value) return;
      input.value = "";
      handleQuestion(value);
    }, true);
  }

  function installQuickActions() { const area = document.querySelector(".quick-actions"); if (!area || document.getElementById("isisCommerceActions")) return; const wrap = document.createElement("div"); wrap.id = "isisCommerceActions"; wrap.className = "quick-actions isis-commerce-actions"; ["Kit proteção", "Kit limpeza energética", "Kit presente", "Kit relaxamento", "Kit prosperidade", "Kit amor e harmonia", "Cristais disponíveis", "Produtos em promoção"].forEach(label => { const btn = document.createElement("button"); btn.className = "btn btn-ghost"; btn.type = "button"; btn.textContent = label; btn.addEventListener("click", () => handleQuestion(label)); wrap.appendChild(btn); }); area.parentNode.appendChild(wrap); }
  function installAddButtons() { document.addEventListener("click", event => { const id = event.target?.dataset?.isisAdd; if (id) { const product = Array.isArray(products) ? products.find(item => String(item.id) === String(id)) : null; if (product) addProductToCart(product); } const kitKey = event.target?.dataset?.isisAddKit; if (kitKey) addKitToCart(kitKey, window.__isisLastProducts || []); }); }

  window.misticaIsisCommerce = { ask: handleQuestion, buildKit };
  window.addEventListener("load", () => { installForm(); installQuickActions(); installAddButtons(); setTimeout(() => { addIsisMessage("bot", "Olá, eu sou a Isis. Posso montar kits por intenção: proteção, limpeza energética, presente, relaxamento, prosperidade, amor, cristais, velas ou incensos."); }, 900); });
})();
