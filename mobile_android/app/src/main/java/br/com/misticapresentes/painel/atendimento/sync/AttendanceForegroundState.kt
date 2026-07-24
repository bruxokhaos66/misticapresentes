package br.com.misticapresentes.painel.atendimento.sync

import java.util.concurrent.atomic.AtomicLong

/**
 * Estado global e leve (processo único) de qual conversa está atualmente
 * visível em primeiro plano. Usado só para DUAS decisões, ambas de UX/
 * privacidade, nunca de segurança/permissão (isso continua 100% no
 * backend):
 *
 * 1. Suprimir notificação de nova mensagem quando o atendente já está
 *    olhando exatamente aquela conversa (`ConversationScreen` aberta).
 * 2. WorkManager em background não tem noção de tela nenhuma -- por
 *    desenho ele só roda quando o processo pode estar morto ou a Activity
 *    em segundo plano, então este estado é zerado no `onPause`/`onCleared`
 *    da tela para nunca "vazar" um falso positivo de tela aberta.
 *
 * Não é um Singleton de DI "de verdade" (não guarda nenhuma dependência
 * pesada nem lógica de negócio) -- é só um sinalizador in-memory, do mesmo
 * jeito que `ProcessLifecycleOwner` é global no Android. Implementado com
 * `AtomicLong` (sem lock) porque é só um valor lido/escrito, nunca uma
 * seção crítica composta.
 */
object AttendanceForegroundState {
    private const val NONE = -1L
    private val visibleConversationId = AtomicLong(NONE)

    fun setVisibleConversation(conversationId: Long) {
        visibleConversationId.set(conversationId)
    }

    /** Só limpa se ainda for A MESMA conversa -- evita que a tela antiga limpe o estado da nova ao ser destruída em sequência rápida. */
    fun clearVisibleConversation(conversationId: Long) {
        visibleConversationId.compareAndSet(conversationId, NONE)
    }

    fun isConversationVisible(conversationId: Long): Boolean = visibleConversationId.get() == conversationId

    /** Usado só em teste, para isolar cada caso sem vazar estado entre testes (objeto é global no processo JVM de teste). */
    fun resetForTest() {
        visibleConversationId.set(NONE)
    }
}
