package br.com.misticapresentes.painel.atendimento.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.atendimento.model.Agent
import br.com.misticapresentes.painel.atendimento.model.AssignmentHistoryEntry
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.Message
import br.com.misticapresentes.painel.atendimento.model.Product
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.network.ApiError
import br.com.misticapresentes.painel.network.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val MESSAGES_PAGE_SIZE = 50
private const val PRODUCT_SEARCH_PAGE_SIZE = 20
private const val RECENT_PRODUCTS_LIMIT = 20
private const val ASSIGNMENT_HISTORY_PAGE_SIZE = 30

data class ConversationUiState(
    val isLoading: Boolean = false,
    val conversation: Conversation? = null,
    val messages: List<Message> = emptyList(),
    val isLoadingOlderMessages: Boolean = false,
    val hasMoreHistory: Boolean = true,
    val draftText: String = "",
    val isSending: Boolean = false,
    val errorMessage: String? = null,
    val infoMessage: String? = null,
    val isActionInProgress: Boolean = false,
    val isActionsMenuOpen: Boolean = false,
    val isTransferDialogOpen: Boolean = false,
    val agents: List<Agent> = emptyList(),
    val isProductPickerOpen: Boolean = false,
    val isProductPickerLoading: Boolean = false,
    val productResults: List<Product> = emptyList(),
    val assignmentHistory: List<AssignmentHistoryEntry> = emptyList(),
    val isAssignmentHistoryExpanded: Boolean = false,
)

/**
 * ViewModel de uma conversa. Não guarda nada em disco -- todo o histórico de
 * mensagens exibido some ao sair da tela/processo, por desenho (dado
 * sensível de cliente). Controle otimista de `assignment_version`: qualquer
 * 409 recarrega a conversa do zero e avisa o atendente, nunca tenta
 * "adivinhar" o novo estado no cliente.
 */
