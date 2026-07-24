package br.com.misticapresentes.painel.auth

/** Usuário autenticado, apenas com o que a UI precisa exibir. */
data class AuthenticatedUser(
    val login: String,
    val nome: String,
    val perfil: String,
)

sealed class AuthState {
    data object Unknown : AuthState()
    data object LoggedOut : AuthState()
    data class LoggedIn(val user: AuthenticatedUser) : AuthState()
    data object SessionExpired : AuthState()
}

sealed class LoginResult {
    data class Success(val user: AuthenticatedUser) : LoginResult()
    data class Failure(val message: String) : LoginResult()
}
