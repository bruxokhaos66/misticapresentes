package br.com.misticapresentes.painel.common

import br.com.misticapresentes.painel.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * Flags de funcionalidade do app. O valor padrão de cada flag vem do
 * BuildConfig (definido por flavor: dev/homolog podem ligar recursos novos
 * para teste, prod nasce conservador). Uma flag local NUNCA concede acesso
 * que o backend negaria: ela só decide se a UI daquela funcionalidade é
 * exibida/habilitada neste build; toda ação continua sendo validada pelo
 * backend (sessão, perfil, CSRF) como qualquer outra chamada de API.
 */
enum class FeatureFlag(val key: String, val defaultValue: Boolean) {
    NEW_AUTH_ENABLED("NEW_AUTH_ENABLED", BuildConfig.DEFAULT_NEW_AUTH_ENABLED),
    LEGACY_WEBVIEW_ENABLED("LEGACY_WEBVIEW_ENABLED", BuildConfig.DEFAULT_LEGACY_WEBVIEW_ENABLED),
    NATIVE_WHATSAPP_ENABLED("NATIVE_WHATSAPP_ENABLED", BuildConfig.DEFAULT_NATIVE_WHATSAPP_ENABLED),
    NATIVE_DASHBOARD_ENABLED("NATIVE_DASHBOARD_ENABLED", BuildConfig.DEFAULT_NATIVE_DASHBOARD_ENABLED),
    PUSH_NOTIFICATIONS_ENABLED("PUSH_NOTIFICATIONS_ENABLED", BuildConfig.DEFAULT_PUSH_NOTIFICATIONS_ENABLED),

    // PR #414 -- sincronização em tempo real (polling), WorkManager e
    // notificações locais da Central de Atendimento. As três nascem
    // DESLIGADAS em todos os flavors (dev/homolog/prod): nenhuma exceção
    // técnica de default `true` em dev nesta PR -- habilite via override
    // local de DataStore para testar. Cada rota/Worker/receiver relevante
    // revalida a flag internamente (nunca só esconde botão na UI).
    REALTIME_SYNC_ENABLED("REALTIME_SYNC_ENABLED", BuildConfig.DEFAULT_REALTIME_SYNC_ENABLED),
    BACKGROUND_SYNC_ENABLED("BACKGROUND_SYNC_ENABLED", BuildConfig.DEFAULT_BACKGROUND_SYNC_ENABLED),
    ATTENDANCE_NOTIFICATIONS_ENABLED("ATTENDANCE_NOTIFICATIONS_ENABLED", BuildConfig.DEFAULT_ATTENDANCE_NOTIFICATIONS_ENABLED),
}

interface FeatureFlagsRepository {
    fun isEnabled(flag: FeatureFlag): Flow<Boolean>
    suspend fun setEnabled(flag: FeatureFlag, enabled: Boolean)
}

/**
 * Implementação padrão apoiada em [AppPreferences] (DataStore, dado NÃO
 * sensível). Em builds de produção, apenas flags cujo default já é `true`
 * podem ser sobrescritas por local override — isto é, esta camada não abre
 * nenhuma funcionalidade nova em produção por conta própria; quem decide o
 * default seguro é o BuildConfig do flavor prod.
 */
class DefaultFeatureFlagsRepository(
    private val appPreferences: AppPreferences,
) : FeatureFlagsRepository {

    override fun isEnabled(flag: FeatureFlag): Flow<Boolean> =
        appPreferences.featureFlagOverride(flag.key).map { override -> override ?: flag.defaultValue }

    override suspend fun setEnabled(flag: FeatureFlag, enabled: Boolean) {
        appPreferences.setFeatureFlagOverride(flag.key, enabled)
    }
}
