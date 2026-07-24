package br.com.misticapresentes.painel.auth

import br.com.misticapresentes.painel.network.ApiResult
import br.com.misticapresentes.painel.network.MisticaApi
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.network.apiCall
import br.com.misticapresentes.painel.network.dto.LoginRequestDto
import br.com.misticapresentes.painel.security.SecureSessionStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Fonte única de verdade de autenticação. Reaproveita a autenticação já
 * existente no backend (`backend/user_sync_routes.py`): sessão por cookie
 * HttpOnly, sem token fixo, sem app_token em query string. Nunca guarda
 * senha — o campo é limpo pela UI imediatamente após o envio.
 *
 * A sessão local NUNCA é confiada isoladamente: [restoreSession] sempre
 * revalida contra `GET /api/auth/me` antes de considerar o usuário logado.
 */
class AuthRepository(
    private val api: MisticaApi,
    private val secureSessionStore: SecureSessionStore,
    private val cookieJar: PersistentCookieJar,
) {
    private val _authState = MutableStateFlow<AuthState>(AuthState.Unknown)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    suspend fun restoreSession() {
        if (!secureSessionStore.hasSession()) {
            _authState.value = AuthState.LoggedOut
            return
        }
        when (val result = apiCall { api.me() }) {
            is ApiResult.Success -> {
                val usuario = result.data.usuario
                val login = usuario.login
                val perfil = usuario.perfil
                if (login != null && perfil != null) {
                    secureSessionStore.loggedInUserLogin = login
                    secureSessionStore.loggedInUserProfile = perfil
                    _authState.value = AuthState.LoggedIn(
                        AuthenticatedUser(login = login, nome = usuario.nome ?: login, perfil = perfil),
                    )
                } else {
                    clearLocalSession()
                    _authState.value = AuthState.LoggedOut
                }
            }
            is ApiResult.Failure -> {
                clearLocalSession()
                _authState.value = AuthState.LoggedOut
            }
        }
    }

    suspend fun login(login: String, senha: String): LoginResult {
        val result = apiCall { api.login(LoginRequestDto(login = login.trim(), senha = senha)) }
        return when (result) {
            is ApiResult.Success -> {
                val usuario = result.data.usuario
                val resolvedLogin = usuario.login ?: login.trim()
                val resolvedPerfil = usuario.perfil ?: "vendedor"
                secureSessionStore.loggedInUserLogin = resolvedLogin
                secureSessionStore.loggedInUserProfile = resolvedPerfil
                val authenticatedUser = AuthenticatedUser(
                    login = resolvedLogin,
                    nome = usuario.nome ?: resolvedLogin,
                    perfil = resolvedPerfil,
                )
                _authState.value = AuthState.LoggedIn(authenticatedUser)
                LoginResult.Success(authenticatedUser)
            }
            is ApiResult.Failure -> LoginResult.Failure(result.error.friendlyMessage)
        }
    }

    suspend fun logout() {
        // Best-effort: mesmo que a chamada de rede falhe, a sessão local é
        // sempre encerrada, para que o usuário nunca fique "preso logado" no
        // dispositivo por falha de conectividade.
        runCatching { apiCall { api.logout() } }
        clearLocalSession()
        _authState.value = AuthState.LoggedOut
    }

    /** Chamado pelo interceptor de rede quando qualquer resposta autenticada volta 401. */
    fun onSessionExpired() {
        clearLocalSession()
        _authState.value = AuthState.SessionExpired
    }

    private fun clearLocalSession() {
        secureSessionStore.clearSession()
        cookieJar.clear()
    }
}
