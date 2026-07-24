package br.com.misticapresentes.painel.legacy

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.LinearLayout
import android.widget.TextView
import br.com.misticapresentes.painel.common.EnvironmentConfig
import br.com.misticapresentes.painel.security.ScreenSecurity

/**
 * Tela do painel legado: mantida apenas como transição enquanto a Central de
 * Atendimento e o dashboard nativos (PR #412+) não cobrem o que hoje só
 * existe no HTML do painel operacional. Endurecida em relação ao app antigo:
 *
 * - navega SOMENTE para os domínios da Mística configurados por ambiente
 *   (BuildConfig.LEGACY_PANEL_URL); qualquer outro link abre no navegador do
 *   sistema, nunca dentro do WebView;
 * - bloqueia esquemas file:// e content://;
 * - desabilita acesso universal a file URLs;
 * - não usa addJavascriptInterface;
 * - não sobrescreve erro de certificado (nenhum onReceivedSslError permissivo);
 * - mixed content NUNCA liberado (MIXED_CONTENT_NEVER_ALLOW);
 * - cookies do WebView são limpos ao encerrar a tela;
 * - a URL é sempre a configurada no BuildConfig do flavor (nunca digitada
 *   pelo usuário em produção/homolog). A flag ALLOW_CUSTOM_LEGACY_URL existe
 *   no BuildConfig do flavor dev para uma futura tela de configuração local;
 *   nesta PR a URL customizada ainda não tem UI própria.
 */
class LegacyPanelActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var statusText: TextView

    private val allowedHost: String by lazy { Uri.parse(EnvironmentConfig.legacyPanelUrl).host.orEmpty() }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ScreenSecurity.enable(this)

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        statusText = TextView(this).apply {
            text = "Abrindo painel operacional..."
            gravity = Gravity.CENTER
            setPadding(24, 24, 24, 24)
        }
        root.addView(statusText)

        webView = WebView(this)
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.cacheMode = WebSettings.LOAD_NO_CACHE
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.allowUniversalAccessFromFileURLs = false
        settings.allowFileAccessFromFileURLs = false

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            // Duas sobrecargas: a que recebe WebResourceRequest (API 24+) e a
            // baseada em String (deprecada, mas é a única chamada em API 23,
            // que é o minSdk deste app) — ambas aplicam a mesma política.
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                return applyPolicy(uri)
            }

            @Suppress("DEPRECATION")
            override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                return applyPolicy(Uri.parse(url))
            }

            private fun applyPolicy(uri: Uri): Boolean {
                return when (LegacyUrlPolicy.decide(uri.scheme, uri.host, allowedHost)) {
                    NavigationDecision.LoadInWebView -> false
                    NavigationDecision.Block -> true
                    NavigationDecision.OpenExternally -> {
                        runCatching { startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                        true
                    }
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                statusText.text = "Painel operacional carregado."
            }

            override fun onReceivedError(
                view: WebView,
                errorCode: Int,
                description: String?,
                failingUrl: String?,
            ) {
                statusText.text = "Falha ao conectar. Confira sua internet."
            }
        }

        root.addView(webView, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(root)

        webView.loadUrl(EnvironmentConfig.legacyPanelUrl)
    }

    override fun onDestroy() {
        // Nenhum dado de sessão do painel web fica retido além do ciclo de vida desta tela.
        CookieManager.getInstance().removeAllCookies(null)
        webView.clearCache(true)
        webView.destroy()
        super.onDestroy()
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
