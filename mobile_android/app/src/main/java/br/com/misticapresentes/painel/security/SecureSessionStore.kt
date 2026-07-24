package br.com.misticapresentes.painel.security

/**
 * Contrato de armazenamento seguro de sessão. Existe como interface para que
 * o restante do app (ex.: AuthRepository) possa ser testado em JVM puro com
 * um fake, sem depender do Android Keystore real (que não está disponível
 * fora de um dispositivo/emulador). A implementação real é [SecureStorage],
 * apoiada em EncryptedSharedPreferences/Keystore.
 */
interface SecureSessionStore {
    var cookieJarState: String?
    var loggedInUserLogin: String?
    var loggedInUserProfile: String?
    fun hasSession(): Boolean
    fun clearSession()
}
