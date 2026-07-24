package br.com.misticapresentes.painel.network.dto

import kotlinx.serialization.Serializable

/**
 * DTOs para os endpoints reais de autenticação do backend
 * (`backend/user_sync_routes.py`): POST /api/auth/login, POST /api/auth/logout,
 * GET /api/auth/me. A sessão em si trafega apenas pelo cookie HttpOnly
 * `mistica_painel_sessao` — nenhum token aparece no corpo da resposta.
 */
@Serializable
data class LoginRequestDto(
    val login: String,
    val senha: String,
)

@Serializable
data class UsuarioDto(
    val id: Long? = null,
    val nome: String? = null,
    val login: String? = null,
    val perfil: String? = null,
)

@Serializable
data class LoginResponseDto(
    val status: String,
    val usuario: UsuarioDto,
)

@Serializable
data class LogoutResponseDto(
    val status: String,
    val mensagem: String? = null,
)

@Serializable
data class MeResponseDto(
    val status: String,
    val usuario: UsuarioDto,
)
