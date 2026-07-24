package br.com.misticapresentes.painel.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import br.com.misticapresentes.painel.ui.home.HomeViewModel
import br.com.misticapresentes.painel.ui.login.LoginViewModel
import br.com.misticapresentes.painel.ui.splash.SplashViewModel

/** Fábrica simples de ViewModels a partir do [AppContainer] (sem Hilt nesta PR). */
class MisticaViewModelFactory(private val container: AppContainer) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return when (modelClass) {
            SplashViewModel::class.java -> SplashViewModel(
                authRepository = container.authRepository,
                connectivityObserver = container.connectivityObserver,
                legacyPrefsMigration = container.legacyPrefsMigration,
                featureFlagsRepository = container.featureFlagsRepository,
            ) as T
            LoginViewModel::class.java -> LoginViewModel(container.authRepository) as T
            HomeViewModel::class.java -> HomeViewModel(
                authRepository = container.authRepository,
                connectivityObserver = container.connectivityObserver,
                featureFlagsRepository = container.featureFlagsRepository,
            ) as T
            else -> throw IllegalArgumentException("ViewModel desconhecida: ${modelClass.name}")
        }
    }
}
