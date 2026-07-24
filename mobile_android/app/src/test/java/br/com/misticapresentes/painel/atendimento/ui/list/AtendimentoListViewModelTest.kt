package br.com.misticapresentes.painel.atendimento.ui.list

import br.com.misticapresentes.painel.atendimento.model.ConversationFilter
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
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
class AtendimentoListViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var atendimentoApi: FakeAtendimentoApi
    private lateinit var authRepository: AuthRepository

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        val store = FakeSecureSessionStore()
        authRepository = AuthRepository(FakeMisticaApi(), store, PersistentCookieJar(store))
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private suspend fun createViewModel(): AtendimentoListViewModel {
        authRepository.login("luna", "senha-correta")
        return AtendimentoListViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            authRepository = authRepository,
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
        )
    }

    @Test
    fun `loads mine conversations by default`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(ConversationFilter.MINE, viewModel.uiState.value.filter)
        assertEquals(1, viewModel.uiState.value.conversations.size)
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `vendedor profile hides the all tab`() = runTest {
        // FakeMisticaApi.loginUsuario já tem perfil vendedor por padrão.
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.uiState.value.canSeeAllTab)
    }

    @Test
    fun `switching filter to queue calls queue endpoint`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.onFilterSelected(ConversationFilter.QUEUE)
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(ConversationFilter.QUEUE, viewModel.uiState.value.filter)
        assertEquals(1, viewModel.uiState.value.conversations.size)
    }

    @Test
    fun `error response shows friendly message`() = runTest {
        atendimentoApi.responseCode = 500
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.errorMessage != null)
        assertTrue(viewModel.uiState.value.conversations.isEmpty())
    }

    @Test
    fun `empty conversation list is exposed as empty state`() = runTest {
        atendimentoApi.myConversations = emptyList()
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.conversations.isEmpty())
        assertTrue(viewModel.uiState.value.errorMessage == null)
    }

    @Test
    fun `refresh reloads current filter`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        atendimentoApi.myConversations = emptyList()
        viewModel.refresh()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.conversations.isEmpty())
    }
}
