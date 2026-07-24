package br.com.misticapresentes.painel.notifications

import android.app.NotificationManager
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AndroidAttendanceNotifierTest {

    private lateinit var context: Context
    private lateinit var notificationManager: NotificationManager
    private lateinit var notifier: AndroidAttendanceNotifier

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notifier = AndroidAttendanceNotifier(context)
        AttendanceForegroundState.resetForTest()
    }

    @After
    fun tearDown() {
        AttendanceForegroundState.resetForTest()
    }

    @Test
    fun `posts a notification with generic content -- no PII`() {
        notifier.notifyNewMessage(conversationId = 1L)

        val posted = shadowOf(notificationManager).allNotifications
        assertEquals(1, posted.size)
        val notification = posted.first()
        val extras = notification.extras
        val title = extras.getCharSequence(android.app.Notification.EXTRA_TITLE)?.toString()
        val text = extras.getCharSequence(android.app.Notification.EXTRA_TEXT)?.toString()
        assertEquals("Central de Atendimento", title)
        assertEquals("Nova mensagem na Central de Atendimento", text)
        // Nenhum destes conteúdos genéricos deve conter dígitos (telefone) nem nomes de exemplo.
        assertFalse((text ?: "").contains(Regex("\\d")))
    }

    @Test
    fun `does not post a notification when the conversation is currently visible`() {
        AttendanceForegroundState.setVisibleConversation(1L)

        notifier.notifyNewMessage(conversationId = 1L)

        assertTrue(shadowOf(notificationManager).allNotifications.isEmpty())
    }

    @Test
    fun `a second call for the same conversation updates instead of stacking a new notification`() {
        notifier.notifyNewMessage(conversationId = 1L)
        notifier.notifyNewMessage(conversationId = 1L)

        assertEquals(1, shadowOf(notificationManager).allNotifications.size)
    }

    @Test
    fun `different conversations get distinct notifications`() {
        notifier.notifyNewMessage(conversationId = 1L)
        notifier.notifyNewMessage(conversationId = 2L)

        assertEquals(2, shadowOf(notificationManager).allNotifications.size)
    }

    @Test
    fun `clearForConversation removes only that conversation's notification`() {
        notifier.notifyNewMessage(conversationId = 1L)
        notifier.notifyNewMessage(conversationId = 2L)

        notifier.clearForConversation(1L)

        val remaining = shadowOf(notificationManager).allNotifications
        assertEquals(1, remaining.size)
    }

    @Test
    fun `clearAll removes every posted notification`() {
        notifier.notifyNewMessage(conversationId = 1L)
        notifier.notifyNewMessage(conversationId = 2L)

        notifier.clearAll()

        assertTrue(shadowOf(notificationManager).allNotifications.isEmpty())
    }

    @Test
    fun `the notification channel is created once and is idempotent to construct again`() {
        AndroidAttendanceNotifier(context) // segunda instância -- não deve duplicar/crashar
        val channel = notificationManager.getNotificationChannel("central_atendimento_mensagens")
        assertTrue(channel != null || android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.O)
    }
}
