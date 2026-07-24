package br.com.misticapresentes.painel.atendimento.ui.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.ConversationFilter
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.atendimento.sync.AttendanceSyncLoop
import br.com.misticapresentes.painel.atendimento.sync.SyncConfig
import br.com.misticapresentes.painel.atendimento.sync.SyncStatus
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.network.ApiResult
import br.com.misticapresentes.painel.notifications.AttendanceNotifier
import br.com.misticapresentes.painel.notifications.NoopAttendanceNotifier
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
    /** Estado discreto de sincronização em primeiro plano (PR #414) -- ver [SyncStatus]. */
    val syncStatus: SyncStatus = SyncStatus.IDLE,
    /** Soma de não lidas de todas as conversas da aba atual -- badge simples na lista/navegação. */
    val totalUnreadCount: Int = 0,
)

class AtendimentoListViewModel(
    private val repository: AtendimentoRepository,
    private val authRepository: AuthRepository,
    private val connectivityObserver: ConnectivityObserver,
    private val featureFlagsRepository: FeatureFlagsRepository,
    private val notifier: AttendanceNotifier = NoopAttendanceNotifier,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AtendimentoListUiState(isOnline = connectivityObserver.isOnlineNow()))
    val uiState: StateFlow<AtendimentoListUiState> = _uiState.asStateFlow()

    /** conversationId -> unreadCount da última carga, só para detectar AUMENTO (nunca decide nada sozinho, é só o gatilho de notificação local). */
    private var lastUnreadByConversationId: Map<Long, Int> = emptyMap()

    // -------- Sincronização em primeiro plano (PR #414) --------
    //
    // Mesmo desenho de ConversationViewModel: um único loop desta instância
    // (uma por navegação até a tela de lista), só ativo quando a tela está
    // visível E a flag está ligada. viewModelScope -- nunca GlobalScope.
    private val syncLoop = AttendanceSyncLoop(
        scope = viewModelScope,
        baseIntervalMs = SyncConfig.LIST_POLL_INTERVAL_MS,
        tick = ::pollTick,
    )

    private var isScreenActive = false
    private var isRealtimeSyncFlagEnabled = false

    init {
        val perfil = (authRepository.authState.value as? AuthState.LoggedIn)?.user?.perfil
        _uiState.value = _uiState.value.copy(canSeeAllTab = perfil != "vendedor")
        viewModelScope.launch {
            connectivityObserver.observe().collect { online ->
                _uiState.value = _uiState.value.copy(
                    isOnline = online,
                    syncStatus = if (!online) SyncStatus.OFFLINE else _uiState.value.syncStatus,
                )
            }
        }
        viewModelScope.launch {
            featureFlagsRepository.isEnabled(FeatureFlag.REALTIME_SYNC_ENABLED).collect { enabled ->
                isRealtimeSyncFlagEnabled = enabled
                evaluateSync()
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

    /** Chamado pela tela ao entrar em primeiro plano (ON_RESUME). */
    fun onScreenResumed() {
        isScreenActive = true
        evaluateSync()
    }

    /** Chamado quando a tela sai de primeiro plano (ON_PAUSE) ou é destruída. */
    fun onScreenPaused() {
        isScreenActive = false
        evaluateSync()
    }

    private fun evaluateSync() {
        if (isScreenActive && isRealtimeSyncFlagEnabled) {
            syncLoop.start()
        } else {
            syncLoop.stop()
        }
    }

    /** Um ciclo de polling silencioso (não mexe em isLoading/isRefreshing -- só usado pela atualização manual). */
    private suspend fun pollTick(): Boolean {
        if (!connectivityObserver.isOnlineNow()) {
            _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.OFFLINE)
            return false
        }
        _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.SYNCING)
        val filter = _uiState.value.filter
        val result = fetchForFilter(filter)
        return when (result) {
            is ApiResult.Success -> {
                applyConversations(result.data.items, resetLoadingFlags = false)
                _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.UPDATED)
                true
            }
            is ApiResult.Failure -> {
                // Sem erro repetitivo: só atualiza o indicador discreto, nunca
                // mostra diálogo/snackbar a cada ciclo de polling com falha.
                _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.FAILED)
                false
            }
        }
    }

    private suspend fun fetchForFilter(filter: ConversationFilter) = when (filter) {
        ConversationFilter.MINE -> repository.listMine(page = 1, pageSize = PAGE_SIZE)
        ConversationFilter.QUEUE -> repository.listQueue(page = 1, pageSize = PAGE_SIZE)
        ConversationFilter.ALL -> repository.listAll(page = 1, pageSize = PAGE_SIZE)
    }

    private fun applyConversations(conversations: List<Conversation>, resetLoadingFlags: Boolean) {
        detectNewUnreadAndNotify(conversations)
        _uiState.value = _uiState.value.copy(
            conversations = conversations,
            totalUnreadCount = conversations.sumOf { it.unreadCount },
            hasLoadedOnce = true,
            isLoading = if (resetLoadingFlags) false else _uiState.value.isLoading,
            isRefreshing = if (resetLoadingFlags) false else _uiState.value.isRefreshing,
        )
    }

    /**
     * Compara a contagem de não lidas desta carga com a anterior: qualquer
     * conversa cujo `unreadCount` SUBIU desde a última vez dispara uma
     * notificação local genérica (a própria [AttendanceNotifier] decide
     * suprimir se aquela conversa estiver aberta em primeiro plano). Nunca
     * dispara na primeira carga da tela (não há "anterior" para comparar
     * ainda, então tudo que já chega com não lidas não é "novo").
     */
    private fun detectNewUnreadAndNotify(conversations: List<Conversation>) {
        if (lastUnreadByConversationId.isNotEmpty() || _uiState.value.hasLoadedOnce) {
            for (conversation in conversations) {
                val previous = lastUnreadByConversationId[conversation.id] ?: conversation.unreadCount
                if (conversation.unreadCount > previous) {
                    notifier.notifyNewMessage(conversation.id)
                }
            }
        }
        lastUnreadByConversationId = conversations.associate { it.id to it.unreadCount }
    }

    /** Atualização manual (pull-to-refresh/botão) -- primeira carga e retomadas explícitas continuam aqui; o polling automático usa [pollTick]. */
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
            when (val result = fetchForFilter(filter)) {
                is ApiResult.Success -> {
                    applyConversations(result.data.items, resetLoadingFlags = true)
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
