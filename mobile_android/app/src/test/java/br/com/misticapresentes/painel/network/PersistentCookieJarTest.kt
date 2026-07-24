package br.com.misticapresentes.painel.network

import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import okhttp3.Cookie
import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PersistentCookieJarTest {

    private val url = "https://misticaesotericos.com.br/api/auth/login".toHttpUrl()

    @Test
    fun `saved cookie is returned for matching host`() {
        val store = FakeSecureSessionStore()
        val jar = PersistentCookieJar(store)

        val cookie = Cookie.Builder()
            .name("mistica_painel_sessao")
            .value("token-abc")
            .domain("misticaesotericos.com.br")
            .path("/")
            .expiresAt(System.currentTimeMillis() + 60_000)
            .httpOnly()
            .secure()
            .build()

        jar.saveFromResponse(url, listOf(cookie))

        val loaded = jar.loadForRequest(url)
        assertEquals(1, loaded.size)
        assertEquals("token-abc", loaded.first().value)
    }

    @Test
    fun `cookie persists across new jar instances backed by same store`() {
        val store = FakeSecureSessionStore()
        val firstJar = PersistentCookieJar(store)
        val cookie = Cookie.Builder()
            .name("mistica_painel_sessao")
            .value("token-xyz")
            .domain("misticaesotericos.com.br")
            .path("/")
            .expiresAt(System.currentTimeMillis() + 60_000)
            .build()
        firstJar.saveFromResponse(url, listOf(cookie))

        val secondJar = PersistentCookieJar(store)
        val loaded = secondJar.loadForRequest(url)
        assertEquals(1, loaded.size)
    }

    @Test
    fun `expired cookie is not returned`() {
        val store = FakeSecureSessionStore()
        val jar = PersistentCookieJar(store)
        val cookie = Cookie.Builder()
            .name("mistica_painel_sessao")
            .value("token-old")
            .domain("misticaesotericos.com.br")
            .path("/")
            .expiresAt(System.currentTimeMillis() - 60_000)
            .build()
        jar.saveFromResponse(url, listOf(cookie))

        assertTrue(jar.loadForRequest(url).isEmpty())
    }

    @Test
    fun `clear removes stored cookies`() {
        val store = FakeSecureSessionStore()
        val jar = PersistentCookieJar(store)
        val cookie = Cookie.Builder()
            .name("mistica_painel_sessao")
            .value("token-abc")
            .domain("misticaesotericos.com.br")
            .path("/")
            .expiresAt(System.currentTimeMillis() + 60_000)
            .build()
        jar.saveFromResponse(url, listOf(cookie))

        jar.clear()

        assertTrue(jar.loadForRequest(url).isEmpty())
        assertEquals(null, store.cookieJarState)
    }
}
