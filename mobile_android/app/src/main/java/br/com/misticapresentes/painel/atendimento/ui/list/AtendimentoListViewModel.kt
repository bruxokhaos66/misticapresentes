package br.com.misticapresentes.painel.atendimento.ui.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.ConversationFilter
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.network.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

private const val PAGE_SIZE = 30

data class AtendimentoListUiState(
    val filter: ConversationFilter = ConversationFilter.MINE,
    /** Vendedor não enxerga a aba "Todas" -- o backend nega 403 para esse perfil. */
    val canSeeAllTab: Boolean = true,
    val isLoading: Boolean = false,
    val isRefreshing: Boolean = false,
    val conversations: List<Conversation> = emptyList(),
    val agentNamesById: Map<Long, String> = emptyMap(),
    val errorMessage: String? = null,
    val isOnline: Boolean = true,
    val hasLoadedOnce: Boolean = false,
)

class AtendimentoListViewModel(
    private val repository: AtendimentoRepository,
    private val authRepository: AuthRepository,
    connectivityObserver: ConnectivityObserver,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AtendimentoListUiState(isOnline = connectivityObserver.isOnlineNow()))
    val uiState: StateFlow<AtendimentoListUiState> = _uiState.asStateFlow()

    init {
        val perfil = (authRepository.authState.value as? AuthState.LoggedIn)?.user?.perfil
        _uiState.value = _uiState.value.copy(canSeeAllTab = perfil != "vendedor")
        viewModelScope.launch {
            connectivityObserver.observe().collect { online ->
                _uiState.value = _uiState.value.copy(isOnline = online)
            }
        }
        loadAgents()
        refresh()
    }

    fun onFilterSelected(filter: ConversationFilter) {
        if (filter == _uiState.value.filter) return
        _uiState.value = _uiState.value.copy(filter = filter)
        refresh()
    }

    /** Atualização manual (pull-to-refresh/botão) -- esta Central NUNCA faz polling automático. */
    fun refresh() {
        val alreadyLoading = _uiState.value.isLoading
        if (alreadyLoading) return
        val isFirstLoad = !_uiState.value.hasLoadedOnce
        _uiState.value = _uiState.value.copy(
            isLoading = isFirstLoad,
            isRefreshing = !isFirstLoad,
            errorMessage = null,
        )
        viewModelScope.launch {
            val filter = _uiState.value.filter
            val result = when (filter) {
                ConversationFilter.MINE -> repository.listMine(page = 1, pageSize = PAGE_SIZE)
                ConversationFilter.QUEUE -> repository.listQueue(page = 1, pageSize = PAGE_SIZE)
                ConversationFilter.ALL -> repository.listAll(page = 1, pageSize = PAGE_SIZE)
            }
            when (result) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        conversations = result.data.items,
                        hasLoadedOnce = true,
                    )
                }
                is ApiResult.Failure -> {
                    // 403 na aba "Todas" para um perfil sem permissão: mensagem
                    // clara em vez de deixar a lista simplesmente vazia.
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isRefreshing = false,
                        errorMessage = result.error.friendlyMessage,
                        hasLoadedOnce = true,
                    )
                }
            }
        }
    }

    private fun loadAgents() {
        viewModelScope.launch {
            when (val result = repository.listAgents()) {
                is ApiResult.Success -> {
                    _uiState.value = _uiState.value.copy(
                        agentNamesById = result.data.associate { it.id to it.nome },
                    )
                }
                is ApiResult.Failure -> {
                    // Não bloqueia a lista de conversas por causa disso (só
                    // deixa de resolver nome do responsável) -- 403 é normal
                    // para vendedor, que não acessa /agents.
                    Unit
                }
            }
        }
    }
}
