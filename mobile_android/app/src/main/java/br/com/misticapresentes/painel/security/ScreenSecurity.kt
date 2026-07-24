package br.com.misticapresentes.painel.security

import android.app.Activity
import android.view.WindowManager

/**
 * Mecanismo reutilizável de FLAG_SECURE para telas sensíveis (dados de
 * clientes, pedidos, mensagens, relatórios). Nesta PR é aplicado apenas à
 * tela legada (que já exibe dados operacionais da loja); a Central de
 * Atendimento nativa (PR #412) deve chamar [enable] no onCreate/onResume das
 * suas telas autenticadas. Não é aplicado a telas públicas (splash, login,
 * configuração) sem necessidade real.
 */
object ScreenSecurity {

    fun enable(activity: Activity) {
        activity.window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE,
        )
    }

    fun disable(activity: Activity) {
        activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }
}
