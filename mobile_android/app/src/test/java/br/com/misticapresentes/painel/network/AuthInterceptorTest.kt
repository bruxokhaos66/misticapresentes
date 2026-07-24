package br.com.misticapresentes.painel.network

import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class AuthInterceptorTest {

    private lateinit var server: MockWebServer
    private lateinit var client: OkHttpClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(server.url("/").toString().toHttpUrl()))
            .build()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `POST requests receive Origin header matching base URL`() {
        server.enqueue(MockResponse().setResponseCode(200))
        val request = Request.Builder()
            .url(server.url("/api/admin/whatsapp/conversations/1/messages"))
            .post(ByteArray(0).toRequestBody(null))
            .build()

        client.newCall(request).execute()

        val recorded = server.takeRequest()
        assertEquals("http://127.0.0.1:${server.port}", recorded.getHeader("Origin"))
    }

    @Test
    fun `GET requests do not receive Origin header`() {
        server.enqueue(MockResponse().setResponseCode(200))
        val request = Request.Builder().url(server.url("/api/auth/me")).get().build()

        client.newCall(request).execute()

        val recorded = server.takeRequest()
        assertNull(recorded.getHeader("Origin"))
    }
}
