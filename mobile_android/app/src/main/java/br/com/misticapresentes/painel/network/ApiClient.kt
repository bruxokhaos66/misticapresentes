package br.com.misticapresentes.painel.network

import br.com.misticapresentes.painel.atendimento.network.AtendimentoApi
import br.com.misticapresentes.painel.common.EnvironmentConfig
import br.com.misticapresentes.painel.security.SecureSessionStore
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * Monta o client HTTP único do app: timeouts explícitos, cookie jar
 * persistente e criptografado, header de Origin para passar na defesa CSRF
 * do backend, notificação central de sessão expirada, retry restrito a
 * GET/HEAD e log sanitizado (nunca corpo, cookie ou Authorization) apenas em
 * dev/homolog.
 */
object ApiClient {

    private val json = Json { ignoreUnknownKeys = true }

    fun create(
        secureSessionStore: SecureSessionStore,
        sessionExpiredNotifier: SessionExpiredNotifier,
        baseUrl: String = EnvironmentConfig.baseUrl,
        verboseLogs: Boolean = EnvironmentConfig.verboseNetworkLogs,
    ): MisticaApi {
        return buildRetrofit(secureSessionStore, sessionExpiredNotifier, baseUrl, verboseLogs)
            .create(MisticaApi::class.java)
    }

    /**
     * Cria a interface irmã da Central de Atendimento (PR #412) reaproveitando
     * exatamente a mesma construção de OkHttpClient/Retrofit acima (cookie de
     * sessão, Origin/CSRF, retry, sessão expirada e log sanitizado) -- nenhum
     * endpoint novo de infraestrutura, só uma segunda interface Retrofit sobre
     * o mesmo client HTTP autenticado por cookie.
     */
    fun createAtendimentoApi(
        secureSessionStore: SecureSessionStore,
        sessionExpiredNotifier: SessionExpiredNotifier,
        baseUrl: String = EnvironmentConfig.baseUrl,
        verboseLogs: Boolean = EnvironmentConfig.verboseNetworkLogs,
    ): AtendimentoApi {
        return buildRetrofit(secureSessionStore, sessionExpiredNotifier, baseUrl, verboseLogs)
            .create(AtendimentoApi::class.java)
    }

    /**
     * Variante de [createAtendimentoApi] com timeouts maiores, usada só para
     * o upload de mídia (imagem/áudio, PR #413 -- `POST .../media`), que pode
     * levar bem mais que os 20s padrão em rede móvel lenta. Mesma
     * infraestrutura (cookie de sessão, Origin/CSRF, retry, sessão expirada,
     * log sanitizado) -- nenhum endpoint novo, só um client HTTP irmão com
     * timeout de escrita maior.
     */
    fun createAtendimentoMediaApi(
        secureSessionStore: SecureSessionStore,
        sessionExpiredNotifier: SessionExpiredNotifier,
        baseUrl: String = EnvironmentConfig.baseUrl,
        verboseLogs: Boolean = EnvironmentConfig.verboseNetworkLogs,
    ): AtendimentoApi {
        return buildRetrofit(
            secureSessionStore, sessionExpiredNotifier, baseUrl, verboseLogs,
            connectTimeoutSeconds = 20, readTimeoutSeconds = 60, writeTimeoutSeconds = 90,
        ).create(AtendimentoApi::class.java)
    }

    private fun buildRetrofit(
        secureSessionStore: SecureSessionStore,
        sessionExpiredNotifier: SessionExpiredNotifier,
        baseUrl: String,
        verboseLogs: Boolean,
        connectTimeoutSeconds: Long = 15,
        readTimeoutSeconds: Long = 20,
        writeTimeoutSeconds: Long = 20,
    ): Retrofit {
        val httpUrl = baseUrl.toHttpUrl()
        val cookieJar = PersistentCookieJar(secureSessionStore)

        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = if (verboseLogs) HttpLoggingInterceptor.Level.HEADERS else HttpLoggingInterceptor.Level.NONE
            redactHeader("Cookie")
            redactHeader("Set-Cookie")
            redactHeader("Authorization")
            redactHeader("X-Mistica-Api-Key")
        }

        val okHttpClient = OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .connectTimeout(connectTimeoutSeconds, TimeUnit.SECONDS)
            .readTimeout(readTimeoutSeconds, TimeUnit.SECONDS)
            .writeTimeout(writeTimeoutSeconds, TimeUnit.SECONDS)
            .addInterceptor(AuthInterceptor(httpUrl))
            .addInterceptor(RetryInterceptor())
            .addInterceptor(SessionExpiryInterceptor(sessionExpiredNotifier))
            // O interceptor de log fica por último para enxergar os headers já
            // finais, mas continua sanitizado independentemente da ordem.
            .addInterceptor(loggingInterceptor)
            .build()

        return Retrofit.Builder()
            .baseUrl(httpUrl)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
    }
}
