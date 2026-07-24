package br.com.misticapresentes.painel.network

import br.com.misticapresentes.painel.network.dto.LoginRequestDto
import br.com.misticapresentes.painel.network.dto.LoginResponseDto
import br.com.misticapresentes.painel.network.dto.LogoutResponseDto
import br.com.misticapresentes.painel.network.dto.MeResponseDto
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/**
 * Superfície de API consumida nesta PR: somente autenticação. Endpoints
 * confirmados em `backend/user_sync_routes.py`. Nenhum endpoint novo foi
 * inventado; a Central de Atendimento (fila, conversas, mensagens etc.) fica
 * para a PR #412, reaproveitando este mesmo client Retrofit/OkHttp.
 */
interface MisticaApi {

    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequestDto): Response<LoginResponseDto>

    @POST("api/auth/logout")
    suspend fun logout(): Response<LogoutResponseDto>

    @GET("api/auth/me")
    suspend fun me(): Response<MeResponseDto>
}
