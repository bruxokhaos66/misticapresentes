package br.com.misticapresentes.painel.ui.splash

import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
import br.com.misticapresentes.painel.testutil.FakeFeatureFlagsRepository
import br.com.misticapresentes.painel.testutil.FakeLegacyPrefsMigration
import br.com.misticapresentes.painel.testutil.FakeMisticaApi
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Totalmente baseado em fakes em memória (sessão, conectividade, feature
 * flags e migração legada) — nenhuma dependência de Context/Robolectric ou
 * de I/O real (SharedPreferences/DataStore), então o resultado nunca
 * depende de timing assíncrono real fora do TestDispatcher controlado.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class SplashViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `with NEW_AUTH_ENABLED off, splash goes straight to legacy-only`() = runTest {
        // Simula o default de produção desta PR: nova autenticação desligada.
        val featureFlagsRepository = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NEW_AUTH_ENABLED to false))

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
            legacyPrefsMigration = FakeLegacyPrefsMigration(),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoLegacyOnly, viewModel.destination.value)
    }

    @Test
    fun `with NEW_AUTH_ENABLED on and no session, splash goes to login`() = runTest {
        val featureFlagsRepository = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NEW_AUTH_ENABLED to true))

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
            legacyPrefsMigration = FakeLegacyPrefsMigration(),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoLogin, viewModel.destination.value)
    }

    @Test
    fun `with NEW_AUTH_ENABLED on and offline, splash goes to no-connection`() = runTest {
        val featureFlagsRepository = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NEW_AUTH_ENABLED to true))

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = false),
            legacyPrefsMigration = FakeLegacyPrefsMigration(),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoNoConnection, viewModel.destination.value)
    }
}
