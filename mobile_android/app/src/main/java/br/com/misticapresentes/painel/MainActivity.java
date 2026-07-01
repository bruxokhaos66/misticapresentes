package br.com.misticapresentes.painel;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
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
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final String PREFS = "mistica_painel_prefs";
    private static final String KEY_URL = "server_url";
    private static final String KEY_TOKEN = "api_token";

    private LinearLayout configLayout;
    private WebView webView;
    private EditText urlInput;
    private EditText tokenInput;
    private TextView statusText;
    private SharedPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        montarTela();
        String url = prefs.getString(KEY_URL, "");
        if (url != null && !url.trim().isEmpty()) {
            abrirPainel(url, prefs.getString(KEY_TOKEN, "mistica-local"));
        } else {
            mostrarConfig();
        }
    }

    private TextView label(String text, int sp, int color) {
        TextView v = new TextView(this);
        v.setText(text);
        v.setTextSize(sp);
        v.setTextColor(color);
        v.setPadding(18, 10, 18, 6);
        return v;
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void montarTela() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(18, 16, 24));

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(14, 12, 14, 10);
        top.setBackgroundColor(Color.rgb(29, 23, 39));

        TextView titulo = label("🌙 Mística Painel", 20, Color.rgb(216, 181, 109));
        LinearLayout.LayoutParams tituloParams = new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1);
        top.addView(titulo, tituloParams);

        Button configBtn = new Button(this);
        configBtn.setText("Config");
        configBtn.setOnClickListener(v -> mostrarConfig());
        top.addView(configBtn);
        root.addView(top);

        statusText = label("Configure o endereço do servidor da loja.", 13, Color.rgb(185, 173, 150));
        root.addView(statusText);

        configLayout = new LinearLayout(this);
        configLayout.setOrientation(LinearLayout.VERTICAL);
        configLayout.setPadding(18, 18, 18, 18);
        configLayout.setBackgroundColor(Color.rgb(18, 16, 24));

        TextView ajuda = label("Digite o endereço que apareceu no servidor local. Exemplo: http://192.168.1.50:8000", 14, Color.WHITE);
        configLayout.addView(ajuda);

        urlInput = new EditText(this);
        urlInput.setHint("http://IP-DO-SERVIDOR:8000");
        urlInput.setTextColor(Color.WHITE);
        urlInput.setHintTextColor(Color.rgb(150, 140, 130));
        urlInput.setSingleLine(true);
        urlInput.setText(prefs.getString(KEY_URL, "http://"));
        configLayout.addView(urlInput);

        tokenInput = new EditText(this);
        tokenInput.setHint("Token da API");
        tokenInput.setTextColor(Color.WHITE);
        tokenInput.setHintTextColor(Color.rgb(150, 140, 130));
        tokenInput.setSingleLine(true);
        tokenInput.setText(prefs.getString(KEY_TOKEN, "mistica-local"));
        configLayout.addView(tokenInput);

        Button salvar = new Button(this);
        salvar.setText("Salvar e abrir painel");
        salvar.setOnClickListener(v -> {
            String url = normalizarUrl(urlInput.getText().toString());
            String token = tokenInput.getText().toString().trim();
            if (url.isEmpty() || !url.startsWith("http")) {
                Toast.makeText(this, "Informe um endereço válido, começando com http://", Toast.LENGTH_LONG).show();
                return;
            }
            if (token.isEmpty()) token = "mistica-local";
            prefs.edit().putString(KEY_URL, url).putString(KEY_TOKEN, token).apply();
            abrirPainel(url, token);
        });
        configLayout.addView(salvar);

        Button testarLocal = new Button(this);
        testarLocal.setText("Usar teste local 127.0.0.1");
        testarLocal.setOnClickListener(v -> {
            urlInput.setText("http://127.0.0.1:8000");
            tokenInput.setText("mistica-local");
        });
        configLayout.addView(testarLocal);

        root.addView(configLayout, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(18, 16, 24));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadsImagesAutomatically(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                statusText.setText("Conectado: " + url);
                super.onPageFinished(view, url);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                statusText.setText("Falha ao conectar. Confira se o servidor está ligado e se o celular está no mesmo Wi-Fi.");
                super.onReceivedError(view, errorCode, description, failingUrl);
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
    }

    private String normalizarUrl(String raw) {
        String url = raw == null ? "" : raw.trim();
        if (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        return url;
    }

    private void mostrarConfig() {
        configLayout.setVisibility(View.VISIBLE);
        statusText.setText(isOnline() ? "Configure o servidor da loja." : "Sem rede. Conecte no Wi-Fi da loja.");
    }

    private void abrirPainel(String url, String token) {
        configLayout.setVisibility(View.GONE);
        statusText.setText("Abrindo painel...");
        String safeToken = token.replace("'", "\\'");
        webView.loadUrl(url);
        webView.postDelayed(() -> webView.evaluateJavascript("localStorage.setItem('MISTICA_API_TOKEN','" + safeToken + "');", null), 900);
    }

    private boolean isOnline() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo info = cm.getActiveNetworkInfo();
            return info != null && info.isConnected();
        } catch (Exception e) {
            return true;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
