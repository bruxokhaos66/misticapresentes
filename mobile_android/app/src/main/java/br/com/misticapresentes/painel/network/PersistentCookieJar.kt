package br.com.misticapresentes.painel.network

import br.com.misticapresentes.painel.security.SecureSessionStore
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl

/**
 * CookieJar do OkHttp que persiste o cookie de sessão (`mistica_painel_sessao`,
 * HttpOnly/Secure/SameSite=Lax, emitido por `panel_sessions.py`) em
 * armazenamento criptografado ([SecureSessionStore]), para que a sessão
 * sobreviva ao fechamento do app — exatamente como um navegador faria, mas
 * sem nunca expor o valor do cookie em texto puro em disco.
 *
 * Não persiste cookies de terceiros nem cookies não-HttpOnly de rastreio.
 */
class PersistentCookieJar(
    private val secureSessionStore: SecureSessionStore,
) : CookieJar {

    private val json = Json { ignoreUnknownKeys = true }

    @Serializable
    private data class StoredCookie(
        val name: String,
        val value: String,
        val domain: String,
        val path: String,
        val expiresAt: Long,
        val secure: Boolean,
        val httpOnly: Boolean,
    )

    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        if (cookies.isEmpty()) return
        val merged = (loadStored() + cookies.map { it.toStoredCookie() })
            .associateBy { it.name to it.domain }
            .values
            .toList()
        persist(merged)
    }

    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        return loadStored()
            .filter { it.expiresAt > now && url.host.endsWith(it.domain) }
            .map { it.toCookie() }
    }

    /** Remove todos os cookies persistidos. Usado no logout e ao expirar a sessão. */
    fun clear() {
        secureSessionStore.cookieJarState = null
    }

    private fun loadStored(): List<StoredCookie> {
        val raw = secureSessionStore.cookieJarState ?: return emptyList()
        return runCatching { json.decodeFromString<List<StoredCookie>>(raw) }.getOrDefault(emptyList())
    }

    private fun persist(cookies: List<StoredCookie>) {
        secureSessionStore.cookieJarState = json.encodeToString(cookies)
    }

    private fun Cookie.toStoredCookie() = StoredCookie(
        name = name,
        value = value,
        domain = domain,
        path = path,
        expiresAt = expiresAt,
        secure = secure,
        httpOnly = httpOnly,
    )

    private fun StoredCookie.toCookie(): Cookie =
        Cookie.Builder()
            .name(name)
            .value(value)
            .domain(domain)
            .path(path)
            .expiresAt(expiresAt)
            .apply { if (secure) secure() }
            .apply { if (httpOnly) httpOnly() }
            .build()
}
