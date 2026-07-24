package br.com.misticapresentes.painel.atendimento.repository

import br.com.misticapresentes.painel.atendimento.model.Agent
import br.com.misticapresentes.painel.atendimento.model.AssignmentHistoryEntry
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.ConversationPage
import br.com.misticapresentes.painel.atendimento.model.MediaKind
import br.com.misticapresentes.painel.atendimento.model.Message
import br.com.misticapresentes.painel.atendimento.model.Product
import br.com.misticapresentes.painel.atendimento.model.SendResult
import br.com.misticapresentes.painel.atendimento.network.AtendimentoApi
import br.com.misticapresentes.painel.atendimento.network.dto.AgentDto
import br.com.misticapresentes.painel.atendimento.network.dto.AssignmentHistoryDto
import br.com.misticapresentes.painel.atendimento.network.dto.InboxConversationDto
import br.com.misticapresentes.painel.atendimento.network.dto.MessageDto
import br.com.misticapresentes.painel.atendimento.network.dto.ProductDto
import br.com.misticapresentes.painel.atendimento.network.dto.QueueConversationDto
import br.com.misticapresentes.painel.atendimento.network.dto.ReleaseRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.ResolveRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendMessageRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendProductRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.TransferRequestDto
import br.com.misticapresentes.painel.network.ApiResult
import br.com.misticapresentes.painel.network.ProgressRequestBody
import br.com.misticapresentes.painel.network.apiCall
import java.io.File
import java.util.UUID
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Fonte única de verdade da Central de Atendimento nativa: só consome os
 * endpoints reais já existentes do backend (ver
 * [br.com.misticapresentes.painel.atendimento.network.AtendimentoApi]),
 * nunca decide regra de negócio (assunção, janela de 24h, permissão por
 * perfil) -- isso é sempre autoridade do backend, este repository só chama a
 * API e traduz o resultado para os modelos de domínio da UI.
 *
 * NUNCA persiste nada em disco: cada chamada devolve um resultado em memória
 * (ApiResult), sem cache local de mensagens/conversas entre chamadas.
 */
