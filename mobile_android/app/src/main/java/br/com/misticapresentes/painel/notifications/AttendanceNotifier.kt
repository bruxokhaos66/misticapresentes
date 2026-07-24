package br.com.misticapresentes.painel.notifications

/**
 * Camada de notificação da Central de Atendimento (PR #414).
 *
 * Auditoria feita antes de implementar: este projeto NÃO tem FCM configurado
 * (sem `google-services.json`, sem `com.google.gms:google-services`, sem
 * `firebase-messaging` em nenhum `build.gradle` -- só a flag placeholder
 * `PUSH_NOTIFICATIONS_ENABLED`, já existente e não usada por nenhum código).
 * Por isso esta PR NÃO adiciona Firebase nem nenhuma credencial/console
 * externo -- implementa apenas notificações LOCAIS, disparadas a partir da
 * própria sincronização (polling em primeiro plano e WorkManager em
 * background) já implementada nesta mesma PR.
 *
 * Limitação conhecida e documentada: sem um servidor push real (FCM ou
 * equivalente), o app só percebe uma mensagem nova quando o próximo ciclo de
 * sincronização rodar -- não há entrega instantânea com o app totalmente
 * fechado e fora da janela do WorkManager. Migrar para push de verdade fica
 * para uma PR futura, quando o FCM for configurado de fato (projeto Firebase
 * real, `google-services.json` real).
 *
 * Interface (em vez de chamar Android/NotificationManager direto dos
 * ViewModels/Worker) para permitir testar toda a lógica de "quando notificar"
 * com um fake, sem depender do framework de notificação real.
 */
interface AttendanceNotifier {

    /**
     * Nova mensagem detectada na conversa [conversationId]. Implementações
     * DEVEM:
     * - Nunca incluir nome, telefone, texto da mensagem, mídia ou qualquer
     *   PII no título/corpo -- conteúdo sempre genérico
     *   ("Nova mensagem na Central de Atendimento").
     * - Suprimir a notificação quando essa MESMA conversa já está visível em
     *   primeiro plano (ver [br.com.misticapresentes.painel.atendimento.sync.AttendanceForegroundState]).
     * - Usar um id de notificação estável por conversa (dedupe: uma segunda
     *   chamada para a mesma conversa atualiza a notificação existente, não
     *   empilha uma nova).
     */
    fun notifyNewMessage(conversationId: Long)

    /** Limpa a notificação (se existir) da conversa [conversationId] -- chamado ao abrir a conversa. */
    fun clearForConversation(conversationId: Long)

    /** Limpa todas as notificações desta feature -- chamado no logout. */
    fun clearAll()
}

/** Implementação inerte, usada como padrão em testes/instanciações que não se importam com notificação. */
object NoopAttendanceNotifier : AttendanceNotifier {
    override fun notifyNewMessage(conversationId: Long) = Unit
    override fun clearForConversation(conversationId: Long) = Unit
    override fun clearAll() = Unit
}
