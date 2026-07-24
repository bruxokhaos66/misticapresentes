package br.com.misticapresentes.painel.atendimento.repository

import br.com.misticapresentes.painel.atendimento.model.MediaKind
import br.com.misticapresentes.painel.atendimento.network.AtendimentoApi
import br.com.misticapresentes.painel.network.ApiError
import br.com.misticapresentes.painel.network.ApiResult
import java.io.File
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
 * Testes de [AtendimentoRepository.sendMedia] contra MockWebServer -- mesmo
 * padrão de [AtendimentoRepositoryTest], cobrindo o endpoint multipart de
 * mídia (`POST /conversations/{id}/media`, PR #413).
 */
class AtendimentoRepositoryMediaTest {

    private lateinit var server: MockWebServer
    private lateinit var repository: AtendimentoRepository
    private lateinit var tempFile: File

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        repository = AtendimentoRepository(buildApi(readTimeoutMillis = 5_000))
        tempFile = File.createTempFile("media_test", ".jpg").apply {
            writeBytes(ByteArray(1024) { 1 })
        }
    }

    @After
    fun tearDown() {
        server.shutdown()
        tempFile.delete()
    }

    private fun buildApi(readTimeoutMillis: Long): AtendimentoApi {
        val json = Json { ignoreUnknownKeys = true }
        val client = OkHttpClient.Builder().readTimeout(readTimeoutMillis, TimeUnit.MILLISECONDS).build()
        val retrofit = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
        return retrofit.create(AtendimentoApi::class.java)
    }

    @Test
    fun `sendMedia posts multipart fields and idempotency key`() = runTest {
        server.enqueue(MockResponse().setBody("""{"ok": true, "message_id": 55, "status": "sent"}"""))

        val result = repository.sendMedia(
            conversationId = 5,
            kind = MediaKind.IMAGE,
            file = tempFile,
            mimeType = "image/jpeg",
            caption = "Legenda teste",
            assignmentVersion = 2,
        )

        assertTrue(result is ApiResult.Success)
        assertEquals(55L, (result as ApiResult.Success).data.messageId)

        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/api/admin/whatsapp/conversations/5/media", request.path)
        assertTrue(request.getHeader("Idempotency-Key")!!.isNotBlank())
        val body = request.body.readUtf8()
        assertTrue(body.contains("name=\"media_kind\""))
        assertTrue(body.contains("image"))
        assertTrue(body.contains("name=\"caption\""))
        assertTrue(body.contains("Legenda teste"))
        assertTrue(body.contains("name=\"assignment_version\""))
        assertTrue(body.contains("name=\"file\""))
    }

    @Test
    fun `sendMedia reports upload progress up to completion`() = runTest {
        server.enqueue(MockResponse().setBody("""{"ok": true, "message_id": 56, "status": "sent"}"""))
        val progressValues = mutableListOf<Float>()

        repository.sendMedia(
            conversationId = 5,
            kind = MediaKind.AUDIO,
            file = tempFile,
            mimeType = "audio/mp4",
            caption = null,
            assignmentVersion = null,
            onProgress = { progressValues += it },
        )

        assertTrue(progressValues.isNotEmpty())
        assertEquals(1f, progressValues.last(), 0.001f)
    }

    @Test
    fun `sendMedia soft failure maps to ok=false without ApiError`() = runTest {
        server.enqueue(MockResponse().setBody("""{"ok": false, "message_id": 57, "status": "failed"}"""))

        val result = repository.sendMedia(5, MediaKind.IMAGE, tempFile, "image/jpeg", null, null)

        assertTrue(result is ApiResult.Success)
        assertEquals(false, (result as ApiResult.Success).data.ok)
    }

    @Test
    fun `sendMedia with 422 maps to ValidationFailed (unsupported format or caption on audio)`() = runTest {
        server.enqueue(MockResponse().setResponseCode(422))

        val result = repository.sendMedia(5, MediaKind.AUDIO, tempFile, "audio/mp4", null, null)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.ValidationFailed)
    }

    @Test
    fun `sendMedia with 409 maps to Conflict (stale assignment version)`() = runTest {
        server.enqueue(MockResponse().setResponseCode(409))

        val result = repository.sendMedia(5, MediaKind.IMAGE, tempFile, "image/jpeg", "legenda", 3)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Conflict)
    }

    @Test
    fun `sendMedia with 413 maps to Unknown`() = runTest {
        server.enqueue(MockResponse().setResponseCode(413))

        val result = repository.sendMedia(5, MediaKind.AUDIO, tempFile, "audio/mp4", null, null)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Unknown)
    }

    /**
     * O servidor aceita a conexão mas nunca responde -- com um client de
     * readTimeout curto, isso força um `SocketTimeoutException` real do
     * OkHttp (não simulado), exercitando o mesmo mapeamento de `apiCall`
     * (network/ApiCall.kt) que qualquer outro upload de mídia usaria em
     * produção numa rede lenta/instável.
     */
    @Test
    fun `sendMedia times out when the server never responds, mapping to ApiError Timeout`() = runTest {
        val shortTimeoutRepository = AtendimentoRepository(buildApi(readTimeoutMillis = 200))
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))

        val result = shortTimeoutRepository.sendMedia(5, MediaKind.IMAGE, tempFile, "image/jpeg", null, null)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.Timeout)
    }

    /**
     * Conexão derrubada logo no início (queda de rede real, não um código
     * HTTP de erro) -- gera uma `IOException` que não é `SocketTimeoutException`,
     * mapeada por `apiCall` para `ApiError.NoConnection`.
     */
    @Test
    fun `sendMedia surfaces a real network disconnect as ApiError NoConnection`() = runTest {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))

        val result = repository.sendMedia(5, MediaKind.AUDIO, tempFile, "audio/mp4", null, null)

        assertTrue(result is ApiResult.Failure)
        assertTrue((result as ApiResult.Failure).error is ApiError.NoConnection)
    }
}
