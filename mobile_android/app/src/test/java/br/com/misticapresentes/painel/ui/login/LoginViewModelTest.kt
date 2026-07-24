package br.com.misticapresentes.painel.ui.login

import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeMisticaApi
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var api: FakeMisticaApi
    private lateinit var viewModel: LoginViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        api = FakeMisticaApi()
        val store = FakeSecureSessionStore()
        val repository = AuthRepository(api, store, PersistentCookieJar(store))
        viewModel = LoginViewModel(repository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `submit with empty fields shows validation error and does not call api`() = runTest {
        viewModel.submit()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals("Informe usuário e senha.", viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `successful login clears password and marks success`() = runTest {
        viewModel.onLoginChanged("luna")
        viewModel.onSenhaChanged("senha-correta")

        viewModel.submit()
        dispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertTrue(state.loginSucceeded)
        assertEquals("", state.senha)
        assertFalse(state.isLoading)
    }

    @Test
    fun `failed login shows friendly error and clears password`() = runTest {
        api.loginResponseCode = 401
        viewModel.onLoginChanged("luna")
        viewModel.onSenhaChanged("senha-errada")

        viewModel.submit()
        dispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertFalse(state.loginSucceeded)
        assertEquals("", state.senha)
        assertEquals("Sessão expirada. Faça login novamente.", state.errorMessage)
    }

    @Test
    fun `double submit while loading is ignored`() = runTest {
        viewModel.onLoginChanged("luna")
        viewModel.onSenhaChanged("senha-correta")

        viewModel.submit()
        // Segundo clique antes da corrotina do primeiro terminar: deve ser ignorado.
        viewModel.submit()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, api.loginCallCount)
    }

    @Test
    fun `toggle password visibility flips state`() {
        assertFalse(viewModel.uiState.value.isPasswordVisible)
        viewModel.onTogglePasswordVisibility()
        assertTrue(viewModel.uiState.value.isPasswordVisible)
    }
}
