package br.com.misticapresentes.painel.common

import android.content.Context

/**
 * Contrato de migração das preferências legadas. Existe como interface para
 * permitir testar ViewModels que disparam a migração (ex.: SplashViewModel)
 * com um fake em memória, sem depender de SharedPreferences/DataStore reais
 * (Robolectric) só para satisfazer essa dependência.
 */
interface LegacyPrefsMigrator {
    suspend fun migrateIfNeeded()
}

/**
 * Migra com segurança as preferências do app legado (Java, pré-#411):
 * `server_url` e `api_token` salvos em SharedPreferences comuns (texto
 * puro), sob o arquivo "mistica_painel_prefs".
 *
 * Regras:
 * - `api_token` NUNCA é reaproveitado como credencial real: o esquema antigo
 *   (`app_token` em query string) não corresponde à autenticação real do
 *   backend (sessão por cookie). O valor antigo é apenas descartado.
 * - `server_url`, se customizada pelo usuário, é preservada apenas como
 *   preferência informativa/local (não sensível) e só tem efeito prático no
 *   flavor dev (onde URL customizada de WebView é permitida).
 * - As SharedPreferences antigas são limpas após a migração, para não deixar
 *   um token/URL órfão residindo em armazenamento não criptografado.
 */
class LegacyPrefsMigration(
    private val context: Context,
    private val appPreferences: AppPreferences,
) : LegacyPrefsMigrator {
    override suspend fun migrateIfNeeded() {
        val legacyPrefs = context.getSharedPreferences(LEGACY_PREFS_NAME, Context.MODE_PRIVATE)
        if (!legacyPrefs.contains(LEGACY_KEY_URL) && !legacyPrefs.contains(LEGACY_KEY_TOKEN)) {
            appPreferences.markLegacyPrefsMigrated()
            return
        }

        // O token legado é intencionalmente descartado (não é uma credencial válida
        // para a autenticação real por sessão). Nada dele é copiado para o
        // armazenamento seguro. A URL customizada legada também é descartada:
        // em produção/homolog a URL vem do BuildConfig; em dev o usuário pode
        // informar uma nova URL local pela tela de configuração legada.
        legacyPrefs.edit().clear().apply()
        appPreferences.markLegacyPrefsMigrated()
    }

    private companion object {
        const val LEGACY_PREFS_NAME = "mistica_painel_prefs"
        const val LEGACY_KEY_URL = "server_url"
        const val LEGACY_KEY_TOKEN = "api_token"
    }
}
