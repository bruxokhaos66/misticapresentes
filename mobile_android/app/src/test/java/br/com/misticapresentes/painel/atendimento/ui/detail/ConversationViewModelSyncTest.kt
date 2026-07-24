package br.com.misticapresentes.painel.atendimento.ui.detail

import br.com.misticapresentes.painel.atendimento.network.dto.MessageDto
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState
import br.com.misticapresentes.painel.atendimento.sync.SyncStatus
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeAttendanceNotifier
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
import br.com.misticapresentes.painel.testutil.FakeFeatureFlagsRepository
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

/**
 * Testes da sincronização em primeiro plano de [ConversationViewModel] (PR
 * #414) -- deliberadamente num arquivo separado de [ConversationViewModelTest]
 * (que já cobre carregamento/envio/mídia/ações da PR #412/#413), para manter
 * cada arquivo focado em uma responsabilidade.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ConversationViewModelSyncTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var atendimentoApi: FakeAtendimentoApi

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        AttendanceForegroundState.resetForTest()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        AttendanceForegroundState.resetForTest()
    }

    private fun createViewModel(
        conversationId: Long = 1L,
        flags: FakeFeatureFlagsRepository = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to true)),
        connectivity: FakeConnectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
        notifier: FakeAttendanceNotifier = FakeAttendanceNotifier(),
    ) = ConversationViewModel(
        repository = AtendimentoRepository(atendimentoApi),
        conversationId = conversationId,
        featureFlagsRepository = flags,
        connectivityObserver = connectivity,
        notifier = notifier,
    )

    @Test
    fun `polling does not start until onScreenResumed is called`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(callsAfterInitialLoad, atendimentoApi.callLog.size)
    }

    @Test
    fun `polling ticks while screen is resumed and flag is on`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()

        assertTrue(atendimentoApi.callLog.size > callsAfterInitialLoad)
        assertEquals(SyncStatus.UPDATED, viewModel.uiState.value.syncStatus)
    }

    @Test
    fun `polling stops when the flag is off even if the screen is resumed`() = runTest {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.REALTIME_SYNC_ENABLED to false))
        val viewModel = createViewModel(flags = flags)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(callsAfterInitialLoad, atendimentoApi.callLog.size)
    }

    @Test
    fun `onScreenResumed marks this conversation as visible for notification suppression`() = runTest {
        val viewModel = createViewModel(conversationId = 7L)
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.onScreenResumed()
        assertTrue(AttendanceForegroundState.isConversationVisible(7L))

        viewModel.onScreenPaused()
        assertTrue(!AttendanceForegroundState.isConversationVisible(7L))
    }

    @Test
    fun `onCleared stops polling and clears the visible-conversation state`() = runTest {
        val viewModel = createViewModel(conversationId = 9L)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        assertTrue(AttendanceForegroundState.isConversationVisible(9L))

        val onClearedMethod = ConversationViewModel::class.java.getDeclaredMethod("onCleared")
        onClearedMethod.isAccessible = true
        onClearedMethod.invoke(viewModel)

        assertTrue(!AttendanceForegroundState.isConversationVisible(9L))
        val callsAfterClear = atendimentoApi.callLog.size
        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(callsAfterClear, atendimentoApi.callLog.size)
    }

    @Test
    fun `stale poll response is discarded when a newer load starts in the meantime`() = runTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        atendimentoApi.getMessagesDelayMs = 5_000
        atendimentoApi.getConversationDelayMs = 5_000
        // Dispara um ciclo de polling que vai ficar "em voo" por 5s...
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()
        // ...e antes dele responder, uma carga manual mais nova começa.
        atendimentoApi.getMessagesDelayMs = 0
        atendimentoApi.getConversationDelayMs = 0
        viewModel.load()
        dispatcher.scheduler.advanceUntilIdle()

        // O resultado final deve ser o do load() mais recente, não uma
        // sobrescrita atrasada do ciclo de polling antigo.
        assertEquals(false, viewModel.uiState.value.isLoading)
    }

    @Test
    fun `offline sets status to OFFLINE and stops calling the network`() = runTest {
        val connectivity = FakeConnectivityObserver(initiallyOnline = true)
        val viewModel = createViewModel(connectivity = connectivity)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        connectivity.setOnline(false)
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(SyncStatus.OFFLINE, viewModel.uiState.value.syncStatus)
    }

    @Test
    fun `notifies once for a new inbound message while the conversation is not visible`() = runTest {
        val notifier = FakeAttendanceNotifier()
        val viewModel = createViewModel(conversationId = 3L, notifier = notifier)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        viewModel.onScreenPaused() // sai da tela -- deixa de estar "visível", mas o polling continua ligado neste teste? Não: pausar desliga o loop.

        // Reativa o polling manualmente simulando um cenário onde a tela
        // ainda dispara o tick (ex.: WorkManager/outro caminho) enquanto o
        // atendente não está mais olhando esta conversa.
        viewModel.onScreenResumed()
        AttendanceForegroundState.clearVisibleConversation(3L) // simula "não está mais visível" no instante do tick
        atendimentoApi.messages = listOf(
            FakeAtendimentoApi.defaultMessage().copy(id = 2, direction = "inbound", textBody = "Nova mensagem"),
        )
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()

        assertTrue(notifier.notifiedConversationIds.contains(3L))
    }

    @Test
    fun `does not notify when the conversation is currently visible`() = runTest {
        val notifier = FakeAttendanceNotifier()
        val viewModel = createViewModel(conversationId = 4L, notifier = notifier)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()

        atendimentoApi.messages = listOf(
            FakeAtendimentoApi.defaultMessage().copy(id = 2, direction = "inbound", textBody = "Nova mensagem"),
        )
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()

        // A ViewModel ainda atualiza a lista de mensagens localmente, mas
        // NUNCA dispara notificação para a própria conversa que está aberta.
        assertTrue(notifier.notifiedConversationIds.isEmpty())
    }
}
