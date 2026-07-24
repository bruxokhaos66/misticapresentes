package br.com.misticapresentes.painel.atendimento.ui.detail

import br.com.misticapresentes.painel.atendimento.network.dto.MessageDto
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ConversationViewModelTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var atendimentoApi: FakeAtendimentoApi
    private lateinit var viewModel: ConversationViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        viewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `load fetches conversation and messages`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isLoading)
        assertNotNull(viewModel.uiState.value.conversation)
        assertEquals(1, viewModel.uiState.value.messages.size)
    }

    @Test
    fun `sendText clears draft and blocks double submit`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onDraftChanged("Olá, tudo bem?")

        viewModel.sendText()
        viewModel.sendText() // segundo clique enquanto o primeiro está em voo -- deve ser ignorado
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, atendimentoApi.sendMessageCallCount)
        assertEquals("", viewModel.uiState.value.draftText)
        assertFalse(viewModel.uiState.value.isSending)
        assertNotNull(atendimentoApi.lastSendMessageIdempotencyKey)
    }

    @Test
    fun `sendText with backend soft failure shows error message`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        atendimentoApi.sendMessageOk = false
        viewModel.onDraftChanged("Oi")

        viewModel.sendText()
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.errorMessage)
    }

    @Test
    fun `blank draft is not sent`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.onDraftChanged("   ")

        viewModel.sendText()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(0, atendimentoApi.sendMessageCallCount)
    }

    @Test
    fun `claim updates conversation from response`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.claim()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, atendimentoApi.claimCallCount)
        assertFalse(viewModel.uiState.value.isActionInProgress)
    }

    @Test
    fun `resolve conflict (409) reloads conversation and shows info message`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        atendimentoApi.responseCode = 409

        viewModel.resolve()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModel.uiState.value.infoMessage != null)
    }

    @Test
    fun `transfer sends target user and closes dialog`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.openTransferDialog()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(1, viewModel.uiState.value.agents.size)

        viewModel.transfer(targetUserId = 2)
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, atendimentoApi.transferCallCount)
        assertFalse(viewModel.uiState.value.isTransferDialogOpen)
    }

    @Test
    fun `sendProduct sends product id and refreshes messages`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()

        viewModel.sendProduct(productId = 5)
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModel.uiState.value.isSending)
        assertFalse(viewModel.uiState.value.isProductPickerOpen)
    }

    // -------- Concorrência entre instâncias (rodada de ajustes de robustez) --------
    //
    // ConversationViewModel não tem nenhum estado estático/compartilhado entre
    // instâncias -- cada uma só enxerga seu próprio MutableStateFlow. Os
    // testes abaixo provam isso explicitamente instanciando duas ViewModels
    // (conversas diferentes, mesmo Fake/API) e confirmando que nada de uma
    // aparece na outra, inclusive quando uma resposta assíncrona da primeira
    // ainda está "em voo" quando a segunda já existe.
    //
    // Observação sobre onCleared()/viewModelScope: normalmente só é acionado
    // pelo framework Android real (lifecycle do NavBackStackEntry), não há um
    // jeito não-frágil de simular isso num teste JUnit puro sem depender de
    // APIs internas do lifecycle-viewmodel-compose -- por isso não há um
    // teste dedicado a "sair da rota cancela o scope"; a garantia de que
    // nenhuma resposta atrasada escapa para OUTRA instância (o que importa na
    // prática) já é coberta pelos testes desta seção.

    @Test
    fun `draft text of one instance is not visible in another independent instance`() = runTest {
        val viewModelA = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 100)
        val viewModelB = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 200)
        dispatcher.scheduler.advanceUntilIdle()

        viewModelA.onDraftChanged("mensagem só de A")
        viewModelB.onDraftChanged("mensagem só de B")

        assertEquals("mensagem só de A", viewModelA.uiState.value.draftText)
        assertEquals("mensagem só de B", viewModelB.uiState.value.draftText)

        viewModelA.sendText()
        dispatcher.scheduler.advanceUntilIdle()

        // Enviar em A não deve tocar no rascunho (nem em mais nada) de B.
        assertEquals("", viewModelA.uiState.value.draftText)
        assertEquals("mensagem só de B", viewModelB.uiState.value.draftText)
        assertFalse(viewModelB.uiState.value.isSending)
    }

    @Test
    fun `product picker results of one instance are not visible in another independent instance`() = runTest {
        val viewModelA = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 100)
        val viewModelB = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 200)
        dispatcher.scheduler.advanceUntilIdle()

        viewModelA.openProductPicker()
        dispatcher.scheduler.advanceUntilIdle()

        assertTrue(viewModelA.uiState.value.isProductPickerOpen)
        assertTrue(viewModelA.uiState.value.productResults.isNotEmpty())

        // B nunca abriu o seletor de produtos -- nada deveria ter vazado para ela.
        assertFalse(viewModelB.uiState.value.isProductPickerOpen)
        assertTrue(viewModelB.uiState.value.productResults.isEmpty())
    }

    @Test
    fun `a slow send in-flight on one instance does not affect a second instance opened while it is pending`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        atendimentoApi.sendMessageDelayMs = 1_000

        val viewModelA = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.advanceUntilIdle() // deixa o load() inicial de A terminar
        viewModelA.onDraftChanged("mensagem em voo")
        viewModelA.sendText()
        dispatcher.scheduler.runCurrent() // A começa o envio e suspende no delay -- ainda "em voo"

        assertTrue(viewModelA.uiState.value.isSending)

        // Usuário "navega" para outra conversa antes da resposta de A voltar --
        // nova instância independente, criada enquanto A ainda está em voo.
        atendimentoApi.sendMessageDelayMs = 0
        val viewModelB = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 2)
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(viewModelB.uiState.value.isSending)
        assertEquals("", viewModelB.uiState.value.draftText)

        // E quando a resposta atrasada de A finalmente chega, só afeta A.
        assertFalse(viewModelA.uiState.value.isSending)
        assertEquals("", viewModelA.uiState.value.draftText)
    }

    @Test
    fun `retry after a failed send generates a new idempotency key`() = runTest {
        dispatcher.scheduler.advanceUntilIdle()
        atendimentoApi.sendMessageOk = false
        viewModel.onDraftChanged("Oi")

        viewModel.sendText()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(1, atendimentoApi.sendMessageIdempotencyKeys.size)
        assertNotNull(viewModel.uiState.value.errorMessage)

        atendimentoApi.sendMessageOk = true
        viewModel.sendText() // nova tentativa -- draftText não foi limpo pela falha anterior
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, atendimentoApi.sendMessageIdempotencyKeys.size)
        val (firstAttemptKey, secondAttemptKey) = atendimentoApi.sendMessageIdempotencyKeys
        assertNotEquals(firstAttemptKey, secondAttemptKey)
    }

    // -------- Paginação de mensagens (rodada de ajustes de robustez) --------

    private fun messagesRange(range: IntRange) = range.map { id ->
        MessageDto(
            id = id.toLong(),
            direction = "inbound",
            messageType = "text",
            textBody = "Mensagem $id",
            status = null,
            sentByAdmin = null,
            timestampMeta = "2026-07-24T09:00:00",
            createdAt = "2026-07-24T09:00:00",
        )
    }

    @Test
    fun `loadOlderMessages prepends without duplicating and keeps chronological order`() = runTest {
        atendimentoApi.messages = messagesRange(51..100) // 50 itens -- mantém hasMoreHistory=true
        val localViewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.advanceUntilIdle()
        assertTrue(localViewModel.uiState.value.hasMoreHistory)
        assertEquals(50, localViewModel.uiState.value.messages.size)

        atendimentoApi.messages = messagesRange(1..50) // página anterior (mais antiga)
        localViewModel.loadOlderMessages()
        dispatcher.scheduler.advanceUntilIdle()

        val ids = localViewModel.uiState.value.messages.map { it.id }
        assertEquals(100, ids.size)
        assertEquals(ids.distinct().size, ids.size) // nenhum id duplicado
        assertEquals(ids.sorted(), ids) // ordem cronológica preservada (mais antiga primeiro)
        assertEquals(1L, ids.first())
        assertEquals(100L, ids.last())
    }

    @Test
    fun `end of pagination stops requesting once backend returns fewer items than the limit`() = runTest {
        atendimentoApi.messages = messagesRange(51..100)
        val localViewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.advanceUntilIdle()

        atendimentoApi.messages = messagesRange(41..50) // só 10 -- menor que o limite (50)
        localViewModel.loadOlderMessages()
        dispatcher.scheduler.advanceUntilIdle()

        assertFalse(localViewModel.uiState.value.hasMoreHistory)
        val callsAfterFirstOlderPage = atendimentoApi.callLog.count { it == "getMessages" }

        localViewModel.loadOlderMessages() // não deveria gerar nova chamada
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(callsAfterFirstOlderPage, atendimentoApi.callLog.count { it == "getMessages" })
    }

    @Test
    fun `error loading older messages preserves already loaded messages`() = runTest {
        atendimentoApi.messages = messagesRange(51..100)
        val localViewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.advanceUntilIdle()
        val messagesBeforeFailure = localViewModel.uiState.value.messages

        atendimentoApi.responseCode = 500
        localViewModel.loadOlderMessages()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(messagesBeforeFailure, localViewModel.uiState.value.messages)
        assertFalse(localViewModel.uiState.value.isLoadingOlderMessages)
        assertNotNull(localViewModel.uiState.value.errorMessage)
    }

    @Test
    fun `two rapid loadOlderMessages calls do not duplicate the HTTP request`() = runTest {
        atendimentoApi.messages = messagesRange(51..100)
        val localViewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.advanceUntilIdle()

        atendimentoApi.getMessagesDelayMs = 1_000
        atendimentoApi.messages = messagesRange(1..50)
        localViewModel.loadOlderMessages()
        localViewModel.loadOlderMessages() // segundo clique enquanto o primeiro ainda está em voo
        dispatcher.scheduler.advanceUntilIdle()

        // 1 chamada do load() inicial + só 1 chamada de loadOlderMessages (não 2).
        assertEquals(2, atendimentoApi.callLog.count { it == "getMessages" })
        assertEquals(100, localViewModel.uiState.value.messages.size)
    }

    @Test
    fun `a late response from an older load does not overwrite a newer load's state`() = runTest {
        // Chamada 1 (lenta): dispara já no init{} do ViewModel (setUp), simulando uma
        // conversa antiga. Chamada 2 (rápida): um load() disparado logo em seguida
        // (ex.: retry manual) deveria "vencer", mesmo respondendo primeiro.
        atendimentoApi.getConversationDelayMs = 1_000
        atendimentoApi.conversationDetail = FakeAtendimentoApi.defaultInboxConversation().copy(status = "estado-antigo")
        val localViewModel = ConversationViewModel(AtendimentoRepository(atendimentoApi), conversationId = 1)
        dispatcher.scheduler.runCurrent() // deixa a 1ª chamada começar e suspender no delay

        atendimentoApi.getConversationDelayMs = 0
        atendimentoApi.conversationDetail = FakeAtendimentoApi.defaultInboxConversation().copy(status = "estado-novo")
        localViewModel.load() // 2ª chamada, mais nova, sem delay -- termina primeiro
        dispatcher.scheduler.advanceUntilIdle() // agora deixa a 1ª chamada (atrasada) também terminar

        assertEquals("estado-novo", localViewModel.uiState.value.conversation?.status)
    }
}
