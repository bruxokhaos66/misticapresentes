package br.com.misticapresentes.painel.network

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
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .addInterceptor(AuthInterceptor(httpUrl))
            .addInterceptor(RetryInterceptor())
            .addInterceptor(SessionExpiryInterceptor(sessionExpiredNotifier))
            // O interceptor de log fica por último para enxergar os headers já
            // finais, mas continua sanitizado independentemente da ordem.
            .addInterceptor(loggingInterceptor)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(httpUrl)
            .client(okHttpClient)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        return retrofit.create(MisticaApi::class.java)
    }
}
