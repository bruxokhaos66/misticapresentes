package br.com.misticapresentes.painel.atendimento.ui.detail

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.atendimento.media.AndroidImageCompressor
import br.com.misticapresentes.painel.atendimento.media.ImageCompressor
import br.com.misticapresentes.painel.atendimento.media.MediaFileStore
import br.com.misticapresentes.painel.atendimento.media.MediaLimits
import br.com.misticapresentes.painel.atendimento.model.Agent
import br.com.misticapresentes.painel.atendimento.model.AssignmentHistoryEntry
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.MediaKind
import br.com.misticapresentes.painel.atendimento.model.Message
import br.com.misticapresentes.painel.atendimento.model.Product
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState
import br.com.misticapresentes.painel.atendimento.sync.AttendanceSyncLoop
import br.com.misticapresentes.painel.atendimento.sync.SyncConfig
import br.com.misticapresentes.painel.atendimento.sync.SyncStatus
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.network.ApiError
import br.com.misticapresentes.painel.network.ApiResult
import br.com.misticapresentes.painel.notifications.AttendanceNotifier
import br.com.misticapresentes.painel.notifications.NoopAttendanceNotifier
import java.io.File
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

private const val MESSAGES_PAGE_SIZE = 50

/**
 * Repositório de flags "sempre desligado", usado só como valor padrão do
 * construtor (mesmo padrão de [InertMediaFileStore]) -- em produção
 * [ConversationViewModelFactory] sempre injeta o real via [AppContainer].
 */
private object AlwaysDisabledFeatureFlags : FeatureFlagsRepository {
    override fun isEnabled(flag: FeatureFlag) = flowOf(false)
    override suspend fun setEnabled(flag: FeatureFlag, enabled: Boolean) = Unit
}

/** Sempre online por padrão -- mesmo padrão de valor inerte usado nos demais parâmetros opcionais desta classe. */
private object AlwaysOnlineConnectivityObserver : ConnectivityObserver {
    override fun isOnlineNow(): Boolean = true
    override fun observe() = flowOf(true)
}
private const val PRODUCT_SEARCH_PAGE_SIZE = 20
private const val RECENT_PRODUCTS_LIMIT = 20
private const val ASSIGNMENT_HISTORY_PAGE_SIZE = 30

/** Qual permissão de runtime está pendente/negada -- só CAMERA e MICROPHONE são pedidas por esta tela. */
enum class MediaPermissionType { CAMERA, MICROPHONE }

/** Imagem ou áudio já capturado/gravado/selecionado, aguardando confirmação do usuário antes do upload. */
data class PendingMedia(
    val kind: MediaKind,
    val file: File,
    val caption: String = "",
    /** Só preenchido para áudio (duração da gravação). */
    val durationMs: Long? = null,
)

data class MediaComposerUiState(
    /** Não-nulo enquanto a tela de câmera (CameraX) está aberta -- arquivo onde a foto será gravada. */
    val cameraOutputFile: File? = null,
    /** Não-nulo enquanto o bottom sheet de gravação de áudio está aberto -- arquivo onde o áudio será gravado. */
    val audioOutputFile: File? = null,
    val isRecordingAudio: Boolean = false,
    val recordingElapsedMs: Long = 0L,
    val pendingMedia: PendingMedia? = null,
    val isUploadingMedia: Boolean = false,
    val uploadProgress: Float = 0f,
    /** Pede pro usuário permitir de novo (rationale) -- ainda pode reperguntar. */
    val permissionRationale: MediaPermissionType? = null,
    /** Negada permanentemente ("Não perguntar novamente") -- só resolve indo em Configurações do app. */
    val permissionPermanentlyDenied: MediaPermissionType? = null,
)

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
    val media: MediaComposerUiState = MediaComposerUiState(),
    /** Estado discreto de sincronização em primeiro plano (PR #414) -- ver [SyncStatus]. */
    val syncStatus: SyncStatus = SyncStatus.IDLE,
    val isOnline: Boolean = true,
)

/**
 * Store de mídia inerte, usada só como valor padrão do construtor para não
 * quebrar os testes/instanciações existentes que criam `ConversationViewModel`
 * sem se importar com mídia (ver `ConversationViewModelTest`/
 * `ConversationScreenTest`, que não passam esses parâmetros). Nunca é a
 * store real usada em produção -- essa vem sempre de `AppContainer` via
 * `ConversationViewModelFactory`.
 */
