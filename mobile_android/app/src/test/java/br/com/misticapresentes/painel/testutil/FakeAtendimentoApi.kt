package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.atendimento.network.AtendimentoApi
import br.com.misticapresentes.painel.atendimento.network.dto.AgentDto
import br.com.misticapresentes.painel.atendimento.network.dto.AgentsResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.AssignmentHistoryDto
import br.com.misticapresentes.painel.atendimento.network.dto.AssignmentHistoryResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ClaimReleaseResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ContactDto
import br.com.misticapresentes.painel.atendimento.network.dto.ConversationDetailResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.InboxConversationDto
import br.com.misticapresentes.painel.atendimento.network.dto.InboxConversationsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.MessageDto
import br.com.misticapresentes.painel.atendimento.network.dto.MessagesResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ProductDto
import br.com.misticapresentes.painel.atendimento.network.dto.ProductsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.QueueConversationDto
import br.com.misticapresentes.painel.atendimento.network.dto.QueueConversationsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.RecentProductsResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ReleaseRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.ResolveRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendMessageRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendMessageResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendProductRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendProductResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.TransferRequestDto
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.Response

/**
 * Fake de [AtendimentoApi] para testar [br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository]
 * e os ViewModels da Central de Atendimento sem rede real -- mesmo padrão de
 * [FakeMisticaApi].
 */
class FakeAtendimentoApi : AtendimentoApi {

    var queueConversations = listOf(defaultQueueConversation())
    var myConversations = listOf(defaultQueueConversation())
    var allConversations = listOf(defaultInboxConversation())
    var conversationDetail = defaultInboxConversation()
    var messages = listOf(defaultMessage())
    var products = listOf(defaultProduct())
    var agents = listOf(defaultAgent())
    var assignmentHistory = emptyList<AssignmentHistoryDto>()

    var responseCode = 200
    var sendMessageOk = true
    var sendProductOk = true

    var lastSendMessageIdempotencyKey: String? = null
    var sendMessageCallCount = 0
    var claimCallCount = 0
    var releaseCallCount = 0
    var transferCallCount = 0
    var resolveCallCount = 0

    private fun <T> errorOrElse(body: () -> Response<T>): Response<T> =
        if (responseCode in 200..299) body() else Response.error(responseCode, "erro".toResponseBody(null))

    override suspend fun queue(page: Int, pageSize: Int) = errorOrElse {
        Response.success(QueueConversationsPageDto(total = queueConversations.size, page = page, pageSize = pageSize, conversations = queueConversations))
    }

    override suspend fun myConversations(page: Int, pageSize: Int) = errorOrElse {
        Response.success(QueueConversationsPageDto(total = myConversations.size, page = page, pageSize = pageSize, conversations = myConversations))
    }

    override suspend fun conversations(status: String?, unreadOnly: Boolean?, q: String?, page: Int, pageSize: Int) = errorOrElse {
        Response.success(InboxConversationsPageDto(total = allConversations.size, page = page, pageSize = pageSize, conversations = allConversations))
    }

    override suspend fun getConversation(conversationId: Long) = errorOrElse {
        Response.success(ConversationDetailResponseDto(conversation = conversationDetail))
    }

    override suspend fun getMessages(conversationId: Long, beforeId: Long?, limit: Int) = errorOrElse {
        Response.success(MessagesResponseDto(messages = messages))
    }

    override suspend fun sendMessage(conversationId: Long, body: SendMessageRequestDto, idempotencyKey: String) = errorOrElse {
        sendMessageCallCount++
        lastSendMessageIdempotencyKey = idempotencyKey
        Response.success(SendMessageResponseDto(ok = sendMessageOk, messageId = 1, status = if (sendMessageOk) "sent" else "failed"))
    }

    override suspend fun sendProduct(conversationId: Long, body: SendProductRequestDto, idempotencyKey: String) = errorOrElse {
        Response.success(SendProductResponseDto(ok = sendProductOk, messageId = 2, status = if (sendProductOk) "sent" else "failed", productId = body.productId))
    }

    override suspend fun searchProducts(q: String, page: Int, pageSize: Int) = errorOrElse {
        Response.success(ProductsPageDto(total = products.size, page = page, pageSize = pageSize, products = products))
    }

    override suspend fun recentProducts(limit: Int) = errorOrElse {
        Response.success(RecentProductsResponseDto(products = products))
    }

    override suspend fun claim(conversationId: Long) = errorOrElse {
        claimCallCount++
        Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
    }

    override suspend fun release(conversationId: Long, body: ReleaseRequestDto) = errorOrElse {
        releaseCallCount++
        Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
    }

    override suspend fun transfer(conversationId: Long, body: TransferRequestDto) = errorOrElse {
        transferCallCount++
        Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
    }

    override suspend fun resolve(conversationId: Long, body: ResolveRequestDto) = errorOrElse {
        resolveCallCount++
        Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
    }

    override suspend fun assignmentHistory(conversationId: Long, page: Int, pageSize: Int) = errorOrElse {
        Response.success(AssignmentHistoryResponseDto(total = assignmentHistory.size, page = page, pageSize = pageSize, history = assignmentHistory))
    }

    override suspend fun agents() = errorOrElse {
        Response.success(AgentsResponseDto(agents = agents))
    }

    companion object {
        fun defaultQueueConversation() = QueueConversationDto(
            id = 1,
            status = "open",
            queueStatus = "waiting",
            assignedUserId = null,
            assignmentVersion = 0,
            unreadCount = 1,
            lastMessageAt = "2026-07-24T10:00:00",
            lastInboundAt = "2026-07-24T10:00:00",
            createdAt = "2026-07-24T09:00:00",
            contact = ContactDto(profileName = "Cliente Teste", phoneLast4 = "1234"),
        )

        fun defaultInboxConversation() = InboxConversationDto(
            id = 1,
            status = "open",
            assignedAdmin = null,
            unreadCount = 1,
            lastMessageAt = "2026-07-24T10:00:00",
            lastInboundAt = "2026-07-24T10:00:00",
            createdAt = "2026-07-24T09:00:00",
            contact = ContactDto(profileName = "Cliente Teste", phoneLast4 = "1234"),
            assignedUserId = null,
            assignmentVersion = 0,
            queueStatus = "waiting",
        )

        fun defaultMessage() = MessageDto(
            id = 1,
            conversationId = 1,
            direction = "inbound",
            messageType = "text",
            textBody = "Olá",
            status = null,
            sentByAdmin = null,
            timestampMeta = "2026-07-24T09:00:00",
            createdAt = "2026-07-24T09:00:00",
        )

        fun defaultProduct() = ProductDto(
            id = 1,
            nome = "Baralho Cigano",
            sku = "SKU-1",
            preco = 49.9,
            moeda = "BRL",
            disponivel = true,
            ativo = true,
            urlPublica = "https://misticaesotericos.com.br/produto/1",
        )

        fun defaultAgent() = AgentDto(
            id = 1,
            nome = "Vendedora Luna",
            login = "luna",
            perfil = "vendedor",
            ativo = true,
            atendimentoEnabled = true,
            atendimentoStatus = "online",
            activeConversations = 1,
        )
    }
}
