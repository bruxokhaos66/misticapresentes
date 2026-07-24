package br.com.misticapresentes.painel.atendimento.network.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * DTOs da Central de Atendimento nativa (PR #412). Os nomes de campo JSON
 * seguem EXATAMENTE o que os endpoints reais devolvem hoje -- conferidos
 * em `backend/atendimento_repository.py` (linha_conversa_fila_publica,
 * listar_agentes/_linha_agente_publica), `backend/whatsapp_inbox_repository.py`
 * (linha_conversa_publica, linha_mensagem_publica) e
 * `backend/whatsapp_catalog_repository.py` (produto_linha_publica). Nenhum
 * endpoint novo foi inventado; nenhum campo aqui existe só no cliente.
 */

@Serializable
data class ContactDto(
    @SerialName("profile_name") val profileName: String? = null,
    @SerialName("phone_last4") val phoneLast4: String? = null,
)

/**
 * Forma devolvida por fila/minhas-conversas/claim/release/transfer/resolve/
 * reopen (`atendimento_repository.linha_conversa_fila_publica`).
 */
@Serializable
data class QueueConversationDto(
    val id: Long,
    val status: String? = null,
    @SerialName("queue_status") val queueStatus: String? = null,
    @SerialName("assigned_user_id") val assignedUserId: Long? = null,
    @SerialName("assigned_at") val assignedAt: String? = null,
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
    @SerialName("unread_count") val unreadCount: Int? = null,
    @SerialName("last_message_at") val lastMessageAt: String? = null,
    @SerialName("last_inbound_at") val lastInboundAt: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("customer_id") val customerId: Long? = null,
    @SerialName("order_id") val orderId: Long? = null,
    val contact: ContactDto? = null,
)

@Serializable
data class QueueConversationsPageDto(
    val ok: Boolean = true,
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 0,
    val conversations: List<QueueConversationDto> = emptyList(),
)

/**
 * Forma devolvida pela listagem geral `GET /conversations`
 * (`whatsapp_inbox_repository.linha_conversa_publica`). NÃO inclui
 * assigned_user_id/assignment_version/queue_status -- esses três só
 * aparecem no detalhe (`GET /conversations/{id}`, ver
 * `whatsapp_inbox_routes.rota_obter_conversa`), por isso são opcionais aqui.
 */
@Serializable
data class InboxConversationDto(
    val id: Long,
    val status: String? = null,
    @SerialName("assigned_admin") val assignedAdmin: String? = null,
    @SerialName("unread_count") val unreadCount: Int? = null,
    @SerialName("last_message_at") val lastMessageAt: String? = null,
    @SerialName("last_inbound_at") val lastInboundAt: String? = null,
    @SerialName("last_outbound_at") val lastOutboundAt: String? = null,
    @SerialName("customer_id") val customerId: Long? = null,
    @SerialName("order_id") val orderId: Long? = null,
    @SerialName("created_at") val createdAt: String? = null,
    val contact: ContactDto? = null,
    @SerialName("assigned_user_id") val assignedUserId: Long? = null,
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
    @SerialName("queue_status") val queueStatus: String? = null,
)

@Serializable
data class InboxConversationsPageDto(
    val ok: Boolean = true,
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 0,
    val conversations: List<InboxConversationDto> = emptyList(),
)

@Serializable
data class ConversationDetailResponseDto(
    val ok: Boolean = true,
    val conversation: InboxConversationDto,
)

@Serializable
data class MessageDto(
    val id: Long,
    @SerialName("conversation_id") val conversationId: Long? = null,
    @SerialName("meta_message_id") val metaMessageId: String? = null,
    val direction: String? = null,
    @SerialName("message_type") val messageType: String? = null,
    @SerialName("text_body") val textBody: String? = null,
    @SerialName("media_id") val mediaId: String? = null,
    @SerialName("media_mime_type") val mediaMimeType: String? = null,
    @SerialName("media_size") val mediaSize: Long? = null,
    @SerialName("reply_to_meta_message_id") val replyToMetaMessageId: String? = null,
    @SerialName("template_name") val templateName: String? = null,
    val status: String? = null,
    @SerialName("error_code") val errorCode: String? = null,
    @SerialName("error_message_sanitized") val errorMessageSanitized: String? = null,
    @SerialName("sent_by_admin") val sentByAdmin: String? = null,
    @SerialName("timestamp_meta") val timestampMeta: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class MessagesResponseDto(
    val ok: Boolean = true,
    val messages: List<MessageDto> = emptyList(),
)

@Serializable
data class SendMessageRequestDto(
    val text: String,
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
)

@Serializable
data class SendMessageResponseDto(
    val ok: Boolean = false,
    @SerialName("message_id") val messageId: Long? = null,
    val status: String? = null,
)

@Serializable
data class SendProductRequestDto(
    @SerialName("product_id") val productId: Long,
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
)

@Serializable
data class SendProductResponseDto(
    val ok: Boolean = false,
    @SerialName("message_id") val messageId: Long? = null,
    val status: String? = null,
    @SerialName("product_id") val productId: Long? = null,
)

@Serializable
data class ProductDto(
    val id: Long,
    val nome: String? = null,
    val sku: String? = null,
    val categoria: String? = null,
    val marca: String? = null,
    val preco: Double? = null,
    @SerialName("preco_promocional") val precoPromocional: Double? = null,
    val moeda: String? = null,
    @SerialName("estoque_status") val estoqueStatus: String? = null,
    @SerialName("imagem_url") val imagemUrl: String? = null,
    @SerialName("imagem_bloqueada_por_host") val imagemBloqueadaPorHost: Boolean? = null,
    @SerialName("url_publica") val urlPublica: String? = null,
    val ativo: Boolean? = null,
    val disponivel: Boolean? = null,
)

@Serializable
data class ProductsPageDto(
    val ok: Boolean = true,
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 0,
    val products: List<ProductDto> = emptyList(),
)

@Serializable
data class RecentProductsResponseDto(
    val ok: Boolean = true,
    val products: List<ProductDto> = emptyList(),
)

@Serializable
data class ClaimReleaseResponseDto(
    val ok: Boolean = true,
    val conversation: QueueConversationDto,
)

@Serializable
data class ReleaseRequestDto(val reason: String? = null)

@Serializable
data class TransferRequestDto(
    @SerialName("target_user_id") val targetUserId: Long,
    val reason: String? = null,
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
)

@Serializable
data class ResolveRequestDto(
    @SerialName("assignment_version") val assignmentVersion: Int? = null,
)

@Serializable
data class AgentDto(
    val id: Long,
    val nome: String? = null,
    val login: String? = null,
    val perfil: String? = null,
    val ativo: Boolean? = null,
    @SerialName("atendimento_enabled") val atendimentoEnabled: Boolean? = null,
    @SerialName("atendimento_status") val atendimentoStatus: String? = null,
    @SerialName("atendimento_max_active_conversations") val atendimentoMaxActiveConversations: Int? = null,
    @SerialName("atendimento_suspended_at") val atendimentoSuspendedAt: String? = null,
    @SerialName("atendimento_last_activity_at") val atendimentoLastActivityAt: String? = null,
    @SerialName("active_conversations") val activeConversations: Int? = null,
)

@Serializable
data class AgentsResponseDto(
    val ok: Boolean = true,
    val agents: List<AgentDto> = emptyList(),
)

@Serializable
data class AssignmentHistoryDto(
    val id: Long,
    @SerialName("conversation_id") val conversationId: Long? = null,
    val action: String? = null,
    @SerialName("from_user_id") val fromUserId: Long? = null,
    @SerialName("to_user_id") val toUserId: Long? = null,
    @SerialName("performed_by_user_id") val performedByUserId: Long? = null,
    val reason: String? = null,
    @SerialName("previous_version") val previousVersion: Int? = null,
    @SerialName("new_version") val newVersion: Int? = null,
    @SerialName("created_at") val createdAt: String? = null,
)

@Serializable
data class AssignmentHistoryResponseDto(
    val ok: Boolean = true,
    val total: Int = 0,
    val page: Int = 1,
    @SerialName("page_size") val pageSize: Int = 0,
    val history: List<AssignmentHistoryDto> = emptyList(),
)
