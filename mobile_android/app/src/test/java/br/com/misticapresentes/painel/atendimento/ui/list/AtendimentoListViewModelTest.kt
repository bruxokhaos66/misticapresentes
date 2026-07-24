package br.com.misticapresentes.painel.atendimento.ui.list

import br.com.misticapresentes.painel.atendimento.model.ConversationFilter
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.atendimento.sync.SyncStatus
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeAttendanceNotifier
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

    private suspend fun createViewModel(
        connectivityObserver: FakeConnectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
        featureFlagsRepository: FakeFeatureFlagsRepository = FakeFeatureFlagsRepository(),
        notifier: FakeAttendanceNotifier = FakeAttendanceNotifier(),
    ): AtendimentoListViewModel {
        authRepository.login("luna", "senha-correta")
        return AtendimentoListViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            authRepository = authRepository,
            connectivityObserver = connectivityObserver,
            featureFlagsRepository = featureFlagsRepository,
            notifier = notifier,
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

    // -------- Sincronização em primeiro plano (PR #414) --------

    @Test
    fun `polling is disabled when REALTIME_SYNC_ENABLED flag is off`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to false))
        val viewModel = createViewModel(featureFlagsRepository = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(120_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(callsAfterInitialLoad, atendimentoApi.callLog.size)
    }

    @Test
    fun `polling refreshes the list while screen is active and flag is on`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val viewModel = createViewModel(featureFlagsRepository = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()

        assertTrue(atendimentoApi.callLog.size > callsAfterInitialLoad)
        assertEquals(SyncStatus.UPDATED, viewModel.uiState.value.syncStatus)
    }

    @Test
    fun `polling pauses when screen goes to background and resumes after onScreenResumed`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val viewModel = createViewModel(featureFlagsRepository = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        viewModel.onScreenPaused()
        val callsWhilePaused = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(callsWhilePaused, atendimentoApi.callLog.size)

        viewModel.onScreenResumed()
        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()
        assertTrue(atendimentoApi.callLog.size > callsWhilePaused)
    }

    @Test
    fun `does not start a second polling loop on repeated onScreenResumed calls`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val viewModel = createViewModel(featureFlagsRepository = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        viewModel.onScreenResumed()
        viewModel.onScreenResumed()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()

        // Só um ciclo de polling deve ter ocorrido (uma chamada por endpoint
        // usado pelo filtro atual), nunca múltiplos loops concorrentes.
        assertEquals(callsAfterInitialLoad + 1, atendimentoApi.callLog.size)
    }

    @Test
    fun `offline sets status and network is not retried while offline`() = runTest {
        val connectivity = FakeConnectivityObserver(initiallyOnline = true)
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val viewModel = createViewModel(connectivityObserver = connectivity, featureFlagsRepository = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        connectivity.setOnline(false)
        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(SyncStatus.OFFLINE, viewModel.uiState.value.syncStatus)
    }

    @Test
    fun `notifies once when unread count increases for a conversation not currently visible`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val notifier = FakeAttendanceNotifier()
        val viewModel = createViewModel(featureFlagsRepository = flags, notifier = notifier)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        atendimentoApi.myConversations = listOf(
            FakeAtendimentoApi.defaultQueueConversation().copy(unreadCount = 5),
        )
        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(listOf(1L), notifier.notifiedConversationIds)
    }

    @Test
    fun `does not notify again when unread count stays the same across polling cycles`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true))
        val notifier = FakeAttendanceNotifier()
        val viewModel = createViewModel(featureFlagsRepository = flags, notifier = notifier)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()
        dispatcher.scheduler.advanceTimeBy(16_000)
        dispatcher.scheduler.runCurrent()

        assertTrue(notifier.notifiedConversationIds.isEmpty())
    }
}
