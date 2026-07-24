package br.com.misticapresentes.painel.network

/** Resultado padronizado de qualquer chamada de API do app. */
sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Failure(val error: ApiError) : ApiResult<Nothing>()
}

/**
 * Erros de API normalizados, com mensagem amigável já pronta para exibição.
 * Nunca inclui corpo bruto da resposta, cookies ou headers de autenticação.
 */
sealed class ApiError(val friendlyMessage: String) {
    data object Unauthorized : ApiError("Sessão expirada. Faça login novamente.")
    data object Forbidden : ApiError("Você não tem permissão para esta ação.")
    data object NotFound : ApiError("Recurso não encontrado.")
    data object Conflict : ApiError("Esta ação já foi realizada ou está em conflito com o estado atual.")
    data object ValidationFailed : ApiError("Dados inválidos. Confira as informações e tente novamente.")
    data object TooManyRequests : ApiError("Muitas tentativas em pouco tempo. Aguarde um momento.")
    data object ServerError : ApiError("O servidor da Mística está indisponível no momento. Tente novamente em instantes.")
    data object Timeout : ApiError("A conexão demorou demais para responder. Verifique sua internet.")
    data object NoConnection : ApiError("Sem conexão com a internet.")
    data class Unknown(val code: Int?) : ApiError("Não foi possível completar a ação agora. Tente novamente.")

    companion object {
        fun fromHttpCode(code: Int): ApiError = when (code) {
            401 -> Unauthorized
            403 -> Forbidden
            404 -> NotFound
            409 -> Conflict
            422 -> ValidationFailed
            429 -> TooManyRequests
            in 500..599 -> ServerError
            else -> Unknown(code)
        }
    }
}
