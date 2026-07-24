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

class RetryInterceptorTest {

    private lateinit var server: MockWebServer
    private lateinit var client: OkHttpClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = OkHttpClient.Builder().addInterceptor(RetryInterceptor(maxRetries = 2)).build()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `GET is retried on 500 until success`() {
        server.enqueue(MockResponse().setResponseCode(500))
        server.enqueue(MockResponse().setResponseCode(200).setBody("ok"))

        val request = Request.Builder().url(server.url("/status")).get().build()
        val response = client.newCall(request).execute()

        assertEquals(200, response.code)
        assertEquals(2, server.requestCount)
    }

    @Test
    fun `POST is never retried on 500`() {
        server.enqueue(MockResponse().setResponseCode(500))

        val request = Request.Builder().url(server.url("/send")).post(
            ByteArray(0).toRequestBody(null),
        ).build()
        val response = client.newCall(request).execute()

        assertEquals(500, response.code)
        assertEquals(1, server.requestCount)
    }
}
