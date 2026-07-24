package br.com.misticapresentes.painel.common

import br.com.misticapresentes.painel.BuildConfig

/**
 * Ambiente de execução do app, derivado do flavor de build (dev/homolog/prod).
 * Nunca é escolhido em runtime por texto livre: vem sempre do BuildConfig.
 */
enum class Environment(val label: String) {
    DEV("DEV"),
    HOMOLOG("HOMOLOGAÇÃO"),
    PROD("PRODUÇÃO");

    companion object {
        fun current(): Environment = when (BuildConfig.ENVIRONMENT_NAME) {
            "dev" -> DEV
            "homolog" -> HOMOLOG
            else -> PROD
        }
    }
}

object EnvironmentConfig {
    val current: Environment get() = Environment.current()
    val baseUrl: String get() = BuildConfig.BASE_URL
    val legacyPanelUrl: String get() = BuildConfig.LEGACY_PANEL_URL
    val allowLocalHttp: Boolean get() = BuildConfig.ALLOW_LOCAL_HTTP
    val allowCustomLegacyUrl: Boolean get() = BuildConfig.ALLOW_CUSTOM_LEGACY_URL
    val verboseNetworkLogs: Boolean get() = BuildConfig.VERBOSE_NETWORK_LOGS
}
