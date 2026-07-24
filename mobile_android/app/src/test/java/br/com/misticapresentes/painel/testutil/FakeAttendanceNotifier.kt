package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState
import br.com.misticapresentes.painel.notifications.AttendanceNotifier

/**
 * Fake em memória de [AttendanceNotifier], para provar em teste QUANDO (e
 * para qual conversa) uma notificação seria disparada, sem depender do
 * NotificationManager real. Reproduz a MESMA regra de supressão descrita no
 * contrato da interface (nunca notifica a conversa que já está visível em
 * primeiro plano) -- do contrário, um teste que use este fake não provaria
 * nada sobre supressão, já que ela é responsabilidade de cada implementação.
 */
class FakeAttendanceNotifier : AttendanceNotifier {

    val notifiedConversationIds = mutableListOf<Long>()
    val clearedConversationIds = mutableListOf<Long>()
    var clearAllCallCount = 0
        private set

    override fun notifyNewMessage(conversationId: Long) {
        if (AttendanceForegroundState.isConversationVisible(conversationId)) return
        notifiedConversationIds += conversationId
    }

    override fun clearForConversation(conversationId: Long) {
        clearedConversationIds += conversationId
    }

    override fun clearAll() {
        clearAllCallCount++
    }
}
