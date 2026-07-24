package br.com.misticapresentes.painel.legacy

sealed class NavigationDecision {
    data object LoadInWebView : NavigationDecision()
    data object OpenExternally : NavigationDecision()
    data object Block : NavigationDecision()
}

/**
 * Política de navegação do WebView legado, extraída como função pura
 * (sem depender de android.webkit/android.net) para ser testável em JVM
 * puro. `file://` e `content://` são sempre bloqueados; apenas o host
 * configurado por ambiente pode navegar dentro do WebView; qualquer outro
 * http(s) abre no navegador do sistema.
 */
object LegacyUrlPolicy {

    fun decide(scheme: String?, host: String?, allowedHost: String): NavigationDecision {
        return when {
            scheme == "file" || scheme == "content" -> NavigationDecision.Block
            scheme != "http" && scheme != "https" -> NavigationDecision.Block
            host != null && host == allowedHost -> NavigationDecision.LoadInWebView
            else -> NavigationDecision.OpenExternally
        }
    }
}
