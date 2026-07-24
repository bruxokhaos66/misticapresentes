package br.com.misticapresentes.painel.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import br.com.misticapresentes.painel.atendimento.ui.detail.ConversationViewModel
import br.com.misticapresentes.painel.atendimento.ui.list.AtendimentoListViewModel
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
            AtendimentoListViewModel::class.java -> AtendimentoListViewModel(
                repository = container.atendimentoRepository,
                authRepository = container.authRepository,
                connectivityObserver = container.connectivityObserver,
            ) as T
            else -> throw IllegalArgumentException("ViewModel desconhecida: ${modelClass.name}")
        }
    }
}

/**
 * Fábrica dedicada para [ConversationViewModel]: diferente das demais telas,
 * esta ViewModel recebe um argumento de execução (o id da conversa vindo da
 * rota de navegação), que [MisticaViewModelFactory] não suporta (ela só
 * despacha por `Class`). Mesmo padrão de DI manual, só especializado para
 * este único caso.
 */
class ConversationViewModelFactory(
    private val container: AppContainer,
    private val conversationId: Long,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return when (modelClass) {
            ConversationViewModel::class.java -> ConversationViewModel(
                repository = container.atendimentoRepository,
                conversationId = conversationId,
            ) as T
            else -> throw IllegalArgumentException("ViewModel desconhecida: ${modelClass.name}")
        }
    }
}
