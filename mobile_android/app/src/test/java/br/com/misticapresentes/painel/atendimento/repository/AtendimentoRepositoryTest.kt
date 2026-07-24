package br.com.misticapresentes.painel.atendimento.repository

import br.com.misticapresentes.painel.atendimento.network.AtendimentoApi
import br.com.misticapresentes.painel.network.ApiError
import br.com.misticapresentes.painel.network.ApiResult
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Testes de integração do [AtendimentoRepository] contra um servidor HTTP
 * real em memória (MockWebServer) -- mesmo padrão já usado em
 * `network/RetryInterceptorTest.kt`/`network/SessionExpiryInterceptorTest.kt`.
 * Nunca acessa rede real nem produção. Cobre o mapeamento de status HTTP via
 * [ApiError.fromHttpCode] (reaproveitado, não duplicado aqui) e os campos
 * dos endpoints reais de `backend/whatsapp_atendimento_routes.py`,
 * `backend/whatsapp_inbox_routes.py` e `backend/whatsapp_catalog_routes.py`.
 */
class AtendimentoRepositoryTest {

    private lateinit var server: MockWebServer
    private lateinit var repository: AtendimentoRepository

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        repository = AtendimentoRepository(buildApi(readTimeoutMillis = 5_000))
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    private fun buildApi(readTimeoutMillis: Long): AtendimentoApi {
        val json = Json { ignoreUnknownKeys = true }
        val client = OkHttpClient.Builder()
            .readTimeout(readTimeoutMillis, TimeUnit.MILLISECONDS)
            .build()
        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
        return retrofit.create(AtendimentoApi::class.java)
    }

