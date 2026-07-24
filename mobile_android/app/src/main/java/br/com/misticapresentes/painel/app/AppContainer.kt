package br.com.misticapresentes.painel.app

import android.content.Context
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.common.AndroidConnectivityObserver
import br.com.misticapresentes.painel.common.AppPreferences
import br.com.misticapresentes.painel.common.ConnectivityObserver
import br.com.misticapresentes.painel.common.DefaultFeatureFlagsRepository
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.common.LegacyPrefsMigration
import br.com.misticapresentes.painel.network.ApiClient
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.security.SecureSessionStore
import br.com.misticapresentes.painel.security.SecureStorage

/**
 * Container de injeção de dependência manual e simples (sem Hilt/Koin nesta
 * PR, para manter a fundação enxuta). Cada dependência é criada uma única
 * vez e reaproveitada — nada aqui duplica regra de negócio do backend, é
 * apenas fiação (wiring) de infraestrutura do app.
 */
class AppContainer(context: Context) {

    val appPreferences = AppPreferences(context)
    val featureFlagsRepository: FeatureFlagsRepository = DefaultFeatureFlagsRepository(appPreferences)
    val connectivityObserver: ConnectivityObserver = AndroidConnectivityObserver(context)
    val legacyPrefsMigration = LegacyPrefsMigration(context, appPreferences)

    val secureSessionStore: SecureSessionStore = SecureStorage(context)
    private val cookieJar = PersistentCookieJar(secureSessionStore)

    val authRepository: AuthRepository by lazy {
        AuthRepository(
            api = ApiClient.create(
                secureSessionStore = secureSessionStore,
                sessionExpiredNotifier = { authRepositoryRef?.onSessionExpired() },
            ),
            secureSessionStore = secureSessionStore,
            cookieJar = cookieJar,
        ).also { authRepositoryRef = it }
    }

    // Referência auxiliar apenas para permitir que o interceptor de rede
    // (criado antes do AuthRepository, pois o client HTTP é uma dependência
    // dele) notifique sessão expirada sem depender de um Flow global estático.
    private var authRepositoryRef: AuthRepository? = null
}
