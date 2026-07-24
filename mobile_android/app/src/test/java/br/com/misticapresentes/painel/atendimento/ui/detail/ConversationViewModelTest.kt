package br.com.misticapresentes.painel.atendimento.ui.detail

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
}
