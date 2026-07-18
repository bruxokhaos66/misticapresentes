const API = "https://api.misticaesotericos.com.br";
const META_MES = 1500;
const VERSAO = "painel-mobile-20260704-dashboard-api";
const AUTO_REFRESH_MS = 5000;
const MIN_REFRESH_GAP_MS = 4000;
const ERROR_RETRY_MS = 6000;

let sessao = null;
let sincronizando = false;
let ultimaTentativa = 0;
let timerAtualizacao = null;
let sessaoVersao = 0; // evita que uma resposta em voo antes do logout repopule a UI depois

let logoutChannel = null;
try { logoutChannel = new BroadcastChannel("mistica-painel-logout"); logoutChannel.onmessage = () => voltarParaLogin(); } catch {}

const $ = (id) => document.getElementById(id);
const brl = (n) => (Number(n) || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const pad = (n) => String(n).padStart(2, "0");
const normalizar = (txt) => String(txt || "").trim().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");

function hojeKey(d = new Date()) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
function mesKey(d = new Date()) { return hojeKey(d).slice(0, 7); }
function brDateKey(d = new Date()) { return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`; }
function parseBrDateKey(txt) {
  const m = String(txt || "").match(/(\d{2})\/(\d{2})\/(\d{4})/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
}
function inicioDiaOperacional(agora = new Date()) {
  const ini = new Date(agora);
  if (agora.getHours() >= 23) ini.setHours(23, 0, 0, 0);
  else ini.setHours(0, 0, 0, 0);
  return ini;
}
function fimDiaOperacional(agora = new Date()) {
  const ini = inicioDiaOperacional(agora);
  const fim = new Date(ini);
  if (ini.getHours() === 23) {
    fim.setDate(fim.getDate() + 1);
    fim.setHours(23, 0, 0, 0);
  } else {
    fim.setHours(23, 0, 0, 0);
  }
  return fim;
}
function etiquetaDiaOperacional(agora = new Date()) {
  const d = new Date(agora);
  if (d.getHours() >= 23) d.setDate(d.getDate() + 1);
  return brDateKey(d);
}
function dataVenda(v) {
  const bruto = String(v.data_iso || v.data_venda || "").replace("T", " ");
  let m = bruto.match(/(\d{4})-(\d{2})-(\d{2})[ T]?(\d{2})?:?(\d{2})?/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0));
  m = bruto.match(/(\d{2})\/(\d{2})\/(\d{4})\s*(\d{2})?:?(\d{2})?/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0));
  return new Date();
}
function usuarioAtual() { return sessao && sessao.usuario ? sessao.usuario : {}; }
function isAdmin() { return ["adm", "admin", "administrador"].includes(normalizar(usuarioAtual().perfil)); }
function vendaAtiva(v) { return !["cancelado", "cancelada"].includes(normalizar(v.status || "Concluido")); }
function vendaDoUsuario(v) {
  if (isAdmin()) return true;
  const u = usuarioAtual();
  const vendedor = normalizar(v.vendedor);
  return vendedor === normalizar(u.nome) || vendedor === normalizar(u.login);
}
function comTimeout(promise, ms, nome) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${nome} demorou para responder`)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}
async function api(path, options = {}, ms = 12000) {
  const sep = path.includes("?") ? "&" : "?";
  const response = await comTimeout(fetch(`${API}${path}${sep}_=${Date.now()}`, {
    cache: "no-store",
    credentials: "include",
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  }), ms, path);
  if ((response.status === 401 || response.status === 403) && sessao && path !== "/api/auth/logout") {
    voltarParaLogin();
  }
  const text = await response.text();
  if (!response.ok) throw new Error(text || `HTTP ${response.status}`);
  try { return JSON.parse(text); } catch { return text; }
}
function voltarParaLogin() {
  sessaoVersao++;
  if (!sessao && $("painel").classList.contains("hide")) return;
  sessao = null;
  pararAtualizacaoAutomatica();
  $("painel").classList.add("hide");
  $("loginBox").classList.remove("hide");
  $("vendasList").innerHTML = "";
  $("senha").value = "";
}
async function entrar() {
  try {
    $("loginMsg").textContent = "Conectando...";
    setStatus("CONFIG", "Entrando", "Verificando login na API.");
    const res = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: $("login").value.trim(), senha: $("senha").value })
    }, 12000);
    sessao = res;
    abrirPainel();
    await sincronizar("login");
    iniciarAtualizacaoAutomatica();
  } catch (error) {
    $("loginMsg").textContent = `Falha no login/API: ${String(error.message || error).slice(0, 100)}`;
    setStatus("OFFLINE", "Sem conexao", "Nao foi possivel entrar.");
  }
}
function abrirPainel() {
  sessaoVersao++;
  const perfil = isAdmin() ? "Adm" : "Vendedor(a)";
  const nome = usuarioAtual().nome || usuarioAtual().login || perfil;
  $("loginBox").classList.add("hide");
  $("painel").classList.remove("hide");
  $("boasVindas").textContent = `Bem-vindo, ${nome}`;
  $("perfilUsuario").textContent = perfil;
  $("diaOperacional").textContent = `Dia operacional: ${etiquetaDiaOperacional()}`;
  setStatus("ONLINE", "Atualizando", "Conectado.");
}
async function sair() {
  voltarParaLogin();
  try { await api("/api/auth/logout", { method: "POST" }); } catch {}
  if (logoutChannel) { try { logoutChannel.postMessage("logout"); } catch {} }
  location.reload();
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}
function setStatus(apiTxt, freshTxt, detail) {
  $("apiPill").textContent = apiTxt;
  $("apiPill").className = `pill ${apiTxt === "ONLINE" ? "ok" : apiTxt === "OFFLINE" ? "bad" : ""}`;
  $("freshPill").textContent = freshTxt;
  $("freshPill").className = `pill ${freshTxt === "Atualizado" ? "ok" : freshTxt === "Sem conexao" ? "bad" : ""}`;
  $("netText").textContent = detail;
}
function renderVendas(vendasHoje) {
  const lista = $("vendasList");
  lista.innerHTML = "";
  if (!vendasHoje.length) {
    lista.innerHTML = '<div class="empty">Nenhuma venda do dia recebida ainda.</div>';
    return;
  }
  vendasHoje.forEach(({ venda, data }) => {
    const cliente = venda.cliente && String(venda.cliente).trim() ? venda.cliente : "Consumidor";
    const itens = Array.isArray(venda.itens) ? venda.itens : [];
    const itensHtml = itens.length
      ? itens.map((item) => `<li>${Number(item.quantidade || 0)} ${esc(item.nome_p || "produto")}</li>`).join("")
      : "<li>Itens nao enviados pela API</li>";
    const card = document.createElement("article");
    card.className = "sale";
    card.innerHTML = `
      <div class="sale-head">
        <p class="sale-title">Cliente ${esc(cliente)} comprou:</p>
        <span class="sale-time">${data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <ul class="items">${itensHtml}</ul>
      <div class="sale-foot">
        <div>Total: <span>${brl(venda.total_final)}</span></div>
        <div>Pagamento: <span>${esc(venda.forma_pagamento || "Nao informado")}</span></div>
      </div>
    `;
    lista.appendChild(card);
  });
}
function aplicarResumo(dados) {
  const falta = Number(dados.falta_meta || 0);
  const vendasDia = Array.isArray(dados.vendas_do_dia) ? dados.vendas_do_dia : [];
  $("vHoje").textContent = brl(dados.vendas_hoje);
  $("vMes").textContent = brl(dados.vendas_mes);
  $("meta").textContent = brl(dados.meta_mes);
  $("falta").textContent = dados.meta_completa ? "Meta completa" : brl(falta);
  $("faltaCard").classList.toggle("ok", Boolean(dados.meta_completa));
  $("ticketMedio").textContent = brl(dados.ticket_medio_mes || 0);
  $("produtoMaisVendido").textContent = dados.produto_mais_vendido_mes
    ? `${esc(dados.produto_mais_vendido_mes)} (${Number(dados.produto_mais_vendido_qtd || 0)} un.)`
    : "Sem vendas no mes";
  $("avaliacaoLoja").textContent = dados.avaliacoes_total
    ? `${Number(dados.avaliacoes_media || 0).toFixed(1)} de 5 (${dados.avaliacoes_total} avaliacoes)`
    : "Sem avaliacoes";
  $("diaOperacional").textContent = `Dia operacional: ${dados.dia_operacional || etiquetaDiaOperacional()}`;
  $("origemDados").textContent = `API online. Versao ${VERSAO}. Regra igual ao desktop. Vendas do dia: ${vendasDia.length}.`;
  renderVendas(vendasDia.map((venda) => ({ venda, data: dataVenda(venda) })));
}
async function sincronizar(motivo = "auto") {
  const agora = Date.now();
  if (sincronizando) return;
  if (motivo === "auto" && agora - ultimaTentativa < MIN_REFRESH_GAP_MS) return;
  sincronizando = true;
  ultimaTentativa = agora;
  const minhaVersao = sessaoVersao;
  try {
    setStatus("ONLINE", "Atualizando", "Buscando dados em segundo plano...");
    const [status, dashboard] = await Promise.all([
      api("/api/status", {}, 8000).catch(() => ({})),
      api(`/api/painel/dashboard?meta_mes=${META_MES}`, {}, 12000)
    ]);
    if (minhaVersao !== sessaoVersao) return; // logout aconteceu enquanto a resposta viajava
    aplicarResumo(dashboard);
    const hora = dashboard.ultima_atualizacao || new Date().toLocaleTimeString("pt-BR");
    $("lastUpdate").textContent = `Ultima atualização: ${hora}`;
    setStatus("ONLINE", "Atualizado", `Última atualização: ${hora}`);
    reagendar(AUTO_REFRESH_MS);
  } catch (error) {
    if (minhaVersao !== sessaoVersao) return;
    $("lastUpdate").textContent = "Ultima atualizacao: sem conexao.";
    setStatus("OFFLINE", "Sem conexao", String(error.message || error).slice(0, 130));
    reagendar(ERROR_RETRY_MS);
  } finally {
    sincronizando = false;
  }
}
function reagendar(ms) {
  if (!sessao) return;
  clearTimeout(timerAtualizacao);
  timerAtualizacao = setTimeout(() => sincronizar("auto"), ms);
}
function iniciarAtualizacaoAutomatica() {
  clearTimeout(timerAtualizacao);
  reagendar(AUTO_REFRESH_MS);
}
function pararAtualizacaoAutomatica() {
  clearTimeout(timerAtualizacao);
  timerAtualizacao = null;
  sincronizando = false;
}
$("entrarBtn")?.addEventListener("click", entrar);
$("sairBtn")?.addEventListener("click", sair);
window.addEventListener("load", async () => {
  // Fonte única da sessão: cookie HttpOnly revalidado a cada carregamento.
  // Nunca lida de localStorage/sessionStorage — apenas mantida em memória.
  try {
    localStorage.removeItem("misticaPainelSessao");
    sessionStorage.removeItem("misticaPainelSessao");
  } catch {}
  try {
    sessao = await api("/api/auth/me", { method: "GET" });
  } catch {
    sessao = null;
  }
  if (sessao?.usuario) {
    abrirPainel();
    sincronizar("load");
    iniciarAtualizacaoAutomatica();
  }
});
