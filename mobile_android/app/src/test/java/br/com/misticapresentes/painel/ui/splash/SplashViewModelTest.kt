package br.com.misticapresentes.painel.ui.splash

import androidx.test.core.app.ApplicationProvider
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.common.AppPreferences
import br.com.misticapresentes.painel.common.DefaultFeatureFlagsRepository
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.LegacyPrefsMigration
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
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
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric só é necessário aqui para [AppPreferences]/[LegacyPrefsMigration]
 * (DataStore/SharedPreferences reais). A conectividade usa [FakeConnectivityObserver],
 * então o resultado do teste nunca depende do estado de rede do executor de CI.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
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
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val appPreferences = AppPreferences(context)
        val featureFlagsRepository = DefaultFeatureFlagsRepository(appPreferences)
        featureFlagsRepository.setEnabled(FeatureFlag.NEW_AUTH_ENABLED, false)

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
            legacyPrefsMigration = LegacyPrefsMigration(context, appPreferences),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoLegacyOnly, viewModel.destination.value)
    }

    @Test
    fun `with NEW_AUTH_ENABLED on and no session, splash goes to login`() = runTest {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val appPreferences = AppPreferences(context)
        val featureFlagsRepository = DefaultFeatureFlagsRepository(appPreferences)
        featureFlagsRepository.setEnabled(FeatureFlag.NEW_AUTH_ENABLED, true)

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
            legacyPrefsMigration = LegacyPrefsMigration(context, appPreferences),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoLogin, viewModel.destination.value)
    }

    @Test
    fun `with NEW_AUTH_ENABLED on and offline, splash goes to no-connection`() = runTest {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val appPreferences = AppPreferences(context)
        val featureFlagsRepository = DefaultFeatureFlagsRepository(appPreferences)
        featureFlagsRepository.setEnabled(FeatureFlag.NEW_AUTH_ENABLED, true)

        val viewModel = SplashViewModel(
            authRepository = AuthRepository(FakeMisticaApi(), FakeSecureSessionStore(), PersistentCookieJar(FakeSecureSessionStore())),
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = false),
            legacyPrefsMigration = LegacyPrefsMigration(context, appPreferences),
            featureFlagsRepository = featureFlagsRepository,
        )

        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(SplashDestination.GoNoConnection, viewModel.destination.value)
    }
}
