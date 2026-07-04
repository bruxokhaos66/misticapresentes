package br.com.misticapresentes.painel;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;

public class MainActivity extends Activity {
    private static final String PREFS = "mistica_painel_prefs";
    private static final String KEY_URL = "server_url";
    private static final String KEY_TOKEN = "api_token";
    private static final String DEFAULT_PANEL_URL = "https://misticaesotericos.com.br/painel-operacional.html";
    private static final String OLD_PANEL_URL = "https://misticaesotericos.com.br/painel";
    private static final String DEFAULT_TOKEN = "mistica-local";

    private final int COR_FUNDO = Color.rgb(18, 16, 24);
    private final int COR_CARD = Color.rgb(30, 24, 41);
    private final int COR_CARD_2 = Color.rgb(42, 32, 55);
    private final int COR_OURO = Color.rgb(216, 181, 109);
    private final int COR_VERDE = Color.rgb(106, 190, 150);
    private final int COR_TEXTO = Color.rgb(246, 240, 223);
    private final int COR_MUTED = Color.rgb(184, 172, 148);

    private LinearLayout configContainer;
    private WebView webView;
    private EditText urlInput;
    private EditText tokenInput;
    private TextView statusText;
    private TextView chipText;
    private TextView sobreStatusText;
    private TextView versaoServidorText;
    private TextView servidorAtualText;
    private SharedPreferences prefs;
    private String ultimaUrl = "";
    private String ultimoToken = DEFAULT_TOKEN;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        corrigirConfiguracaoAntiga();
        montarTela();
        String url = prefs.getString(KEY_URL, DEFAULT_PANEL_URL);
        String token = prefs.getString(KEY_TOKEN, DEFAULT_TOKEN);
        if (url != null && !url.trim().isEmpty()) {
            abrirPainel(url, token);
        } else {
            mostrarConfig();
        }
    }

    private void corrigirConfiguracaoAntiga() {
        String atual = prefs.getString(KEY_URL, "");
        if (atual == null || atual.trim().isEmpty() || atual.contains("192.168.") || atual.contains("127.0.0.1") || atual.endsWith(":8000") || atual.equals(OLD_PANEL_URL) || atual.endsWith("/painel")) {
            prefs.edit().putString(KEY_URL, DEFAULT_PANEL_URL).putString(KEY_TOKEN, DEFAULT_TOKEN).apply();
        }
    }

    private int dp(int valor) { return (int) (valor * getResources().getDisplayMetrics().density + 0.5f); }
    private boolean urlValida(String url) { return url != null && (url.startsWith("http://") || url.startsWith("https://")); }
    private GradientDrawable fundo(int cor, float raioDp) { GradientDrawable g = new GradientDrawable(); g.setColor(cor); g.setCornerRadius(dp((int) raioDp)); return g; }
    private GradientDrawable fundoComBorda(int cor, float raioDp, int bordaCor) { GradientDrawable g = fundo(cor, raioDp); g.setStroke(dp(1), bordaCor); return g; }
    private TextView texto(String text, int sp, int color, int estilo) { TextView v = new TextView(this); v.setText(text); v.setTextSize(sp); v.setTextColor(color); v.setTypeface(Typeface.DEFAULT, estilo); v.setLineSpacing(0, 1.08f); return v; }
    private TextView label(String text, int sp, int color) { TextView v = texto(text, sp, color, Typeface.NORMAL); v.setPadding(0, dp(4), 0, dp(4)); return v; }
    private Button botao(String texto, int cor, int textoCor) { Button b = new Button(this); b.setText(texto); b.setTextColor(textoCor); b.setTextSize(14); b.setTypeface(Typeface.DEFAULT, Typeface.BOLD); b.setAllCaps(false); b.setBackground(fundo(cor, 14)); b.setPadding(dp(10), dp(8), dp(10), dp(8)); return b; }
    private EditText campo(String hint, String valor) { EditText e = new EditText(this); e.setHint(hint); e.setText(valor); e.setTextColor(Color.WHITE); e.setHintTextColor(Color.rgb(150, 140, 130)); e.setSingleLine(true); e.setTextSize(15); e.setPadding(dp(14), dp(10), dp(14), dp(10)); e.setBackground(fundoComBorda(Color.rgb(22, 18, 31), 14, Color.rgb(76, 62, 92))); return e; }
    private LinearLayout card() { LinearLayout c = new LinearLayout(this); c.setOrientation(LinearLayout.VERTICAL); c.setPadding(dp(18), dp(16), dp(18), dp(16)); c.setBackground(fundoComBorda(COR_CARD, 22, Color.argb(70, 216, 181, 109))); LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT); lp.setMargins(dp(14), dp(10), dp(14), dp(10)); c.setLayoutParams(lp); return c; }

    @SuppressLint("SetJavaScriptEnabled")
    private void montarTela() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(COR_FUNDO);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(14), dp(12), dp(14), dp(10));
        top.setBackground(fundo(COR_CARD, 0));
        LinearLayout titulos = new LinearLayout(this);
        titulos.setOrientation(LinearLayout.VERTICAL);
        titulos.addView(texto("🌙 Mística Painel", 22, COR_OURO, Typeface.BOLD));
        titulos.addView(texto("Acompanhamento operacional da loja", 12, COR_MUTED, Typeface.NORMAL));
        top.addView(titulos, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));

        Button sobreBtn = botao("Sobre", Color.rgb(61, 50, 77), COR_OURO);
        sobreBtn.setOnClickListener(v -> mostrarConfig());
        top.addView(sobreBtn, new LinearLayout.LayoutParams(dp(82), dp(46)));
        Button configBtn = botao("⚙", Color.rgb(61, 50, 77), COR_OURO);
        configBtn.setOnClickListener(v -> mostrarConfig());
        LinearLayout.LayoutParams cfgLp = new LinearLayout.LayoutParams(dp(52), dp(46)); cfgLp.setMargins(dp(8), 0, 0, 0); top.addView(configBtn, cfgLp);
        root.addView(top);

        LinearLayout statusBar = new LinearLayout(this);
        statusBar.setOrientation(LinearLayout.HORIZONTAL); statusBar.setGravity(Gravity.CENTER_VERTICAL); statusBar.setPadding(dp(14), dp(8), dp(14), dp(8)); statusBar.setBackgroundColor(Color.rgb(16, 14, 22));
        chipText = texto("CONFIG", 11, COR_OURO, Typeface.BOLD); chipText.setGravity(Gravity.CENTER); chipText.setBackground(fundoComBorda(Color.rgb(42, 32, 55), 999, Color.argb(90, 216, 181, 109))); chipText.setPadding(dp(10), dp(4), dp(10), dp(4)); statusBar.addView(chipText);
        statusText = texto("Configure o endereço do servidor da loja.", 12, COR_MUTED, Typeface.NORMAL); LinearLayout.LayoutParams stLp = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1); stLp.setMargins(dp(10), 0, 0, 0); statusBar.addView(statusText, stLp); root.addView(statusBar);

        configContainer = new LinearLayout(this); configContainer.setOrientation(LinearLayout.VERTICAL); configContainer.setBackgroundColor(COR_FUNDO);
        ScrollView scroll = new ScrollView(this); LinearLayout conteudo = new LinearLayout(this); conteudo.setOrientation(LinearLayout.VERTICAL); conteudo.setPadding(0, dp(8), 0, dp(12));
        LinearLayout hero = card(); hero.setBackground(fundoComBorda(COR_CARD_2, 24, Color.argb(100, 216, 181, 109))); hero.addView(texto("Painel operacional da loja", 23, COR_OURO, Typeface.BOLD)); hero.addView(label("Esta versão força o painel operacional, que usa a mesma regra do desktop para Vendas Hoje.", 14, COR_TEXTO)); conteudo.addView(hero);
        LinearLayout configCard = card(); configCard.addView(texto("Conectar ao servidor", 18, COR_OURO, Typeface.BOLD)); configCard.addView(label("Use o painel operacional oficial para evitar valor antigo em cache.", 13, COR_MUTED));
        urlInput = campo("https://misticaesotericos.com.br/painel-operacional.html", prefs.getString(KEY_URL, DEFAULT_PANEL_URL)); LinearLayout.LayoutParams campoLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT); campoLp.setMargins(0, dp(8), 0, dp(10)); configCard.addView(urlInput, campoLp);
        tokenInput = campo("Token da API", prefs.getString(KEY_TOKEN, DEFAULT_TOKEN)); configCard.addView(tokenInput, campoLp);
        Button abrir = botao("Salvar e abrir painel", COR_OURO, Color.rgb(30, 24, 41)); abrir.setOnClickListener(v -> salvarEAbrir()); LinearLayout.LayoutParams btnLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(50)); btnLp.setMargins(0, dp(10), 0, dp(6)); configCard.addView(abrir, btnLp);
        LinearLayout linhaBotoes = new LinearLayout(this); linhaBotoes.setOrientation(LinearLayout.HORIZONTAL);
        Button exemplo = botao("Usar operacional", Color.rgb(61, 50, 77), COR_TEXTO); exemplo.setOnClickListener(v -> { urlInput.setText(DEFAULT_PANEL_URL); tokenInput.setText(DEFAULT_TOKEN); });
        Button limpar = botao("Limpar cache", Color.rgb(92, 52, 58), Color.WHITE); limpar.setOnClickListener(v -> { if (webView != null) webView.clearCache(true); prefs.edit().putString(KEY_URL, DEFAULT_PANEL_URL).putString(KEY_TOKEN, DEFAULT_TOKEN).apply(); urlInput.setText(DEFAULT_PANEL_URL); tokenInput.setText(DEFAULT_TOKEN); atualizarInfoSobre(); Toast.makeText(this, "Cache limpo e painel operacional configurado.", Toast.LENGTH_SHORT).show(); });
        linhaBotoes.addView(exemplo, new LinearLayout.LayoutParams(0, dp(46), 1)); LinearLayout.LayoutParams limparLp = new LinearLayout.LayoutParams(0, dp(46), 1); limparLp.setMargins(dp(8), 0, 0, 0); linhaBotoes.addView(limpar, limparLp); configCard.addView(linhaBotoes); conteudo.addView(configCard);
        LinearLayout sobreCard = card(); sobreCard.setBackground(fundoComBorda(Color.rgb(26, 31, 43), 22, Color.argb(90, 106, 190, 150))); sobreCard.addView(texto("Sobre / Atualização", 19, COR_OURO, Typeface.BOLD)); sobreCard.addView(label("Versão instalada: " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")", 14, COR_TEXTO)); servidorAtualText = label("Servidor configurado: -", 14, COR_TEXTO); versaoServidorText = label("Versão disponível no servidor: painel operacional", 14, COR_MUTED); sobreStatusText = label("Esta versão força painel operacional e limpa cache da WebView.", 13, COR_MUTED); sobreCard.addView(servidorAtualText); sobreCard.addView(versaoServidorText); sobreCard.addView(sobreStatusText); Button verificar = botao("Verificar atualização", COR_VERDE, Color.rgb(18, 16, 24)); verificar.setOnClickListener(v -> verificarAtualizacao()); LinearLayout.LayoutParams verificarLp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(50)); verificarLp.setMargins(0, dp(10), 0, 0); sobreCard.addView(verificar, verificarLp); conteudo.addView(sobreCard);
        scroll.addView(conteudo); configContainer.addView(scroll, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.MATCH_PARENT)); root.addView(configContainer, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));

        webView = new WebView(this); webView.setVisibility(View.GONE); webView.setBackgroundColor(COR_FUNDO); webView.clearCache(true);
        WebSettings settings = webView.getSettings(); settings.setJavaScriptEnabled(true); settings.setDomStorageEnabled(true); settings.setDatabaseEnabled(true); settings.setLoadsImagesAutomatically(true); settings.setCacheMode(WebSettings.LOAD_NO_CACHE); settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView view, String url) { chipText.setText("ONLINE"); chipText.setTextColor(COR_VERDE); statusText.setText("Conectado ao painel operacional."); super.onPageFinished(view, url); }
            @Override public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) { chipText.setText("ERRO"); chipText.setTextColor(Color.rgb(224, 112, 112)); statusText.setText("Falha ao conectar. Confira internet ou API."); super.onReceivedError(view, errorCode, description, failingUrl); }
        });
        root.addView(webView, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1)); setContentView(root); atualizarInfoSobre();
    }

    private void atualizarInfoSobre() { if (servidorAtualText != null) { String servidor = prefs.getString(KEY_URL, DEFAULT_PANEL_URL); servidorAtualText.setText("Servidor configurado: " + (servidor == null || servidor.trim().isEmpty() ? "não configurado" : servidor)); } }
    private void verificarAtualizacao() { sobreStatusText.setText("Use o painel operacional. Atualize o APK quando houver nova versão."); versaoServidorText.setText("Versão disponível no servidor: painel operacional."); }
    private void salvarEAbrir() { String url = normalizarUrl(urlInput.getText().toString()); String token = tokenInput.getText().toString().trim(); if (url.isEmpty() || !urlValida(url)) { Toast.makeText(this, "Informe um endereço válido começando com http:// ou https://", Toast.LENGTH_LONG).show(); return; } if (token.isEmpty()) token = DEFAULT_TOKEN; prefs.edit().putString(KEY_URL, url).putString(KEY_TOKEN, token).apply(); atualizarInfoSobre(); abrirPainel(url, token); }
    private String normalizarUrl(String raw) { String url = raw == null ? "" : raw.trim(); if (url.endsWith("/")) url = url.substring(0, url.length() - 1); if (url.endsWith("/painel")) return DEFAULT_PANEL_URL; return url; }
    private String montarUrlComToken(String baseUrl, String token) { try { String separador = baseUrl.contains("?") ? "&" : "?"; String tokenEncoded = URLEncoder.encode(token == null ? "" : token, "UTF-8"); return baseUrl + separador + "app_token=" + tokenEncoded + "&_app_ts=" + System.currentTimeMillis(); } catch (Exception e) { return baseUrl; } }
    private void mostrarConfig() { configContainer.setVisibility(View.VISIBLE); webView.setVisibility(View.GONE); chipText.setText("CONFIG"); chipText.setTextColor(COR_OURO); statusText.setText(isOnline() ? "Configuração, servidor e atualização." : "Sem rede. Conecte no Wi-Fi ou internet."); atualizarInfoSobre(); }
    private void abrirPainel(String url, String token) { ultimaUrl = normalizarUrl(url); ultimoToken = token == null || token.trim().isEmpty() ? DEFAULT_TOKEN : token.trim(); configContainer.setVisibility(View.GONE); webView.setVisibility(View.VISIBLE); chipText.setText("ABRINDO"); chipText.setTextColor(COR_OURO); statusText.setText("Abrindo painel operacional atualizado..."); webView.clearCache(true); webView.loadUrl(montarUrlComToken(ultimaUrl, ultimoToken)); }
    private boolean isOnline() { try { ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE); NetworkInfo info = cm.getActiveNetworkInfo(); return info != null && info.isConnected(); } catch (Exception e) { return true; } }
    @Override public void onBackPressed() { if (webView != null && webView.getVisibility() == View.VISIBLE && webView.canGoBack()) { webView.goBack(); } else if (webView != null && webView.getVisibility() == View.VISIBLE) { mostrarConfig(); } else { super.onBackPressed(); } }
}
