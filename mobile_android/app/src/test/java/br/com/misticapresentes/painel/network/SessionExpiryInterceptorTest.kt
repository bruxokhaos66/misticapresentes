package br.com.misticapresentes.painel.network

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class SessionExpiryInterceptorTest {

    private lateinit var server: MockWebServer

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `401 on non-login endpoint notifies session expired`() {
        var notified = 0
        val client = OkHttpClient.Builder()
            .addInterceptor(SessionExpiryInterceptor { notified++ })
            .build()
        server.enqueue(MockResponse().setResponseCode(401))

        val request = Request.Builder().url(server.url("/api/auth/me")).get().build()
        client.newCall(request).execute()

        assertEquals(1, notified)
    }

    @Test
    fun `401 on login endpoint does not notify session expired`() {
        var notified = 0
        val client = OkHttpClient.Builder()
            .addInterceptor(SessionExpiryInterceptor { notified++ })
            .build()
        server.enqueue(MockResponse().setResponseCode(401))

        val request = Request.Builder()
            .url(server.url("/api/auth/login"))
            .post(ByteArray(0).toRequestBody(null))
            .build()
        client.newCall(request).execute()

        assertEquals(0, notified)
    }
}
