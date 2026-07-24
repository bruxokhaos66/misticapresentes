package br.com.misticapresentes.painel.legacy

import org.junit.Assert.assertEquals
import org.junit.Test

class LegacyUrlPolicyTest {

    private val allowedHost = "misticaesotericos.com.br"

    @Test
    fun `allowed https host loads in webview`() {
        val decision = LegacyUrlPolicy.decide("https", allowedHost, allowedHost)
        assertEquals(NavigationDecision.LoadInWebView, decision)
    }

    @Test
    fun `different host opens externally`() {
        val decision = LegacyUrlPolicy.decide("https", "outrosite.com", allowedHost)
        assertEquals(NavigationDecision.OpenExternally, decision)
    }

    @Test
    fun `file scheme is always blocked`() {
        val decision = LegacyUrlPolicy.decide("file", allowedHost, allowedHost)
        assertEquals(NavigationDecision.Block, decision)
    }

    @Test
    fun `content scheme is always blocked`() {
        val decision = LegacyUrlPolicy.decide("content", allowedHost, allowedHost)
        assertEquals(NavigationDecision.Block, decision)
    }

    @Test
    fun `unknown scheme is blocked`() {
        val decision = LegacyUrlPolicy.decide("intent", allowedHost, allowedHost)
        assertEquals(NavigationDecision.Block, decision)
    }

    @Test
    fun `null host opens externally instead of loading in webview`() {
        val decision = LegacyUrlPolicy.decide("https", null, allowedHost)
        assertEquals(NavigationDecision.OpenExternally, decision)
    }
}
