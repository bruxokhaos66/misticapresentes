package br.com.misticapresentes.painel.ui.home

import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
import br.com.misticapresentes.painel.testutil.FakeFeatureFlagsRepository
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `logout clears user and marks state as logged out`() = runTest {
        val store = FakeSecureSessionStore()
        val api = FakeMisticaApi()
        val authRepository = AuthRepository(api, store, PersistentCookieJar(store))
        authRepository.login("luna", "senha-correta")

        val viewModel = HomeViewModel(
            authRepository = authRepository,
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
            featureFlagsRepository = FakeFeatureFlagsRepository(),
        )

        dispatcher.scheduler.advanceUntilIdle()
        assertEquals("Vendedora Luna", viewModel.uiState.value.userName)

        viewModel.logout()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.loggedOut)
        assertEquals(1, api.logoutCalls)
    }
}