class AtendimentoRepository(
    private val api: AtendimentoApi,
    // Client irmão só com timeouts maiores para o upload de mídia (ver
    // ApiClient.createAtendimentoMediaApi) -- por padrão é o mesmo `api`
    // (ex.: em teste/Fake), produção passa uma instância dedicada via
    // AppContainer.
    private val mediaApi: AtendimentoApi = api,
) {

    suspend fun listQueue(page: Int, pageSize: Int): ApiResult<ConversationPage> =
        when (val result = apiCall { api.queue(page, pageSize) }) {
            is ApiResult.Success -> ApiResult.Success(
                ConversationPage(
                    items = result.data.conversations.map { it.toDomain() },
                    total = result.data.total,
                    page = result.data.page,
                    pageSize = result.data.pageSize,
                ),
            )
            is ApiResult.Failure -> result
        }

    suspend fun listMine(page: Int, pageSize: Int): ApiResult<ConversationPage> =
        when (val result = apiCall { api.myConversations(page, pageSize) }) {
            is ApiResult.Success -> ApiResult.Success(
                ConversationPage(
                    items = result.data.conversations.map { it.toDomain() },
                    total = result.data.total,
                    page = result.data.page,
                    pageSize = result.data.pageSize,
                ),
            )
            is ApiResult.Failure -> result
        }

    suspend fun listAll(
        status: String? = null,
        unreadOnly: Boolean = false,
        q: String? = null,
        page: Int,
        pageSize: Int,
    ): ApiResult<ConversationPage> =
        when (val result = apiCall { api.conversations(status, unreadOnly, q, page, pageSize) }) {
            is ApiResult.Success -> ApiResult.Success(
                ConversationPage(
                    items = result.data.conversations.map { it.toDomain() },
                    total = result.data.total,
                    page = result.data.page,
                    pageSize = result.data.pageSize,
                ),
            )
            is ApiResult.Failure -> result
        }

    suspend fun getConversation(conversationId: Long): ApiResult<Conversation> =
        when (val result = apiCall { api.getConversation(conversationId) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.conversation.toDomain())
            is ApiResult.Failure -> result
        }

    suspend fun getMessages(conversationId: Long, beforeId: Long?, limit: Int): ApiResult<List<Message>> =
        when (val result = apiCall { api.getMessages(conversationId, beforeId, limit) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.messages.map { it.toDomain() })
            is ApiResult.Failure -> result
        }

    /**
     * Gera uma Idempotency-Key nova por TENTATIVA de envio (não por
     * ViewModel/tela) -- bloqueia duplo envio ponta a ponta mesmo que a UI
     * seja contornada, já que cada chamada aqui é uma tentativa distinta.
     */
    suspend fun sendText(conversationId: Long, text: String, assignmentVersion: Int?): ApiResult<SendResult> =
        when (
            val result = apiCall {
                api.sendMessage(
                    conversationId = conversationId,
                    body = SendMessageRequestDto(text = text, assignmentVersion = assignmentVersion),
                    idempotencyKey = UUID.randomUUID().toString(),
                )
            }
        ) {
            is ApiResult.Success -> ApiResult.Success(
                SendResult(ok = result.data.ok, messageId = result.data.messageId, status = result.data.status),
            )
            is ApiResult.Failure -> result
        }

    suspend fun sendProduct(conversationId: Long, productId: Long, assignmentVersion: Int?): ApiResult<SendResult> =
        when (
            val result = apiCall {
                api.sendProduct(
                    conversationId = conversationId,
                    body = SendProductRequestDto(productId = productId, assignmentVersion = assignmentVersion),
                    idempotencyKey = UUID.randomUUID().toString(),
                )
            }
        ) {
            is ApiResult.Success -> ApiResult.Success(
                SendResult(ok = result.data.ok, messageId = result.data.messageId, status = result.data.status),
            )
            is ApiResult.Failure -> result
        }

    /**
     * Envia imagem ou áudio já pronto (comprimido/gravado, arquivo em cache
     * -- ver `atendimento.media.MediaFileStore`) para a conversa. Idempotency-Key
     * nova por TENTATIVA de upload, mesma regra de [sendText]/[sendProduct].
     * [onProgress] reporta 0f..1f conforme os bytes do multipart vão sendo
     * escritos -- nunca decide nada, só repassa para quem chamou (ViewModel).
     */
    suspend fun sendMedia(
        conversationId: Long,
        kind: MediaKind,
        file: File,
        mimeType: String,
        caption: String?,
        assignmentVersion: Int?,
        onProgress: (Float) -> Unit = {},
    ): ApiResult<SendResult> {
        val textPlain = "text/plain".toMediaType()
        val mediaKindPart = (if (kind == MediaKind.IMAGE) "image" else "audio").toRequestBody(textPlain)
        val captionPart = caption?.takeIf { it.isNotBlank() }?.toRequestBody(textPlain)
        val assignmentVersionPart = assignmentVersion?.toString()?.toRequestBody(textPlain)
        val progressBody = ProgressRequestBody(file.asRequestBody(mimeType.toMediaType())) { sent, total ->
            if (total > 0) onProgress(sent.toFloat() / total.toFloat())
        }
        val filePart = MultipartBody.Part.createFormData("file", file.name, progressBody)

        return when (
            val result = apiCall {
                mediaApi.sendMedia(
                    conversationId = conversationId,
                    mediaKind = mediaKindPart,
                    caption = captionPart,
                    assignmentVersion = assignmentVersionPart,
                    file = filePart,
                    idempotencyKey = UUID.randomUUID().toString(),
                )
            }
        ) {
            is ApiResult.Success -> ApiResult.Success(
                SendResult(ok = result.data.ok, messageId = result.data.messageId, status = result.data.status),
            )
            is ApiResult.Failure -> result
        }
    }

    suspend fun searchProducts(q: String, page: Int, pageSize: Int): ApiResult<List<Product>> =
        when (val result = apiCall { api.searchProducts(q, page, pageSize) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.products.map { it.toDomain() })
            is ApiResult.Failure -> result
        }

    suspend fun recentProducts(limit: Int): ApiResult<List<Product>> =
        when (val result = apiCall { api.recentProducts(limit) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.products.map { it.toDomain() })
            is ApiResult.Failure -> result
        }

    suspend fun claim(conversationId: Long): ApiResult<Conversation> =
        when (val result = apiCall { api.claim(conversationId) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.conversation.toDomain())
            is ApiResult.Failure -> result
        }

    suspend fun release(conversationId: Long, reason: String?): ApiResult<Conversation> =
        when (val result = apiCall { api.release(conversationId, ReleaseRequestDto(reason = reason)) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.conversation.toDomain())
            is ApiResult.Failure -> result
        }

    suspend fun transfer(
        conversationId: Long,
        targetUserId: Long,
        reason: String?,
        assignmentVersion: Int?,
    ): ApiResult<Conversation> =
        when (
            val result = apiCall {
                api.transfer(
                    conversationId,
                    TransferRequestDto(targetUserId = targetUserId, reason = reason, assignmentVersion = assignmentVersion),
                )
            }
        ) {
            is ApiResult.Success -> ApiResult.Success(result.data.conversation.toDomain())
            is ApiResult.Failure -> result
        }

    suspend fun resolve(conversationId: Long, assignmentVersion: Int?): ApiResult<Conversation> =
        when (val result = apiCall { api.resolve(conversationId, ResolveRequestDto(assignmentVersion = assignmentVersion)) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.conversation.toDomain())
            is ApiResult.Failure -> result
        }

    suspend fun assignmentHistory(conversationId: Long, page: Int, pageSize: Int): ApiResult<List<AssignmentHistoryEntry>> =
        when (val result = apiCall { api.assignmentHistory(conversationId, page, pageSize) }) {
            is ApiResult.Success -> ApiResult.Success(result.data.history.map { it.toDomain() })
            is ApiResult.Failure -> result
        }

    suspend fun listAgents(): ApiResult<List<Agent>> =
        when (val result = apiCall { api.agents() }) {
            is ApiResult.Success -> ApiResult.Success(result.data.agents.map { it.toDomain() })
            is ApiResult.Failure -> result
        }
}

