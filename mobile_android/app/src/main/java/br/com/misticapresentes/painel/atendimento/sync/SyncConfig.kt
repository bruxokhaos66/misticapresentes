package br.com.misticapresentes.painel.atendimento.sync

/**
 * Configuração central de sincronização da Central de Atendimento (PR #414).
 *
 * Auditoria feita antes de escrever qualquer código desta PR (ver
 * `mobile_android/README.md`, seção "Sincronização (PR #414)"): o backend
 * (`backend/whatsapp_*_routes.py`) não expõe WebSocket, SSE, long polling,
 * nem endpoint incremental por cursor/timestamp para eventos -- só
 * paginação por página (fila/lista) e por `before_id` (mensagens, para
 * carregar histórico mais antigo). Não existe também nenhum webhook interno
 * para o app. Por isso a estratégia adotada aqui é polling HTTP eficiente,
 * usando os MESMOS endpoints que a PR #412/#413 já consomem -- nenhum
 * endpoint novo foi criado ou é necessário.
 *
 * Todos os intervalos de polling do app vivem aqui -- nenhum outro arquivo
 * deve espalhar um valor de intervalo "mágico".
 */
object SyncConfig {

    /** Conversa aberta (tela de detalhe visível): intervalo-base do polling de mensagens/status. */
    const val CONVERSATION_POLL_INTERVAL_MS: Long = 8_000L

    /** Lista de conversas / fila (tela de lista visível): intervalo-base do polling. */
    const val LIST_POLL_INTERVAL_MS: Long = 15_000L

    /** Teto do backoff exponencial em primeiro plano -- nunca cresce além disso, mesmo com falhas seguidas. */
    const val FOREGROUND_MAX_BACKOFF_MS: Long = 90_000L

    /** Fator de multiplicação do backoff a cada falha consecutiva (dobra o intervalo, até o teto acima). */
    const val FOREGROUND_BACKOFF_MULTIPLIER: Int = 2

    /**
     * Intervalo do WorkManager em background (minutos). 15 minutos é o
     * MÍNIMO absoluto permitido pelo Android para `PeriodicWorkRequest`
     * (`WorkRequest.MIN_PERIODIC_INTERVAL_MILLIS`) -- usamos exatamente o
     * piso, nunca menos, e nunca usamos WorkManager para tentar simular
     * tempo real (isso é papel exclusivo do polling em primeiro plano acima).
     */
    const val BACKGROUND_SYNC_INTERVAL_MINUTES: Long = 15L

    /** Backoff inicial do próprio WorkManager em caso de falha (`BackoffPolicy.EXPONENTIAL`). */
    const val BACKGROUND_SYNC_BACKOFF_DELAY_SECONDS: Long = 30L

    /** Página pequena o bastante para uma checagem leve de contagem de não lidas em background. */
    const val BACKGROUND_SYNC_PAGE_SIZE: Int = 20
}
