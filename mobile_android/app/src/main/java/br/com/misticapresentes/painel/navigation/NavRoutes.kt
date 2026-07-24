package br.com.misticapresentes.painel.navigation

object NavRoutes {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val HOME = "home"
    const val SESSION_EXPIRED = "session_expired"
    const val NO_CONNECTION = "no_connection"

    // Central de Atendimento nativa (PR #412) -- só alcançável a partir de
    // HomeScreen quando FeatureFlag.NATIVE_WHATSAPP_ENABLED está ligada.
    const val ATENDIMENTO_LIST = "atendimento_list"
    const val ATENDIMENTO_DETAIL = "atendimento_detail/{conversationId}"

    fun atendimentoDetail(conversationId: Long) = "atendimento_detail/$conversationId"
}
