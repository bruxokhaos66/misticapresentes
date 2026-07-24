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
import kotlinx.coroutines.test.TestResult
import kotlinx.coroutines.test.TestScope
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

    /**
     * Referência à(s) ViewModel(s) criada(s) pelo teste corrente, só para o
     * teardown central conseguir parar qualquer polling ainda ativo -- ver
     * [runSyncTest].
     */
    private val createdViewModels = mutableListOf<ConversationViewModel>()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        AttendanceForegroundState.resetForTest()
        createdViewModels.clear()
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
    ): ConversationViewModel {
        val viewModel = ConversationViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            conversationId = conversationId,
            featureFlagsRepository = flags,
            connectivityObserver = connectivity,
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
     * Substituto de `runTest` usado por TODOS os testes desta classe.
     *
     * Causa raiz que isto corrige (comprovada por thread dump no CI): o
     * [br.com.misticapresentes.painel.atendimento.sync.AttendanceSyncLoop] é
     * INTENCIONALMENTE infinito enquanto ativo (`while (isActive) { delay(...);
     * tick() }` -- correto em produção, onde só `viewModelScope`/`onCleared`
     * o encerra). Um teste que chama `onScreenResumed()` e não para o
     * polling antes do bloco `runTest` terminar deixa esse Job ainda ativo;
     * a própria maquinaria do `runTest` então tenta drenar o
     * `TestCoroutineScheduler` até ficar ocioso (`advanceUntilIdleOr`) antes
     * de checar por Jobs vazados -- e como o polling reagenda a si mesmo
     * para sempre, essa fila NUNCA fica vazia. O resultado não é uma
     * exceção limpa (`UncompletedCoroutinesError`), e sim um laço apertado
     * real, consumindo 100% de uma CPU para sempre (foi exatamente isso que
     * o thread dump do CI mostrou: a thread do worker de teste presa dentro
     * de `TestCoroutineScheduler.advanceUntilIdleOr`, `RUNNABLE`, consumindo
     * CPU continuamente).
     *
     * O `finally` roda DENTRO da própria coroutine do teste, antes desse
     * dreno interno do `runTest` -- por isso funciona mesmo se o corpo do
     * teste lançar uma exceção no meio (a asserção que falhou ainda dispara
     * o `finally`), e [stopAnyActivePolling] é seguro de chamar mesmo se
     * nenhuma ViewModel tiver sido criada (lista vazia) ou se o polling já
     * estiver parado (`onScreenPaused` é idempotente -- só ajusta um
     * booleano e chama `stop()`, que por sua vez tolera ser chamado sobre
     * um Job já nulo/cancelado).
     */
    private fun runSyncTest(block: suspend TestScope.() -> Unit): TestResult = runTest {
        try {
            block()
        } finally {
            stopAnyActivePolling()
        }
    }

    @Test
    fun `polling does not start until onScreenResumed is called`() = runSyncTest {
        val viewModel = createViewModel()
        dispatcher.scheduler.advanceUntilIdle()
        val callsAfterInitialLoad = atendimentoApi.callLog.size

        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()

        assertEquals(callsAfterInitialLoad, atendimentoApi.callLog.size)
    }

    @Test
    fun `polling ticks while screen is resumed and flag is on`() = runSyncTest {
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
    fun `polling stops when the flag is off even if the screen is resumed`() = runSyncTest {
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
    fun `onScreenResumed marks this conversation as visible for notification suppression`() = runSyncTest {
        val viewModel = createViewModel(conversationId = 7L)
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.onScreenResumed()
        assertTrue(AttendanceForegroundState.isConversationVisible(7L))

        viewModel.onScreenPaused()
        assertTrue(!AttendanceForegroundState.isConversationVisible(7L))
    }

    @Test
    fun `onCleared stops polling and clears the visible-conversation state`() = runSyncTest {
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
    fun `stale poll response is discarded when a newer load starts in the meantime`() = runSyncTest {
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
    fun `offline sets status to OFFLINE and stops calling the network`() = runSyncTest {
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
    fun `notifies once for a new inbound message while the conversation is not visible`() = runSyncTest {
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
    fun `does not notify when the conversation is currently visible`() = runSyncTest {
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

    /**
     * Teste de regressão para o livelock reproduzido no CI (thread dump:
     * worker de teste preso em `TestCoroutineScheduler.advanceUntilIdleOr`,
     * `RUNNABLE`, consumindo CPU continuamente, nunca completando).
     *
     * Reproduz deliberadamente o padrão que causava o travamento -- inicia o
     * polling e NÃO o para -- e prova que [stopAnyActivePolling] (o mesmo
     * helper usado pelo `finally` de [runSyncTest]) resolve: o scheduler
     * consegue ficar realmente ocioso, nenhum tick a mais acontece depois, a
     * chamada é idempotente, e uma nova ViewModel continua funcionando
     * normalmente depois. Tudo em tempo virtual (`TestCoroutineScheduler`),
     * sem sleep nem tempo real.
     */
    @Test
    fun `stopping an active polling loop left running lets the scheduler go truly idle`() = runSyncTest {
        val viewModel = createViewModel(conversationId = 99L)
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onScreenResumed()
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()
        assertTrue(AttendanceForegroundState.isConversationVisible(99L))
        val callsWhilePolling = atendimentoApi.callLog.size

        // Simula exatamente o cenário que travava o CI: o teste "esqueceu"
        // de chamar onScreenPaused()/onCleared() antes de terminar.
        stopAnyActivePolling()

        // Sem o teardown acima, ESTA chamada é onde o CI travava para
        // sempre (livelock em advanceUntilIdleOr, laço infinito reagendando
        // a si mesmo). Com o polling já cancelado, ela conclui normalmente.
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(!AttendanceForegroundState.isConversationVisible(99L))
        val callsRightAfterTeardown = atendimentoApi.callLog.size
        assertEquals(callsWhilePolling, callsRightAfterTeardown)

        // Nenhum tick a mais, mesmo avançando bastante tempo virtual.
        dispatcher.scheduler.advanceTimeBy(60_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(callsRightAfterTeardown, atendimentoApi.callLog.size)

        // Idempotente: chamar de novo não lança nem tem efeito colateral.
        stopAnyActivePolling()
        stopAnyActivePolling()

        // Uma nova instância de ViewModel funciona normalmente depois.
        val secondViewModel = createViewModel(conversationId = 100L)
        dispatcher.scheduler.advanceUntilIdle()
        secondViewModel.onScreenResumed()
        val callsAfterSecondResume = atendimentoApi.callLog.size
        dispatcher.scheduler.advanceTimeBy(9_000)
        dispatcher.scheduler.runCurrent()
        assertTrue(atendimentoApi.callLog.size > callsAfterSecondResume)
    }
}
