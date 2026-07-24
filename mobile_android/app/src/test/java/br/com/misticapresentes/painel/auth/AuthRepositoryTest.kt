package br.com.misticapresentes.painel.auth

import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeMisticaApi
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AuthRepositoryTest {

    private lateinit var api: FakeMisticaApi
    private lateinit var store: FakeSecureSessionStore
    private lateinit var repository: AuthRepository

    @Before
    fun setUp() {
        api = FakeMisticaApi()
        store = FakeSecureSessionStore()
        repository = AuthRepository(api, store, PersistentCookieJar(store))
    }

    @Test
    fun `login with valid credentials updates state to LoggedIn`() = runTest {
        val result = repository.login("luna", "senha-correta")

        assertTrue(result is LoginResult.Success)
        assertTrue(repository.authState.value is AuthState.LoggedIn)
        assertEquals("luna", store.loggedInUserLogin)
    }

    @Test
    fun `login with invalid credentials returns friendly failure and does not log in`() = runTest {
        api.loginResponseCode = 401

        val result = repository.login("luna", "senha-errada")

        assertTrue(result is LoginResult.Failure)
        assertEquals("Sessão expirada. Faça login novamente.", (result as LoginResult.Failure).message)
        assertTrue(repository.authState.value !is AuthState.LoggedIn)
    }

    @Test
    fun `restoreSession without stored cookie goes to LoggedOut`() = runTest {
        repository.restoreSession()
        assertEquals(AuthState.LoggedOut, repository.authState.value)
    }

    @Test
    fun `restoreSession with valid cookie revalidates against backend and logs in`() = runTest {
        store.cookieJarState = "[]" // simula sessão local presente

        repository.restoreSession()

        assertTrue(repository.authState.value is AuthState.LoggedIn)
    }

    @Test
    fun `restoreSession with cookie rejected by backend clears local session`() = runTest {
        store.cookieJarState = "[]"
        api.meResponseCode = 401

        repository.restoreSession()

        assertEquals(AuthState.LoggedOut, repository.authState.value)
        assertEquals(1, store.clearSessionCallCount)
    }

    @Test
    fun `logout clears local session even if network call fails`() = runTest {
        repository.login("luna", "senha-correta")

        repository.logout()

        assertEquals(AuthState.LoggedOut, repository.authState.value)
        assertNull(store.cookieJarState)
        assertNull(store.loggedInUserLogin)
    }

    @Test
    fun `onSessionExpired clears local session and sets SessionExpired state`() = runTest {
        repository.login("luna", "senha-correta")

        repository.onSessionExpired()

        assertEquals(AuthState.SessionExpired, repository.authState.value)
        assertEquals(1, store.clearSessionCallCount)
    }
}
