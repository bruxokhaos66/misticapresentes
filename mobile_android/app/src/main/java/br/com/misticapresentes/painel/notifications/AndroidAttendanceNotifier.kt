package br.com.misticapresentes.painel.notifications

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import br.com.misticapresentes.painel.MainActivity
import br.com.misticapresentes.painel.R
import br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState

/** Extra do deep link: id (Long) da conversa a abrir quando a notificação é tocada. */
const val EXTRA_ATTENDANCE_CONVERSATION_ID = "br.com.misticapresentes.painel.EXTRA_ATTENDANCE_CONVERSATION_ID"

private const val CHANNEL_ID = "central_atendimento_mensagens"
private const val NOTIFICATION_ID_BASE = 90_000

/**
 * Implementação real de [AttendanceNotifier], apoiada em
 * `NotificationManagerCompat`. Nunca é chamada diretamente pelo Worker/
 * ViewModel sem que a flag `ATTENDANCE_NOTIFICATIONS_ENABLED` já tenha sido
 * checada por quem invoca -- esta classe só sabe "notificar" ou não
 * (suprimindo quando a conversa já está visível), não decide feature flag.
 */
class AndroidAttendanceNotifier(private val context: Context) : AttendanceNotifier {

    private val appContext = context.applicationContext

    init {
        ensureChannel()
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = appContext.getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Central de Atendimento",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Avisos de novas mensagens na Central de Atendimento"
        }
        manager.createNotificationChannel(channel)
    }

    override fun notifyNewMessage(conversationId: Long) {
        // Privacidade + evita notificação redundante: se o atendente já está
        // olhando exatamente esta conversa, não há nada de novo para mostrar.
        if (AttendanceForegroundState.isConversationVisible(conversationId)) return

        val intent = Intent(appContext, MainActivity::class.java).apply {
            action = Intent.ACTION_VIEW
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra(EXTRA_ATTENDANCE_CONVERSATION_ID, conversationId)
        }
        // requestCode único por conversa: PendingIntents de conversas
        // diferentes não se sobrescrevem; a mesma conversa reaproveita
        // (FLAG_UPDATE_CURRENT) em vez de acumular.
        val requestCode = conversationId.hashCode()
        val pendingIntentFlags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val pendingIntent = PendingIntent.getActivity(appContext, requestCode, intent, pendingIntentFlags)

        // Conteúdo mínimo por padrão: NUNCA nome, telefone, texto da
        // mensagem, mídia ou id legível ao usuário -- só um aviso genérico,
        // seguro para tela bloqueada (ver requisito de privacidade da PR #414).
        val notification = NotificationCompat.Builder(appContext, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentTitle("Central de Atendimento")
            .setContentText("Nova mensagem na Central de Atendimento")
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .build()

        runCatching {
            NotificationManagerCompat.from(appContext).notify(notificationIdFor(conversationId), notification)
        }
        // SecurityException se POST_NOTIFICATIONS não foi concedida (Android
        // 13+) -- best effort, nunca derruba o app por causa de um aviso.
    }

    override fun clearForConversation(conversationId: Long) {
        runCatching {
            NotificationManagerCompat.from(appContext).cancel(notificationIdFor(conversationId))
        }
    }

    override fun clearAll() {
        runCatching {
            NotificationManagerCompat.from(appContext).cancelAll()
        }
    }

    private fun notificationIdFor(conversationId: Long): Int = NOTIFICATION_ID_BASE + (conversationId.hashCode() and 0x0FFFFFFF)
}