private object InertMediaFileStore : MediaFileStore {
    override fun newCameraCaptureFile(): File = File.createTempFile("inert_media_camera", ".jpg")
    override fun newAudioRecordingFile(): File = File.createTempFile("inert_media_audio", ".m4a")
    override fun newCompressedImageFile(): File = File.createTempFile("inert_media_compressed", ".jpg")
    override suspend fun importFromGallery(uri: Uri): File? = null
    override fun delete(file: File?) {
        file?.delete()
    }
}

/**
 * ViewModel de uma conversa. Não guarda nada em disco -- todo o histórico de
 * mensagens exibido some ao sair da tela/processo, por desenho (dado
 * sensível de cliente). Controle otimista de `assignment_version`: qualquer
 * 409 recarrega a conversa do zero e avisa o atendente, nunca tenta
 * "adivinhar" o novo estado no cliente.
 *
 * Suporte de mídia (PR #413): esta ViewModel nunca toca em CameraX/
 * MediaRecorder/ContentResolver diretamente -- isso é responsabilidade da
 * Composable (câmera/áudio/galeria), que só reporta eventos terminais aqui
 * (arquivo capturado, erro, cancelamento). [mediaFileStore]/[imageCompressor]
 * são as únicas dependências de plataforma, injetadas para permanecerem
 * fakeable em teste.
 */
