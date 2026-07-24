package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.security.SecureSessionStore

/** Fake em memória de [SecureSessionStore], para testar sem o Android Keystore real. */
class FakeSecureSessionStore : SecureSessionStore {
    override var cookieJarState: String? = null
    override var loggedInUserLogin: String? = null
    override var loggedInUserProfile: String? = null

    var clearSessionCallCount = 0
        private set

    override fun hasSession(): Boolean = !cookieJarState.isNullOrBlank()

    override fun clearSession() {
        clearSessionCallCount++
        loggedInUserLogin = null
        loggedInUserProfile = null
        cookieJarState = null
    }
}
