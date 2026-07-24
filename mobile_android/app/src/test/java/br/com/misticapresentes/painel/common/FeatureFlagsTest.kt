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

    // -------- PR #414: sincronização/WorkManager/notificações --------

    @Test
    fun `sync notifications and background flags default to false regardless of flavor`() = runTest {
        assertEquals(false, FeatureFlag.REALTIME_SYNC_ENABLED.defaultValue)
        assertEquals(false, FeatureFlag.BACKGROUND_SYNC_ENABLED.defaultValue)
        assertEquals(false, FeatureFlag.ATTENDANCE_NOTIFICATIONS_ENABLED.defaultValue)
        // A flag legada de WhatsApp nativo permanece desligada por padrão --
        // esta PR não a liga em nenhum flavor.
        assertEquals(false, FeatureFlag.NATIVE_WHATSAPP_ENABLED.defaultValue)
    }

    @Test
    fun `each new PR 414 flag can be overridden locally and read back`() = runTest {
        for (flag in listOf(
            FeatureFlag.REALTIME_SYNC_ENABLED,
            FeatureFlag.BACKGROUND_SYNC_ENABLED,
            FeatureFlag.ATTENDANCE_NOTIFICATIONS_ENABLED,
        )) {
            repository.setEnabled(flag, true)
            assertEquals(true, repository.isEnabled(flag).first())
            repository.setEnabled(flag, false)
            assertEquals(false, repository.isEnabled(flag).first())
        }
    }
}
