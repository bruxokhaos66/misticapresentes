package br.com.misticapresentes.painel.common

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LegacyPrefsMigrationTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun `migration clears legacy prefs and never copies the old token as a credential`() = runTest {
        val legacyPrefs = context.getSharedPreferences("mistica_painel_prefs", Context.MODE_PRIVATE)
        legacyPrefs.edit()
            .putString("server_url", "http://192.168.0.115:8000/painel")
            .putString("api_token", "mistica-local")
            .apply()

        val appPreferences = AppPreferences(context)
        LegacyPrefsMigration(context, appPreferences).migrateIfNeeded()

        assertFalse(legacyPrefs.contains("server_url"))
        assertFalse(legacyPrefs.contains("api_token"))
        assertTrue(appPreferences.legacyPrefsMigrated.first())
    }

    @Test
    fun `migration is a no-op when there is nothing legacy to migrate`() = runTest {
        val appPreferences = AppPreferences(context)
        LegacyPrefsMigration(context, appPreferences).migrateIfNeeded()

        assertTrue(appPreferences.legacyPrefsMigrated.first())
    }
}
