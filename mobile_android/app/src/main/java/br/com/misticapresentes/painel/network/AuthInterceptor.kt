package br.com.misticapresentes.painel.network

import okhttp3.HttpUrl
import okhttp3.Interceptor
import okhttp3.Response

private val MUTABLE_METHODS = setOf("POST", "PUT", "PATCH", "DELETE")

/**
 * Adiciona o header `Origin` nas requisições que mudam estado, para que a
 * defesa de CSRF do backend (`panel_sessions._validar_origem_csrf`, que
 * compara Origin/Referer contra uma allowlist de domínios da Mística) aceite
 * as chamadas feitas pelo app. Requisições autenticadas por cookie de sessão
 * sem esse header seriam rejeitadas com 403 pelo backend.
 *
 * Não adiciona nem loga nenhum header de autenticação aqui — o cookie de
 * sessão é responsabilidade do [PersistentCookieJar], gerenciado pelo próprio
 * OkHttp.
 */
class AuthInterceptor(private val baseUrl: HttpUrl) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val original = chain.request()
        if (original.method !in MUTABLE_METHODS) {
            return chain.proceed(original)
        }
        val request = original.newBuilder()
            .header("Origin", originOf(baseUrl))
            .build()
        return chain.proceed(request)
    }

    private fun originOf(url: HttpUrl): String {
        val defaultPort = if (url.scheme == "https") 443 else 80
        val portSuffix = if (url.port != defaultPort) ":${url.port}" else ""
        return "${url.scheme}://${url.host}$portSuffix"
    }
}

/**
 * Notificado quando qualquer resposta autenticada volta 401, para que a UI
 * possa navegar para a tela de "sessão expirada" de forma centralizada, sem
 * duplicar esse tratamento em cada ViewModel.
 */
fun interface SessionExpiredNotifier {
    fun onSessionExpired()
}

class SessionExpiryInterceptor(
    private val notifier: SessionExpiredNotifier,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val response = chain.proceed(request)
        val isLoginCall = request.url.encodedPath.endsWith("/api/auth/login")
        if (response.code == 401 && !isLoginCall) {
            notifier.onSessionExpired()
        }
        return response
    }
}
