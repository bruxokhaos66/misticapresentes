package br.com.misticapresentes.painel.network

import java.io.IOException
import okhttp3.Interceptor
import okhttp3.Response

/**
 * Retry automático SOMENTE para métodos seguros e idempotentes (GET/HEAD),
 * e somente diante de falha de rede ou erro 5xx — nunca para POST/PUT/PATCH
 * (ex.: enviar mensagem/mídia), onde não há garantia de idempotência e um
 * retry poderia duplicar a ação no backend.
 */
class RetryInterceptor(private val maxRetries: Int = 2) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.method != "GET" && request.method != "HEAD") {
            return chain.proceed(request)
        }

        var attempt = 0
        var lastException: IOException? = null
        while (attempt <= maxRetries) {
            try {
                val response = chain.proceed(request)
                if (response.code < 500 || attempt == maxRetries) {
                    return response
                }
                response.close()
            } catch (io: IOException) {
                lastException = io
                if (attempt == maxRetries) throw io
            }
            attempt++
        }
        throw lastException ?: IOException("Falha de rede após $maxRetries tentativas")
    }
}
