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
import kotlinx.coroutines.delay
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
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
    var sendMediaOk = true

    var sendMediaCallCount = 0
    var sendMediaDelayMs: Long = 0
    var lastSendMediaKind: String? = null
    var lastSendMediaCaption: String? = null
    var lastSendMediaAssignmentVersion: String? = null
    val sendMediaIdempotencyKeys = mutableListOf<String>()

    var lastSendMessageIdempotencyKey: String? = null
    var sendMessageCallCount = 0
    var claimCallCount = 0
    var releaseCallCount = 0
    var transferCallCount = 0
    var resolveCallCount = 0

    /** Todas as Idempotency-Key usadas em `sendMessage`, na ordem das chamadas (não só a última). */
    val sendMessageIdempotencyKeys = mutableListOf<String>()

    /**
     * Registro de toda chamada feita neste fake, na ordem em que ocorreram --
     * usado para provar em testes que NENHUMA chamada foi feita (ex.: guard
     * de feature flag bloqueando a tela antes do ViewModel existir).
     */
    val callLog = mutableListOf<String>()

    /** Atraso artificial (ms de tempo virtual) só em `getConversation`, para simular respostas fora de ordem em teste. */
    var getConversationDelayMs: Long = 0

    /** Atraso artificial (ms de tempo virtual) só em `getMessages`, para simular respostas fora de ordem em teste. */
    var getMessagesDelayMs: Long = 0

    /** Atraso artificial (ms de tempo virtual) só em `sendMessage`, para simular um envio "em voo" em teste. */
    var sendMessageDelayMs: Long = 0

    private fun <T> errorOrElse(body: () -> Response<T>): Response<T> =
        if (responseCode in 200..299) body() else Response.error(responseCode, "erro".toResponseBody(null))

    override suspend fun queue(page: Int, pageSize: Int): Response<QueueConversationsPageDto> {
        callLog += "queue"
        return errorOrElse {
            Response.success(QueueConversationsPageDto(total = queueConversations.size, page = page, pageSize = pageSize, conversations = queueConversations))
        }
    }

    override suspend fun myConversations(page: Int, pageSize: Int): Response<QueueConversationsPageDto> {
        callLog += "myConversations"
        return errorOrElse {
            Response.success(QueueConversationsPageDto(total = myConversations.size, page = page, pageSize = pageSize, conversations = myConversations))
        }
    }

    override suspend fun conversations(status: String?, unreadOnly: Boolean?, q: String?, page: Int, pageSize: Int): Response<InboxConversationsPageDto> {
        callLog += "conversations"
        return errorOrElse {
            Response.success(InboxConversationsPageDto(total = allConversations.size, page = page, pageSize = pageSize, conversations = allConversations))
        }
    }

    override suspend fun getConversation(conversationId: Long): Response<ConversationDetailResponseDto> {
        callLog += "getConversation"
        // Captura o valor ANTES do delay -- assim como um servidor real
        // "veria" o estado no momento em que recebeu a requisição, não no
        // momento em que a resposta é escrita de volta. Isso permite simular
        // em teste duas chamadas concorrentes com respostas diferentes e
        // ordem de chegada invertida (a mais lenta chega por último).
        val snapshot = conversationDetail
        if (getConversationDelayMs > 0) delay(getConversationDelayMs)
        return errorOrElse {
            Response.success(ConversationDetailResponseDto(conversation = snapshot))
        }
    }

    override suspend fun getMessages(conversationId: Long, beforeId: Long?, limit: Int): Response<MessagesResponseDto> {
        callLog += "getMessages"
        val snapshot = messages
        if (getMessagesDelayMs > 0) delay(getMessagesDelayMs)
        return errorOrElse {
            Response.success(MessagesResponseDto(messages = snapshot))
        }
    }

    override suspend fun sendMessage(conversationId: Long, body: SendMessageRequestDto, idempotencyKey: String): Response<SendMessageResponseDto> {
        callLog += "sendMessage"
        sendMessageCallCount++
        lastSendMessageIdempotencyKey = idempotencyKey
        sendMessageIdempotencyKeys += idempotencyKey
        if (sendMessageDelayMs > 0) delay(sendMessageDelayMs)
        return errorOrElse {
            Response.success(SendMessageResponseDto(ok = sendMessageOk, messageId = 1, status = if (sendMessageOk) "sent" else "failed"))
        }
    }

    override suspend fun sendProduct(conversationId: Long, body: SendProductRequestDto, idempotencyKey: String): Response<SendProductResponseDto> {
        callLog += "sendProduct"
        return errorOrElse {
            Response.success(SendProductResponseDto(ok = sendProductOk, messageId = 2, status = if (sendProductOk) "sent" else "failed", productId = body.productId))
        }
    }

    override suspend fun sendMedia(
        conversationId: Long,
        mediaKind: RequestBody,
        caption: RequestBody?,
        assignmentVersion: RequestBody?,
        file: MultipartBody.Part,
        idempotencyKey: String,
    ): Response<SendMessageResponseDto> {
        callLog += "sendMedia"
        sendMediaCallCount++
        lastSendMediaKind = mediaKind.readUtf8()
        lastSendMediaCaption = caption?.readUtf8()
        lastSendMediaAssignmentVersion = assignmentVersion?.readUtf8()
        sendMediaIdempotencyKeys += idempotencyKey
        if (sendMediaDelayMs > 0) delay(sendMediaDelayMs)
        return errorOrElse {
            Response.success(SendMessageResponseDto(ok = sendMediaOk, messageId = 3, status = if (sendMediaOk) "sent" else "failed"))
        }
    }

    override suspend fun searchProducts(q: String, page: Int, pageSize: Int): Response<ProductsPageDto> {
        callLog += "searchProducts"
        return errorOrElse {
            Response.success(ProductsPageDto(total = products.size, page = page, pageSize = pageSize, products = products))
        }
    }

    override suspend fun recentProducts(limit: Int): Response<RecentProductsResponseDto> {
        callLog += "recentProducts"
        return errorOrElse {
            Response.success(RecentProductsResponseDto(products = products))
        }
    }

    override suspend fun claim(conversationId: Long): Response<ClaimReleaseResponseDto> {
        callLog += "claim"
        claimCallCount++
        return errorOrElse {
            Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
        }
    }

    override suspend fun release(conversationId: Long, body: ReleaseRequestDto): Response<ClaimReleaseResponseDto> {
        callLog += "release"
        releaseCallCount++
        return errorOrElse {
            Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
        }
    }

    override suspend fun transfer(conversationId: Long, body: TransferRequestDto): Response<ClaimReleaseResponseDto> {
        callLog += "transfer"
        transferCallCount++
        return errorOrElse {
            Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
        }
    }

    override suspend fun resolve(conversationId: Long, body: ResolveRequestDto): Response<ClaimReleaseResponseDto> {
        callLog += "resolve"
        resolveCallCount++
        return errorOrElse {
            Response.success(ClaimReleaseResponseDto(conversation = queueConversations.first()))
        }
    }

    override suspend fun assignmentHistory(conversationId: Long, page: Int, pageSize: Int): Response<AssignmentHistoryResponseDto> {
        callLog += "assignmentHistory"
        return errorOrElse {
            Response.success(AssignmentHistoryResponseDto(total = assignmentHistory.size, page = page, pageSize = pageSize, history = assignmentHistory))
        }
    }

    override suspend fun agents(): Response<AgentsResponseDto> {
        callLog += "agents"
        return errorOrElse {
            Response.success(AgentsResponseDto(agents = agents))
        }
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

/** Lê o conteúdo de um RequestBody de campo de formulário simples (texto), só para asserção em teste. */
private fun RequestBody.readUtf8(): String {
    val buffer = Buffer()
    writeTo(buffer)
    return buffer.readUtf8()
}
