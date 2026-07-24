package br.com.misticapresentes.painel.atendimento.model

/**
 * Modelos de domínio da Central de Atendimento nativa, desacoplados dos DTOs
 * de rede (mapeamento feito só no repository -- ver
 * [br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository]).
 * A UI (Composables) só enxerga estes tipos através do StateFlow do
 * ViewModel, nunca DTO nem Retrofit diretamente.
 */

/** Os três filtros da lista de atendimentos, cada um mapeado para um endpoint diferente. */
enum class ConversationFilter {
    MINE, QUEUE, ALL
}

/**
 * Uma conversa, seja na forma resumida de lista (fila/minhas/todas) ou no
 * detalhe. Os campos exclusivos da Central Multiatendente (queueStatus,
 * assignedUserId, assignmentVersion) só vêm preenchidos quando a origem é a
 * fila/minhas-conversas/ações (claim etc.) ou o detalhe -- nunca na listagem
 * "Todas", que o backend não enriquece com eles.
 */
data class Conversation(
    val id: Long,
    val status: String?,
    val queueStatus: String?,
    val assignedUserId: Long?,
    val assignmentVersion: Int?,
    val unreadCount: Int,
    val lastMessageAt: String?,
    val lastInboundAt: String?,
    val createdAt: String?,
    val profileName: String?,
    val phoneLast4: String?,
)

data class ConversationPage(
    val items: List<Conversation>,
    val total: Int,
    val page: Int,
    val pageSize: Int,
)

data class Message(
    val id: Long,
    val direction: String?,
    val messageType: String?,
    val textBody: String?,
    val status: String?,
    val sentByAdmin: String?,
    /** timestamp_meta quando disponível, senão created_at -- sempre uma das duas. */
    val timestamp: String?,
)

data class SendResult(
    val ok: Boolean,
    val messageId: Long?,
    val status: String?,
)

/**
 * Tipo de mídia enviável pelo compose avançado (câmera/galeria = IMAGE,
 * gravação de áudio = AUDIO) -- espelha `media_kind` aceito por
 * `POST /conversations/{id}/media` (`"image"` ou `"audio"`, ver
 * `backend/whatsapp_inbox_routes.py`). Vive no pacote de modelos de domínio
 * (não em `atendimento.media`, que é infraestrutura específica de
 * plataforma) porque é usado tanto pelo repository quanto pela UI.
 */
enum class MediaKind { IMAGE, AUDIO }

data class Product(
    val id: Long,
    val nome: String,
    val sku: String,
    val preco: Double,
    val precoPromocional: Double?,
    val moeda: String,
    val imagemUrl: String?,
    val disponivel: Boolean,
    val urlPublica: String?,
)

data class Agent(
    val id: Long,
    val nome: String,
    val perfil: String?,
    val atendimentoEnabled: Boolean,
    val atendimentoStatus: String?,
    val activeConversations: Int,
    val maxActiveConversations: Int?,
)

data class AssignmentHistoryEntry(
    val id: Long,
    val action: String?,
    val fromUserId: Long?,
    val toUserId: Long?,
    val performedByUserId: Long?,
    val reason: String?,
    val createdAt: String?,
)
