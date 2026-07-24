package br.com.misticapresentes.painel.common

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
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
        val LAST_KNOWN_UNREAD_TOTAL = intPreferencesKey("attendance_last_known_unread_total")
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

    /**
     * Único dado guardado pela sincronização em background (PR #414): um
     * inteiro (total de não lidas já visto), NUNCA texto de mensagem,
     * telefone ou nome de cliente -- serve só para o Worker saber se a
     * contagem SUBIU desde a última execução, para decidir se dispara uma
     * notificação local. Limpo no logout junto com o resto da sessão (ver
     * [br.com.misticapresentes.painel.auth.AuthRepository]).
     */
    val lastKnownUnreadTotal: Flow<Int> =
        context.dataStore.data.map { it[Keys.LAST_KNOWN_UNREAD_TOTAL] ?: 0 }

    suspend fun setLastKnownUnreadTotal(total: Int) {
        context.dataStore.edit { it[Keys.LAST_KNOWN_UNREAD_TOTAL] = total }
    }

    suspend fun clearLastKnownUnreadTotal() {
        context.dataStore.edit { it.remove(Keys.LAST_KNOWN_UNREAD_TOTAL) }
    }
}