class ConversationViewModel(
    private val repository: AtendimentoRepository,
    private val conversationId: Long,
    private val mediaFileStore: MediaFileStore = InertMediaFileStore,
    private val imageCompressor: ImageCompressor = AndroidImageCompressor(),
    private val featureFlagsRepository: FeatureFlagsRepository = AlwaysDisabledFeatureFlags,
    private val connectivityObserver: ConnectivityObserver = AlwaysOnlineConnectivityObserver,
    private val notifier: AttendanceNotifier = NoopAttendanceNotifier,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ConversationUiState())
    val uiState: StateFlow<ConversationUiState> = _uiState.asStateFlow()

    /**
     * Geração da carga "cheia" da conversa (load()/refreshMessagesQuietly()/
     * polling em primeiro plano). Cada chamada captura o valor incrementado
     * em uma variável local antes de suspender; ao voltar, só aplica o
     * resultado se nenhuma chamada mais nova tiver começado nesse meio-tempo
     * -- evita que a resposta atrasada de um load()/refresh/tick de polling
     * antigo sobrescreva um estado mais novo (ex.: dois refreshes disparados
     * em sequência rápida, um retry manual enquanto o load() anterior ainda
     * estava em voo, ou um ciclo de polling atrasado que chega depois de um
     * mais recente já ter respondido).
     */
    private var requestGeneration = 0

    /** Job do upload de mídia em voo -- cancelado explicitamente por [cancelMediaUpload]. */
    private var uploadJob: Job? = null

    // -------- Sincronização em primeiro plano (PR #414) --------
    //
    // Um único AttendanceSyncLoop por instância desta ViewModel, ou seja, por
    // conversationId -- nunca compartilhado entre conversas. Só roda quando a
    // tela está de fato visível (onScreenResumed/onScreenPaused, chamados
    // pela Composable via lifecycle) E a flag REALTIME_SYNC_ENABLED está
    // ligada; qualquer uma das duas condições ausentes para o loop.
    // viewModelScope garante que o loop morre com a ViewModel (nunca
    // GlobalScope) e nunca sobrevive à troca de conversa.

    private val syncLoop = AttendanceSyncLoop(
        scope = viewModelScope,
        baseIntervalMs = SyncConfig.CONVERSATION_POLL_INTERVAL_MS,
        tick = ::pollTick,
    )

    private var isScreenActive = false
    private var isRealtimeSyncFlagEnabled = false

    init {
        load()
        _uiState.value = _uiState.value.copy(isOnline = connectivityObserver.isOnlineNow())
        viewModelScope.launch {
            featureFlagsRepository.isEnabled(FeatureFlag.REALTIME_SYNC_ENABLED).collect { enabled ->
                isRealtimeSyncFlagEnabled = enabled
                evaluateSync()
            }
        }
        viewModelScope.launch {
            connectivityObserver.observe().collect { online ->
                _uiState.value = _uiState.value.copy(isOnline = online)
            }
        }
    }

    /** Chamado pela tela quando ela entra em primeiro plano (ON_RESUME) -- nunca no init, para não iniciar o loop antes da UI existir de fato. */
    fun onScreenResumed() {
        isScreenActive = true
        AttendanceForegroundState.setVisibleConversation(conversationId)
        notifier.clearForConversation(conversationId)
        evaluateSync()
    }

    /** Chamado quando a tela sai de primeiro plano (ON_PAUSE) ou é destruída -- pausa o polling, nunca o cancela de forma que impeça retomar. */
    fun onScreenPaused() {
        isScreenActive = false
        AttendanceForegroundState.clearVisibleConversation(conversationId)
        evaluateSync()
    }

    private fun evaluateSync() {
        if (isScreenActive && isRealtimeSyncFlagEnabled) {
            syncLoop.start()
        } else {
            syncLoop.stop()
        }
    }

    /**
     * Um ciclo de polling: conversa + página mais recente de mensagens.
     * Devolve `true` em sucesso (o [AttendanceSyncLoop] volta ao intervalo-
     * base) e `false` em falha (dispara backoff exponencial). Uma resposta
     * descartada por ser antiga (generation guard) conta como sucesso -- não
     * foi uma falha de rede, só uma corrida com uma chamada mais nova.
     */
    private suspend fun pollTick(): Boolean {
        if (!connectivityObserver.isOnlineNow()) {
            _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.OFFLINE)
            return false
        }
        // Nunca sobrescreve um envio/ação em andamento no meio do caminho.
        val stateBeforeTick = _uiState.value
        if (stateBeforeTick.isSending || stateBeforeTick.isActionInProgress) return true

        _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.SYNCING)
        val generation = ++requestGeneration
        val conversationResult = repository.getConversation(conversationId)
        val messagesResult = repository.getMessages(conversationId, beforeId = null, limit = MESSAGES_PAGE_SIZE)
        if (generation != requestGeneration) return true

        return if (conversationResult is ApiResult.Success && messagesResult is ApiResult.Success) {
            val previousMessageIds = _uiState.value.messages.map { it.id }.toSet()
            val hasNewInbound = messagesResult.data.any { it.id !in previousMessageIds && it.direction == "inbound" }
            _uiState.value = _uiState.value.copy(
                conversation = conversationResult.data,
                messages = messagesResult.data,
                hasMoreHistory = messagesResult.data.size >= MESSAGES_PAGE_SIZE,
                syncStatus = SyncStatus.UPDATED,
            )
            if (hasNewInbound) notifier.notifyNewMessage(conversationId)
            true
        } else {
            _uiState.value = _uiState.value.copy(syncStatus = SyncStatus.FAILED)
            false
        }
    }

    /** Atualização manual (botão/gesto) -- sempre disponível independente da flag/tela ativa, mesmo padrão de [load]. */
    fun refresh() {
        load()
    }

    fun load() {
        val generation = ++requestGeneration
        _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
        viewModelScope.launch {
            val conversationResult = repository.getConversation(conversationId)
            val messagesResult = repository.getMessages(conversationId, beforeId = null, limit = MESSAGES_PAGE_SIZE)
            if (generation != requestGeneration) return@launch
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

    // -------- Permissões de mídia (câmera/microfone) --------
    //
    // A Composable é quem decide granted/rationale/permanentemente-negada
    // (via shouldShowRequestPermissionRationale, que exige Activity) -- esta
    // ViewModel só guarda qual diálogo mostrar, nunca chama API de permissão
    // diretamente (não tem Context).

    fun onMediaPermissionDenied(permission: MediaPermissionType, permanentlyDenied: Boolean) {
        _uiState.value = _uiState.value.copy(
            media = _uiState.value.media.copy(
                permissionRationale = if (permanentlyDenied) null else permission,
                permissionPermanentlyDenied = if (permanentlyDenied) permission else null,
            ),
        )
    }

    fun dismissMediaPermissionDialog() {
        _uiState.value = _uiState.value.copy(
            media = _uiState.value.media.copy(permissionRationale = null, permissionPermanentlyDenied = null),
        )
    }

    // -------- Câmera --------

    fun openCamera() {
        val file = mediaFileStore.newCameraCaptureFile()
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(cameraOutputFile = file))
    }

    fun closeCamera() {
        mediaFileStore.delete(_uiState.value.media.cameraOutputFile)
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(cameraOutputFile = null))
    }

    fun onPhotoCaptured(rawFile: File) {
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(cameraOutputFile = null))
        compressAndStagePendingImage(rawFile)
    }

    // -------- Galeria (Photo Picker) --------

    fun onGalleryImageSelected(uri: Uri) {
        viewModelScope.launch {
            val imported = mediaFileStore.importFromGallery(uri)
            if (imported == null) {
                _uiState.value = _uiState.value.copy(errorMessage = "Não foi possível abrir a imagem selecionada.")
                return@launch
            }
            compressAndStagePendingImage(imported)
        }
    }

    private fun compressAndStagePendingImage(rawFile: File) {
        viewModelScope.launch {
            try {
                val destination = mediaFileStore.newCompressedImageFile()
                val result = imageCompressor.compress(rawFile, destination)
                mediaFileStore.delete(rawFile)
                _uiState.value = _uiState.value.copy(
                    media = _uiState.value.media.copy(
                        pendingMedia = PendingMedia(kind = MediaKind.IMAGE, file = result.file),
                    ),
                )
            } catch (error: Exception) {
                mediaFileStore.delete(rawFile)
                _uiState.value = _uiState.value.copy(errorMessage = "Não foi possível processar a imagem.")
            }
        }
    }

    // -------- Áudio --------

    fun openAudioRecorder() {
        val file = mediaFileStore.newAudioRecordingFile()
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(audioOutputFile = file))
    }

    /** Fecha o sheet de áudio: cancela gravação em andamento e descarta qualquer arquivo pendente (câmera de troco). */
    fun closeAudioRecorder() {
        val media = _uiState.value.media
        mediaFileStore.delete(media.audioOutputFile)
        mediaFileStore.delete(media.pendingMedia?.takeIf { it.kind == MediaKind.AUDIO }?.file)
        _uiState.value = _uiState.value.copy(
            media = media.copy(
                audioOutputFile = null,
                isRecordingAudio = false,
                recordingElapsedMs = 0L,
                pendingMedia = media.pendingMedia?.takeIf { it.kind != MediaKind.AUDIO },
            ),
        )
    }

    fun onAudioRecordingStarted() {
        _uiState.value = _uiState.value.copy(
            media = _uiState.value.media.copy(isRecordingAudio = true, recordingElapsedMs = 0L),
        )
    }

    fun onAudioRecordingTick(elapsedMs: Long) {
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(recordingElapsedMs = elapsedMs))
    }

    fun onAudioRecordingStopped(file: File, durationMs: Long) {
        _uiState.value = _uiState.value.copy(
            media = _uiState.value.media.copy(
                isRecordingAudio = false,
                pendingMedia = PendingMedia(kind = MediaKind.AUDIO, file = file, durationMs = durationMs),
            ),
        )
    }

    fun onAudioRecordingCancelled() {
        val media = _uiState.value.media
        mediaFileStore.delete(media.audioOutputFile)
        mediaFileStore.delete(media.pendingMedia?.takeIf { it.kind == MediaKind.AUDIO }?.file)
        _uiState.value = _uiState.value.copy(
            media = media.copy(isRecordingAudio = false, audioOutputFile = null, pendingMedia = null),
        )
    }

    /** Erro vindo da câmera/gravador (ex.: falha ao abrir a câmera, falha ao salvar a gravação) -- fecha a UI de mídia envolvida e limpa o temp file. */
    fun onMediaError(message: String) {
        val media = _uiState.value.media
        mediaFileStore.delete(media.cameraOutputFile)
        mediaFileStore.delete(media.audioOutputFile)
        _uiState.value = _uiState.value.copy(
            errorMessage = message,
            media = media.copy(cameraOutputFile = null, audioOutputFile = null, isRecordingAudio = false),
        )
    }

    // -------- Envio da mídia pendente (imagem ou áudio) --------

    fun onPendingMediaCaptionChanged(caption: String) {
        val pending = _uiState.value.media.pendingMedia ?: return
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(pendingMedia = pending.copy(caption = caption)))
    }

    /** Descarta a mídia pendente sem enviar (cancelamento explícito do usuário) -- sempre apaga o temp file. */
    fun cancelPendingMedia() {
        uploadJob?.cancel()
        mediaFileStore.delete(_uiState.value.media.pendingMedia?.file)
        _uiState.value = _uiState.value.copy(
            media = _uiState.value.media.copy(pendingMedia = null, isUploadingMedia = false, uploadProgress = 0f),
        )
    }

    /** Cancela só o upload em voo -- mantém a mídia pendente para um retry explícito do usuário (nunca reenvia sozinho). */
    fun cancelMediaUpload() {
        uploadJob?.cancel()
        _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(isUploadingMedia = false, uploadProgress = 0f))
    }

    fun sendPendingMedia() {
        val state = _uiState.value
        val pending = state.media.pendingMedia ?: return
        if (state.media.isUploadingMedia) return

        val limit = if (pending.kind == MediaKind.IMAGE) MediaLimits.MAX_IMAGE_BYTES else MediaLimits.MAX_AUDIO_BYTES
        if (pending.file.length() > limit) {
            _uiState.value = _uiState.value.copy(
                errorMessage = "Arquivo excede o tamanho máximo permitido (${limit / (1024 * 1024)}MB). Escolha um arquivo menor.",
            )
            return
        }

        _uiState.value = _uiState.value.copy(
            errorMessage = null,
            media = _uiState.value.media.copy(isUploadingMedia = true, uploadProgress = 0f),
        )
        uploadJob = viewModelScope.launch {
            val mimeType = if (pending.kind == MediaKind.IMAGE) "image/jpeg" else "audio/mp4"
            val result = repository.sendMedia(
                conversationId = conversationId,
                kind = pending.kind,
                file = pending.file,
                mimeType = mimeType,
                caption = pending.caption.takeIf { it.isNotBlank() },
                assignmentVersion = _uiState.value.conversation?.assignmentVersion,
                onProgress = { progress ->
                    _uiState.value = _uiState.value.copy(media = _uiState.value.media.copy(uploadProgress = progress))
                },
            )
            when (result) {
                is ApiResult.Success -> {
                    if (result.data.ok) {
                        mediaFileStore.delete(pending.file)
                        _uiState.value = _uiState.value.copy(
                            media = _uiState.value.media.copy(
                                pendingMedia = null,
                                isUploadingMedia = false,
                                uploadProgress = 0f,
                                audioOutputFile = null,
                            ),
                        )
                        refreshMessagesQuietly()
                    } else {
                        // Falha "suave" reportada pelo backend (ex.: provider
                        // indisponível) -- mantém o arquivo para um retry
                        // explícito (nova tentativa = nova Idempotency-Key).
                        _uiState.value = _uiState.value.copy(
                            errorMessage = "Não foi possível enviar a mídia. Tente novamente.",
                            media = _uiState.value.media.copy(isUploadingMedia = false, uploadProgress = 0f),
                        )
                    }
                }
                is ApiResult.Failure -> {
                    _uiState.value = _uiState.value.copy(
                        media = _uiState.value.media.copy(isUploadingMedia = false, uploadProgress = 0f),
                    )
                    handleActionFailure(result.error)
                }
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        // Polling desta conversa nunca sobrevive à ViewModel -- cancelamento
        // explícito além do que viewModelScope já garantiria, e limpeza do
        // estado global de "conversa visível" (rede de segurança contra
        // destruição fora da ordem onScreenPaused -> onCleared).
        syncLoop.stop()
        AttendanceForegroundState.clearVisibleConversation(conversationId)
        // Rede de segurança: se a tela for destruída com mídia pendente (o
        // usuário nunca confirmou nem cancelou explicitamente), nenhum
        // arquivo de cliente pode sobreviver além da sessão -- ver regra de
        // "nunca persistir mídia de cliente" do escopo desta PR.
        val media = _uiState.value.media
        mediaFileStore.delete(media.cameraOutputFile)
        mediaFileStore.delete(media.audioOutputFile)
        mediaFileStore.delete(media.pendingMedia?.file)
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
        val generation = ++requestGeneration
        viewModelScope.launch {
            when (val result = repository.getMessages(conversationId, beforeId = null, limit = MESSAGES_PAGE_SIZE)) {
                is ApiResult.Success -> {
                    if (generation != requestGeneration) return@launch
                    _uiState.value = _uiState.value.copy(
                        messages = result.data,
                        hasMoreHistory = result.data.size >= MESSAGES_PAGE_SIZE,
                    )
                }
                is ApiResult.Failure -> Unit // mensagem já foi enviada; falha aqui só afeta o refresh da lista
            }
        }
    }
}
