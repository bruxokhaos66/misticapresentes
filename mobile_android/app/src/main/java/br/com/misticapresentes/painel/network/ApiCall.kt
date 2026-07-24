package br.com.misticapresentes.painel.network

import java.io.IOException
import java.net.SocketTimeoutException
import retrofit2.Response

/**
 * Executa uma chamada Retrofit e normaliza o resultado em [ApiResult],
 * mapeando exceções de rede e códigos HTTP para erros amigáveis (§5 da
 * fundação). Nenhuma mensagem de erro aqui expõe corpo bruto da resposta.
 */
suspend fun <T> apiCall(block: suspend () -> Response<T>): ApiResult<T> {
    return try {
        val response = block()
        val body = response.body()
        if (response.isSuccessful && body != null) {
            ApiResult.Success(body)
        } else {
            ApiResult.Failure(ApiError.fromHttpCode(response.code()))
        }
    } catch (timeout: SocketTimeoutException) {
        ApiResult.Failure(ApiError.Timeout)
    } catch (io: IOException) {
        ApiResult.Failure(ApiError.NoConnection)
    }
}
