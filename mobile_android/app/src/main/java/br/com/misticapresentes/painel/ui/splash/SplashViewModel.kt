package br.com.misticapresentes.painel.ui.splash

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.common.LegacyPrefsMigration
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

sealed class SplashDestination {
    data object Loading : SplashDestination()
    data object GoLogin : SplashDestination()
    data object GoHome : SplashDestination()
    data object GoNoConnection : SplashDestination()

    /**
     * Quando NEW_AUTH_ENABLED está desligada (padrão de produção nesta PR),
     * o app entra direto no painel legado, preservando exatamente o
     * comportamento anterior — a fundação nova fica pronta, mas desligada
     * por padrão em produção, garantindo rollback trivial (só a flag).
     */
    data object GoLegacyOnly : SplashDestination()
}

class SplashViewModel(
    private val authRepository: AuthRepository,
    private val connectivityObserver: ConnectivityObserver,
    private val legacyPrefsMigration: LegacyPrefsMigration,
    private val featureFlagsRepository: FeatureFlagsRepository,
) : ViewModel() {

    private val _destination = MutableStateFlow<SplashDestination>(SplashDestination.Loading)
    val destination: StateFlow<SplashDestination> = _destination.asStateFlow()

    init {
        viewModelScope.launch {
            legacyPrefsMigration.migrateIfNeeded()

            val newAuthEnabled = featureFlagsRepository.isEnabled(FeatureFlag.NEW_AUTH_ENABLED).first()
            if (!newAuthEnabled) {
                _destination.value = SplashDestination.GoLegacyOnly
                return@launch
            }

            if (!connectivityObserver.isOnlineNow()) {
                _destination.value = SplashDestination.GoNoConnection
                return@launch
            }

            authRepository.restoreSession()
            _destination.value = when (authRepository.authState.value) {
                is AuthState.LoggedIn -> SplashDestination.GoHome
                else -> SplashDestination.GoLogin
            }
        }
    }
}
