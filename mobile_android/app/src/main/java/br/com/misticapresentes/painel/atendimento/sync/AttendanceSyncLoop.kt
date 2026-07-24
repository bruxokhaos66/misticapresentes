package br.com.misticapresentes.painel.atendimento.sync

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Motor único e reutilizável do polling em primeiro plano da Central de
 * Atendimento (ver [SyncConfig] para o porquê de ser polling em vez de
 * WebSocket/SSE). Cada tela (lista e detalhe de conversa) possui a SUA
 * própria instância, criada pelo respectivo ViewModel -- nunca compartilhada
 * entre telas/conversas, o que garante isolamento por `conversationId` e
 * cancelamento correto ao trocar de conversa (o ViewModel antigo é
 * destruído, o novo cria seu próprio loop).
 *
 * - [start] é idempotente: chamar de novo enquanto já ativo não cria um
 *   segundo loop (evita polling duplicado em recomposição).
 * - [stop] cancela o [Job] em andamento; chamar de novo sem estar rodando é
 *   inofensivo.
 * - Backoff exponencial só quando [tick] devolve `false` (falha/offline);
 *   qualquer sucesso volta imediatamente ao intervalo-base.
 * - Nunca usa `GlobalScope`: [scope] é sempre o `viewModelScope` de quem
 *   instancia, então o loop morre sozinho quando o ViewModel é limpo.
 */
class AttendanceSyncLoop(
    private val scope: CoroutineScope,
    private val baseIntervalMs: Long,
    private val maxIntervalMs: Long = SyncConfig.FOREGROUND_MAX_BACKOFF_MS,
    private val backoffMultiplier: Int = SyncConfig.FOREGROUND_BACKOFF_MULTIPLIER,
    private val tick: suspend () -> Boolean,
) {
    private var job: Job? = null

    val isRunning: Boolean
        get() = job?.isActive == true

    fun start() {
        if (isRunning) return
        job = scope.launch {
            var currentInterval = baseIntervalMs
            while (isActive) {
                delay(currentInterval)
                if (!isActive) break
                val success = runCatching { tick() }.getOrDefault(false)
                currentInterval = if (success) {
                    baseIntervalMs
                } else {
                    (currentInterval * backoffMultiplier).coerceAtMost(maxIntervalMs)
                }
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
    }
}
