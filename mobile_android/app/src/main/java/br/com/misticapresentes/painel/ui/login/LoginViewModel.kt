package br.com.misticapresentes.painel.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.auth.LoginResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class LoginUiState(
    val login: String = "",
    val senha: String = "",
    val isPasswordVisible: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val loginSucceeded: Boolean = false,
)

class LoginViewModel(private val authRepository: AuthRepository) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState.asStateFlow()

    fun onLoginChanged(value: String) {
        _uiState.value = _uiState.value.copy(login = value, errorMessage = null)
    }

    fun onSenhaChanged(value: String) {
        _uiState.value = _uiState.value.copy(senha = value, errorMessage = null)
    }

    fun onTogglePasswordVisibility() {
        _uiState.value = _uiState.value.copy(isPasswordVisible = !_uiState.value.isPasswordVisible)
    }

    fun submit() {
        val state = _uiState.value
        // Bloqueio de clique duplo: um envio em andamento ignora novos toques.
        if (state.isLoading) return
        if (state.login.isBlank() || state.senha.isBlank()) {
            _uiState.value = state.copy(errorMessage = "Informe usuário e senha.")
            return
        }

        _uiState.value = state.copy(isLoading = true, errorMessage = null)
        viewModelScope.launch {
            when (val result = authRepository.login(state.login, state.senha)) {
                is LoginResult.Success -> {
                    // A senha nunca fica retida em memória além do necessário.
                    _uiState.value = _uiState.value.copy(isLoading = false, senha = "", loginSucceeded = true)
                }
                is LoginResult.Failure -> {
                    _uiState.value = _uiState.value.copy(isLoading = false, senha = "", errorMessage = result.message)
                }
            }
        }
    }
}