    @Test
    fun `queue returns mapped conversations`() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """
                {"ok": true, "total": 1, "page": 1, "page_size": 30, "conversations": [
                    {"id": 10, "status": "open", "queue_status": "waiting", "assigned_user_id": null,
                     "assignment_version": 0, "unread_count": 2, "last_message_at": "2026-07-24T10:00:00",
                     "last_inbound_at": "2026-07-24T10:00:00", "created_at": "2026-07-24T09:00:00",
                     "resolved_at": null, "customer_id": null, "order_id": null,
                     "contact": {"profile_name": "Cliente Teste", "phone_last4": "1234"}}
                ]}
                """.trimIndent(),
            ),
        )

        val result = repository.listQueue(page = 1, pageSize = 30)

        assertTrue(result is ApiResult.Success)
        val page = (result as ApiResult.Success).data
        assertEquals(1, page.items.size)
        assertEquals(10L, page.items[0].id)
        assertEquals("Cliente Teste", page.items[0].profileName)
        assertEquals("1234", page.items[0].phoneLast4)
        assertEquals(2, page.items[0].unreadCount)
        assertEquals("/api/admin/whatsapp/queue?page=1&page_size=30", server.takeRequest().path)
    }

    @Test
    fun `getConversation returns mapped detail`() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """
                {"ok": true, "conversation": {"id": 5, "status": "open", "assigned_admin": null,
                 "unread_count": 0, "last_message_at": null, "last_inbound_at": null, "last_outbound_at": null,
                 "customer_id": null, "order_id": null, "created_at": "2026-07-24T09:00:00",
                 "contact": {"profile_name": "Fulana", "phone_last4": "9876"},
                 "assigned_user_id": 3, "assignment_version": 2, "queue_status": "assigned"}}
                """.trimIndent(),
            ),
        )

        val result = repository.getConversation(5)

        assertTrue(result is ApiResult.Success)
        val conversation = (result as ApiResult.Success).data
        assertEquals(3L, conversation.assignedUserId)
        assertEquals(2, conversation.assignmentVersion)
        assertEquals("assigned", conversation.queueStatus)
    }

    @Test
    fun `getMessages returns mapped history`() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """
                {"ok": true, "messages": [
                    {"id": 1, "conversation_id": 5, "direction": "inbound", "message_type": "text",
                     "text_body": "Oi", "status": null, "sent_by_admin": null,
                     "timestamp_meta": "2026-07-24T09:00:00", "created_at": "2026-07-24T09:00:00"}
                ]}
                """.trimIndent(),
            ),
        )

        val result = repository.getMessages(5, beforeId = null, limit = 50)

        assertTrue(result is ApiResult.Success)
        val messages = (result as ApiResult.Success).data
        assertEquals(1, messages.size)
        assertEquals("inbound", messages[0].direction)
        assertEquals("Oi", messages[0].textBody)
    }

    @Test
    fun `sendText posts idempotency key header and text body`() = runTest {
        server.enqueue(MockResponse().setBody("""{"ok": true, "message_id": 99, "status": "sent"}"""))

        val result = repository.sendText(5, "Olá cliente", assignmentVersion = 1)

        assertTrue(result is ApiResult.Success)
        assertEquals(true, (result as ApiResult.Success).data.ok)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertTrue(request.getHeader("Idempotency-Key")!!.isNotBlank())
        assertTrue(request.body.readUtf8().contains("Olá cliente"))
    }

    @Test
    fun `sendProduct posts product id and idempotency key`() = runTest {
        server.enqueue(MockResponse().setBody("""{"ok": true, "message_id": 100, "status": "sent", "product_id": 7}"""))

        val result = repository.sendProduct(5, productId = 7, assignmentVersion = 1)

        assertTrue(result is ApiResult.Success)
        val data = (result as ApiResult.Success).data
        assertEquals(100L, data.messageId)
        val request = server.takeRequest()
        assertTrue(request.getHeader("Idempotency-Key")!!.isNotBlank())
        assertTrue(request.body.readUtf8().contains("\"product_id\":7"))
    }

    @Test
    fun `claim returns updated conversation`() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """
                {"ok": true, "conversation": {"id": 5, "status": "open", "queue_status": "assigned",
                 "assigned_user_id": 3, "assigned_at": "2026-07-24T10:00:00", "assignment_version": 1,
                 "unread_count": 0, "last_message_at": null, "last_inbound_at": null,
                 "created_at": "2026-07-24T09:00:00", "resolved_at": null, "customer_id": null, "order_id": null,
                 "contact": {"profile_name": "Fulana", "phone_last4": "9876"}}}
                """.trimIndent(),
            ),
        )

        val result = repository.claim(5)

        assertTrue(result is ApiResult.Success)
        assertEquals(3L, (result as ApiResult.Success).data.assignedUserId)
    }

    @Test
    fun `resolve returns updated conversation`() = runTest {
        server.enqueue(
            MockResponse().setBody(
                """
                {"ok": true, "conversation": {"id": 5, "status": "resolved", "queue_status": "resolved",
                 "assigned_user_id": 3, "assignment_version": 2, "unread_count": 0, "last_message_at": null,
                 "last_inbound_at": null, "created_at": "2026-07-24T09:00:00", "resolved_at": "2026-07-24T11:00:00",
                 "customer_id": null, "order_id": null, "contact": {"profile_name": "Fulana", "phone_last4": "9876"}}}
                """.trimIndent(),
            ),
        )

        val result = repository.resolve(5, assignmentVersion = 1)

        assertTrue(result is ApiResult.Success)
        assertEquals("resolved", (result as ApiResult.Success).data.queueStatus)
    }

    @Test
    fun `generic 500 error maps to ServerError`() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))

        val result = repository.listQueue(page = 1, pageSize = 30)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.ServerError)
    }

    @Test
    fun `401 maps to Unauthorized (session expired)`() = runTest {
        server.enqueue(MockResponse().setResponseCode(401))

        val result = repository.getConversation(5)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Unauthorized)
    }

    @Test
    fun `403 maps to Forbidden`() = runTest {
        server.enqueue(MockResponse().setResponseCode(403))

        val result = repository.listAll(page = 1, pageSize = 30)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Forbidden)
    }

    @Test
    fun `404 maps to NotFound`() = runTest {
        server.enqueue(MockResponse().setResponseCode(404))

        val result = repository.getConversation(999)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.NotFound)
    }

    @Test
    fun `409 maps to Conflict for assignment version mismatch`() = runTest {
        server.enqueue(MockResponse().setResponseCode(409))

        val result = repository.resolve(5, assignmentVersion = 0)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Conflict)
    }

    @Test
    fun `429 maps to TooManyRequests`() = runTest {
        server.enqueue(MockResponse().setResponseCode(429))

        val result = repository.sendText(5, "Oi", assignmentVersion = null)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.TooManyRequests)
    }

    @Test
    fun `timeout maps to Timeout`() = runTest {
        val timeoutApi = buildApi(readTimeoutMillis = 200)
        val timeoutRepository = AtendimentoRepository(timeoutApi)
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))

        val result = timeoutRepository.listQueue(page = 1, pageSize = 30)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Timeout)
    }
}
