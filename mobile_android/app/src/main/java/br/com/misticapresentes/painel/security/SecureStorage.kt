package br.com.misticapresentes.painel.security

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Armazenamento de dados SENSÍVEIS: cookie de sessão e identificação básica
 * do usuário autenticado. Apoiado em [EncryptedSharedPreferences] com chave
 * gerenciada pelo Android Keystore (AES256-GCM), nunca em texto puro.
 *
 * Não guarda senha em nenhuma hipótese. Não guarda mensagens.
 */
class SecureStorage(context: Context) : SecureSessionStore {

    private val appContext = context.applicationContext

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        EncryptedSharedPreferences.create(
            appContext,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    override var loggedInUserLogin: String?
        get() = prefs.getString(KEY_USER_LOGIN, null)
        set(value) {
            prefs.edit().apply {
                if (value.isNullOrBlank()) remove(KEY_USER_LOGIN) else putString(KEY_USER_LOGIN, value)
            }.apply()
        }

    override var loggedInUserProfile: String?
        get() = prefs.getString(KEY_USER_PROFILE, null)
        set(value) {
            prefs.edit().apply {
                if (value.isNullOrBlank()) remove(KEY_USER_PROFILE) else putString(KEY_USER_PROFILE, value)
            }.apply()
        }

    /**
     * Cookie de sessão (`mistica_painel_sessao`) serializado, criptografado
     * no Keystore. É este cookie que de fato autentica as chamadas à API,
     * persistido/lido pelo [br.com.misticapresentes.painel.network.PersistentCookieJar].
     */
    override var cookieJarState: String?
        get() = prefs.getString(KEY_COOKIE_JAR, null)
        set(value) {
            prefs.edit().apply {
                if (value.isNullOrBlank()) remove(KEY_COOKIE_JAR) else putString(KEY_COOKIE_JAR, value)
            }.apply()
        }

    override fun hasSession(): Boolean = !cookieJarState.isNullOrBlank()

    /** Limpa toda a sessão local. Usado no logout e na expiração de sessão. */
    override fun clearSession() {
        prefs.edit()
            .remove(KEY_USER_LOGIN)
            .remove(KEY_USER_PROFILE)
            .remove(KEY_COOKIE_JAR)
            .apply()
    }

    private companion object {
        const val FILE_NAME = "mistica_secure_prefs"
        const val KEY_USER_LOGIN = "user_login"
        const val KEY_USER_PROFILE = "user_profile"
        const val KEY_COOKIE_JAR = "cookie_jar_state"
    }
}
