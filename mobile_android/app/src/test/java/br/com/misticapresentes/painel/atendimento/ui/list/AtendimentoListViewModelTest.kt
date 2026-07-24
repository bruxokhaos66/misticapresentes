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
import kotlinx.coroutines.test.TestResult
import kotlinx.coroutines.test.TestScope
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

    /**
     * Referência à(s) ViewModel(s) criada(s) pelo teste corrente, só para o
     * teardown central conseguir parar qualquer polling ainda ativo -- ver
     * [runSyncTest]. Mesmo padrão usado em `ConversationViewModelSyncTest`,
     * pelo mesmo motivo: [AtendimentoListViewModel] tem seu próprio
     * `AttendanceSyncLoop` (polling da lista/fila) que é INTENCIONALMENTE
     * infinito enquanto ativo, e um teste que chama `onScreenResumed()` sem
     * parar o polling antes do bloco `runTest` terminar trava o dreno
     * interno do `runTest` (`TestCoroutineScheduler.advanceUntilIdleOr`) num
     * laço apertado para sempre.
     */
    private val createdViewModels = mutableListOf<AtendimentoListViewModel>()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        val store = FakeSecureSessionStore()
        authRepository = AuthRepository(FakeMisticaApi(), store, PersistentCookieJar(store))
        createdViewModels.clear()
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
        val viewModel = AtendimentoListViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            authRepository = authRepository,
            connectivityObserver = connectivityObserver,
            featureFlagsRepository = featureFlagsRepository,
            notifier = notifier,
        )
        createdViewModels += viewModel
        return viewModel
    }

    /** Chamado no teardown central -- nunca lança, mesmo sem nenhuma ViewModel criada ainda. */
    private fun stopAnyActivePolling() {
        createdViewModels.forEach { it.onScreenPaused() }
    }

    /**
     * Substituto de `runTest` usado por TODOS os testes desta classe -- ver
     * a versão espelhada e comentada em `ConversationViewModelSyncTest` para
     * o raciocínio completo. O `finally` roda dentro da própria coroutine do
     * teste, antes do dreno interno do `runTest`, então funciona mesmo se o
     * corpo do teste falhar no meio.
     */
    private fun runSyncTest(block: suspend TestScope.() -> Unit): TestResult = runTest {
        try {
            block()
        } finally {
            stopAnyActivePolling()
        }
    }

    @Test
    fun `loads mine conversations by default`() = runSyncTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(ConversationFilter.MINE, viewModel.uiState.value.filter)
        assertEquals(1, viewModel.uiState.value.conversations.size)
        assertFalse(viewModel.uiState.value.isLoading)
    }

    @Test
    fun `vendedor profile hides the all tab`() = runSyncTest {
        // FakeMisticaApi.loginUsuario já tem perfil vendedor por padrão.
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.uiState.value.canSeeAllTab)
    }

    @Test
    fun `switching filter to queue calls queue endpoint`() = runSyncTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.onFilterSelected(ConversationFilter.QUEUE)
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(ConversationFilter.QUEUE, viewModel.uiState.value.filter)
        assertEquals(1, viewModel.uiState.value.conversations.size)
    }

    @Test
    fun `error response shows friendly message`() = runSyncTest {
        atendimentoApi.responseCode = 500
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.errorMessage != null)
        assertTrue(viewModel.uiState.value.conversations.isEmpty())
    }

    @Test
    fun `empty conversation list is exposed as empty state`() = runSyncTest {
        atendimentoApi.myConversations = emptyList()
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.conversations.isEmpty())
        assertTrue(viewModel.uiState.value.errorMessage == null)
    }

    @Test
    fun `refresh reloads current filter`() = runSyncTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()

        atendimentoApi.myConversations = emptyList()
        viewModel.refresh()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.conversations.isEmpty())
    }

    // -------- Sincronização em primeiro plano (PR #414) --------

    @Test
    fun `polling is disabled when REALTIME_SYNC_ENABLED flag is off`() = runSyncTest {
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
    fun `polling refreshes the list while screen is active and flag is on`() = runSyncTest {
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
    fun `polling pauses when screen goes to background and resumes after onScreenResumed`() = runSyncTest {
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
    fun `does not start a second polling loop on repeated onScreenResumed calls`() = runSyncTest {
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
    fun `offline sets status and network is not retried while offline`() = runSyncTest {
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
    fun `notifies once when unread count increases for a conversation not currently visible`() = runSyncTest {
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
    fun `does not notify again when unread count stays the same across polling cycles`() = runSyncTest {
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
