package br.com.misticapresentes.painel.common

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "mistica_prefs")

/**
 * Armazenamento de dados NÃO sensíveis: ambiente escolhido (informativo),
 * overrides locais de feature flag, última tela e flag de migração das
 * preferências legadas. Nenhuma credencial, sessão ou token entra aqui —
 * isso é responsabilidade de [br.com.misticapresentes.painel.security.SecureStorage].
 */
class AppPreferences(private val context: Context) {

    private object Keys {
        val LEGACY_PREFS_MIGRATED = booleanPreferencesKey("legacy_prefs_migrated")
        val LAST_SCREEN_ROUTE = stringPreferencesKey("last_screen_route")
        fun featureFlagKey(key: String) = booleanPreferencesKey("flag_$key")
    }

    val legacyPrefsMigrated: Flow<Boolean> =
        context.dataStore.data.map { it[Keys.LEGACY_PREFS_MIGRATED] ?: false }

    suspend fun markLegacyPrefsMigrated() {
        context.dataStore.edit { it[Keys.LEGACY_PREFS_MIGRATED] = true }
    }

    val lastScreenRoute: Flow<String?> =
        context.dataStore.data.map { it[Keys.LAST_SCREEN_ROUTE] }

    suspend fun setLastScreenRoute(route: String) {
        context.dataStore.edit { it[Keys.LAST_SCREEN_ROUTE] = route }
    }

    fun featureFlagOverride(key: String): Flow<Boolean?> =
        context.dataStore.data.map { it[Keys.featureFlagKey(key)] }

    suspend fun setFeatureFlagOverride(key: String, enabled: Boolean) {
        context.dataStore.edit { it[Keys.featureFlagKey(key)] = enabled }
    }
}
