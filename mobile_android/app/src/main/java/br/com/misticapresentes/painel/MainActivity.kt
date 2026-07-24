package br.com.misticapresentes.painel

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import br.com.misticapresentes.painel.app.MisticaApplication
import br.com.misticapresentes.painel.legacy.LegacyPanelActivity
import br.com.misticapresentes.painel.navigation.MisticaNavHost
import br.com.misticapresentes.painel.notifications.EXTRA_ATTENDANCE_CONVERSATION_ID
import br.com.misticapresentes.painel.ui.theme.MisticaTheme

class MainActivity : ComponentActivity() {

    /**
     * Deep link vindo do toque em uma notificação da Central de Atendimento
     * (PR #414) -- `null`/inválido significa "nenhum deep link pendente"; a
     * NavHost consome e sinaliza de volta (via `onDeepLinkConsumed`) para
     * nunca navegar de novo sozinha numa recomposição ou rotação de tela.
     */
    private var pendingConversationDeepLink by mutableStateOf<Long?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        consumeDeepLinkFromIntent(intent)

        val container = (application as MisticaApplication).container

        setContent {
            MisticaTheme {
                MisticaNavHost(
                    container = container,
                    onOpenLegacyPanel = { startActivity(Intent(this, LegacyPanelActivity::class.java)) },
                    onEnterLegacyOnly = {
                        startActivity(Intent(this, LegacyPanelActivity::class.java))
                        finish()
                    },
                    pendingConversationDeepLink = pendingConversationDeepLink,
                    onDeepLinkConsumed = { pendingConversationDeepLink = null },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        consumeDeepLinkFromIntent(intent)
    }

    /** Só aceita um id de conversa positivo (`> 0`) -- qualquer outra coisa é tratada como "sem deep link". */
    private fun consumeDeepLinkFromIntent(intent: Intent?) {
        val conversationId = intent?.getLongExtra(EXTRA_ATTENDANCE_CONVERSATION_ID, -1L) ?: -1L
        if (conversationId > 0) {
            pendingConversationDeepLink = conversationId
        }
    }
}