private fun QueueConversationDto.toDomain() = Conversation(
    id = id,
    status = status,
    queueStatus = queueStatus,
    assignedUserId = assignedUserId,
    assignmentVersion = assignmentVersion,
    unreadCount = unreadCount ?: 0,
    lastMessageAt = lastMessageAt,
    lastInboundAt = lastInboundAt,
    createdAt = createdAt,
    profileName = contact?.profileName,
    phoneLast4 = contact?.phoneLast4,
)

private fun InboxConversationDto.toDomain() = Conversation(
    id = id,
    status = status,
    queueStatus = queueStatus,
    assignedUserId = assignedUserId,
    assignmentVersion = assignmentVersion,
    unreadCount = unreadCount ?: 0,
    lastMessageAt = lastMessageAt,
    lastInboundAt = lastInboundAt,
    createdAt = createdAt,
    profileName = contact?.profileName,
    phoneLast4 = contact?.phoneLast4,
)

private fun MessageDto.toDomain() = Message(
    id = id,
    direction = direction,
    messageType = messageType,
    textBody = textBody,
    status = status,
    sentByAdmin = sentByAdmin,
    timestamp = timestampMeta ?: createdAt,
)

private fun ProductDto.toDomain() = Product(
    id = id,
    nome = nome.orEmpty(),
    sku = sku.orEmpty(),
    preco = preco ?: 0.0,
    precoPromocional = precoPromocional,
    moeda = moeda ?: "BRL",
    imagemUrl = imagemUrl?.takeIf { it.isNotBlank() },
    disponivel = disponivel ?: false,
    urlPublica = urlPublica,
)

private fun AgentDto.toDomain() = Agent(
    id = id,
    nome = nome ?: login.orEmpty(),
    perfil = perfil,
    atendimentoEnabled = atendimentoEnabled ?: false,
    atendimentoStatus = atendimentoStatus,
    activeConversations = activeConversations ?: 0,
    maxActiveConversations = atendimentoMaxActiveConversations,
)

private fun AssignmentHistoryDto.toDomain() = AssignmentHistoryEntry(
    id = id,
    action = action,
    fromUserId = fromUserId,
    toUserId = toUserId,
    performedByUserId = performedByUserId,
    reason = reason,
    createdAt = createdAt,
)
