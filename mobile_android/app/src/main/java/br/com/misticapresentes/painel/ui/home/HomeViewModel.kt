package br.com.misticapresentes.painel.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class HomeUiState(
    val userName: String = "",
    val userProfile: String = "",
    val isOnline: Boolean = true,
    val nativeWhatsAppEnabled: Boolean = false,
    val nativeDashboardEnabled: Boolean = false,
    val loggedOut: Boolean = false,
)

class HomeViewModel(
    private val authRepository: AuthRepository,
    connectivityObserver: ConnectivityObserver,
    featureFlagsRepository: FeatureFlagsRepository,
) : ViewModel() {

    val uiState: StateFlow<HomeUiState> = combine(
        authRepository.authState,
        connectivityObserver.observe(),
        featureFlagsRepository.isEnabled(FeatureFlag.NATIVE_WHATSAPP_ENABLED),
        featureFlagsRepository.isEnabled(FeatureFlag.NATIVE_DASHBOARD_ENABLED),
    ) { state, online, whatsAppEnabled, dashboardEnabled ->
        val user = (state as? AuthState.LoggedIn)?.user
        HomeUiState(
            userName = user?.nome.orEmpty(),
            userProfile = user?.perfil.orEmpty(),
            isOnline = online,
            nativeWhatsAppEnabled = whatsAppEnabled,
            nativeDashboardEnabled = dashboardEnabled,
            loggedOut = state !is AuthState.LoggedIn,
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, HomeUiState())

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }
}
