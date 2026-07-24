package br.com.misticapresentes.painel.common

import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class FeatureFlagsTest {

    private val appPreferences = AppPreferences(ApplicationProvider.getApplicationContext())
    private val repository = DefaultFeatureFlagsRepository(appPreferences)

    @Test
    fun `flag without override falls back to its BuildConfig default`() = runTest {
        val enabled = repository.isEnabled(FeatureFlag.NATIVE_WHATSAPP_ENABLED).first()
        assertEquals(FeatureFlag.NATIVE_WHATSAPP_ENABLED.defaultValue, enabled)
    }

    @Test
    fun `local override takes precedence over default`() = runTest {
        repository.setEnabled(FeatureFlag.NATIVE_DASHBOARD_ENABLED, true)
        assertEquals(true, repository.isEnabled(FeatureFlag.NATIVE_DASHBOARD_ENABLED).first())

        repository.setEnabled(FeatureFlag.NATIVE_DASHBOARD_ENABLED, false)
        assertEquals(false, repository.isEnabled(FeatureFlag.NATIVE_DASHBOARD_ENABLED).first())
    }
}