class ConversationViewModel(
    private val repository: AtendimentoRepository,
    private val conversationId: Long,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ConversationUiState())
    val uiState: StateFlow<ConversationUiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
        viewModelScope.launch {
            val conversationResult = repository.getConversation(conversationId)
            val messagesResult = repository.getMessages(conversationId, beforeId = null, limit = MESSAGES_PAGE_SIZE)
            when {
                conversationResult is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = conversationResult.error.friendlyMessage,
                    )
                }
                messagesResult is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = messagesResult.error.friendlyMessage,
                    )
                }
                conversationResult is ApiResult.Success && messagesResult is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        conversation = conversationResult.data,
                        messages = messagesResult.data,
                        hasMoreHistory = messagesResult.data.size >= MESSAGES_PAGE_SIZE,
                    )
                }
            }
        }
    }

    fun loadOlderMessages() {
        val state = _uiState.value
        if (state.isLoadingOlderMessages || !state.hasMoreHistory) return
        val oldestId = state.messages.firstOrNull()?.id ?: return
        _uiState.value = state.copy(isLoadingOlderMessages = true)
        viewModelScope.launch {
            when (val result = repository.getMessages(conversationId, beforeId = oldestId, limit = MESSAGES_PAGE_SIZE)) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoadingOlderMessages = false,
                        messages = result.data + _uiState.value.messages,
                        hasMoreHistory = result.data.size >= MESSAGES_PAGE_SIZE,
                    )
                }
                is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(
                        isLoadingOlderMessages = false,
                        errorMessage = result.error.friendlyMessage,
                    )
                }
            }
        }
    }

    fun onDraftChanged(text: String) {
        _uiState.value = _uiState.value.copy(draftText = text)
    }

    fun sendText() {
        val state = _uiState.value
        // Bloqueio de envio duplo: um envio em voo ignora novos toques/Enter.
        if (state.isSending) return
        val text = state.draftText.trim()
        if (text.isBlank()) return

        _uiState.value = state.copy(isSending = true, errorMessage = null)
        viewModelScope.launch {
            val result = repository.sendText(
                conversationId = conversationId,
                text = text,
                assignmentVersion = _uiState.value.conversation?.assignmentVersion,
            )
            when (result) {
                is ApiResult.Success -> {
                    if (result.data.ok) {
                        _uiState.value = _uiState.value.copy(isSending = false, draftText = "")
                        refreshMessagesQuietly()
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isSending = false,
                            errorMessage = "Não foi possível enviar a mensagem. Tente novamente.",
                        )
                    }
                }
                is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(isSending = false)
                    handleActionFailure(result.error)
                }
            }
        }
    }

    fun openProductPicker() {
        _uiState.value = _uiState.value.copy(isProductPickerOpen = true)
        loadRecentProducts()
    }

    fun closeProductPicker() {
        _uiState.value = _uiState.value.copy(isProductPickerOpen = false, productResults = emptyList())
    }

    private fun loadRecentProducts() {
        _uiState.value = _uiState.value.copy(isProductPickerLoading = true)
        viewModelScope.launch {
            when (val result = repository.recentProducts(RECENT_PRODUCTS_LIMIT)) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    isProductPickerLoading = false,
                    productResults = result.data,
                )
                is ApiResult.Failure -> _uiState.value = _uiState.value.copy(
                    isProductPickerLoading = false,
                    errorMessage = result.error.friendlyMessage,
                )
            }
        }
    }

    fun searchProducts(query: String) {
        _uiState.value = _uiState.value.copy(isProductPickerLoading = true)
        viewModelScope.launch {
            val result = if (query.isBlank()) {
                repository.recentProducts(RECENT_PRODUCTS_LIMIT)
            } else {
                repository.searchProducts(query, page = 1, pageSize = PRODUCT_SEARCH_PAGE_SIZE)
            }
            when (result) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    isProductPickerLoading = false,
                    productResults = result.data,
                )
                is ApiResult.Failure -> _uiState.value = _uiState.value.copy(
                    isProductPickerLoading = false,
                    errorMessage = result.error.friendlyMessage,
                )
            }
        }
    }

    fun sendProduct(productId: Long) {
        val state = _uiState.value
        if (state.isSending) return
        _uiState.value = state.copy(isSending = true, isProductPickerOpen = false, errorMessage = null)
        viewModelScope.launch {
            val result = repository.sendProduct(
                conversationId = conversationId,
                productId = productId,
                assignmentVersion = _uiState.value.conversation?.assignmentVersion,
            )
            when (result) {
                is ApiResult.Success -> {
                    if (result.data.ok) {
                        _uiState.value = _uiState.value.copy(isSending = false)
                        refreshMessagesQuietly()
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isSending = false,
                            errorMessage = "Não foi possível enviar o produto. Tente novamente.",
                        )
                    }
                }
                is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(isSending = false)
                    handleActionFailure(result.error)
                }
            }
        }
    }

    fun openActionsMenu() {
        _uiState.value = _uiState.value.copy(isActionsMenuOpen = true)
    }

    fun closeActionsMenu() {
        _uiState.value = _uiState.value.copy(isActionsMenuOpen = false)
    }

    fun claim() {
        runAction { repository.claim(conversationId) }
    }

    fun release(reason: String? = null) {
        runAction { repository.release(conversationId, reason) }
    }

    fun resolve() {
        runAction { repository.resolve(conversationId, _uiState.value.conversation?.assignmentVersion) }
    }

    fun openTransferDialog() {
        _uiState.value = _uiState.value.copy(isTransferDialogOpen = true, isActionsMenuOpen = false)
        viewModelScope.launch {
            when (val result = repository.listAgents()) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(agents = result.data)
                is ApiResult.Failure -> _uiState.value = _uiState.value.copy(errorMessage = result.error.friendlyMessage)
            }
        }
    }

    fun closeTransferDialog() {
        _uiState.value = _uiState.value.copy(isTransferDialogOpen = false)
    }

    fun transfer(targetUserId: Long, reason: String? = null) {
        _uiState.value = _uiState.value.copy(isTransferDialogOpen = false)
        runAction { repository.transfer(conversationId, targetUserId, reason, _uiState.value.conversation?.assignmentVersion) }
    }

    fun toggleAssignmentHistory() {
        val expanding = !_uiState.value.isAssignmentHistoryExpanded
        _uiState.value = _uiState.value.copy(isAssignmentHistoryExpanded = expanding)
        if (expanding && _uiState.value.assignmentHistory.isEmpty()) {
            viewModelScope.launch {
                when (val result = repository.assignmentHistory(conversationId, page = 1, pageSize = ASSIGNMENT_HISTORY_PAGE_SIZE)) {
                    is ApiResult.Success -> _uiState.value = _uiState.value.copy(assignmentHistory = result.data)
                    is ApiResult.Failure -> _uiState.value = _uiState.value.copy(errorMessage = result.error.friendlyMessage)
                }
            }
        }
    }

    fun dismissMessage() {
        _uiState.value = _uiState.value.copy(errorMessage = null, infoMessage = null)
    }

    private fun runAction(block: suspend () -> ApiResult<Conversation>) {
        val state = _uiState.value
        if (state.isActionInProgress) return
        _uiState.value = state.copy(isActionInProgress = true, isActionsMenuOpen = false, errorMessage = null)
        viewModelScope.launch {
            when (val result = block()) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(isActionInProgress = false, conversation = result.data)
                }
                is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(isActionInProgress = false)
                    handleActionFailure(result.error)
                }
            }
        }
    }

    /**
     * 409 (assignment_version desatualizado) recarrega a conversa inteira do
     * backend e avisa o atendente com uma mensagem clara -- nunca tenta
     * mesclar/adivinhar o novo estado no cliente (backend é a única fonte de
     * verdade do assignment_version atual).
     */
    private fun handleActionFailure(error: ApiError) {
        if (error is ApiError.Conflict) {
            _uiState.value = _uiState.value.copy(
                infoMessage = "Esta conversa foi alterada por outra ação. Recarregando...",
            )
            load()
        } else {
            _uiState.value = _uiState.value.copy(errorMessage = error.friendlyMessage)
        }
    }

    private fun refreshMessagesQuietly() {
        viewModelScope.launch {
            when (val result = repository.getMessages(conversationId, beforeId = null, limit = MESSAGES_PAGE_SIZE)) {
                is ApiResult.Success -> _uiState.value = _uiState.value.copy(
                    messages = result.data,
                    hasMoreHistory = result.data.size >= MESSAGES_PAGE_SIZE,
                )
                is ApiResult.Failure -> Unit // mensagem já foi enviada; falha aqui só afeta o refresh da lista
            }
        }
    }
}
