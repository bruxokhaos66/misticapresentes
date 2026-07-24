package br.com.misticapresentes.painel.atendimento.ui.common

import br.com.misticapresentes.painel.atendimento.sync.SyncStatus

/**
 * Rótulo textual curto e discreto para cada [SyncStatus], compartilhado
 * entre a lista e o detalhe de conversa -- nunca um diálogo/snackbar, só um
 * texto pequeno próximo ao topo da tela. `null` quando não há nada a
 * mostrar (ex.: [SyncStatus.IDLE], ou [SyncStatus.OFFLINE], que já tem seu
 * próprio banner dedicado em ambas as telas).
 */
fun syncStatusLabel(status: SyncStatus): String? = when (status) {
    SyncStatus.IDLE -> null
    SyncStatus.OFFLINE -> null
    SyncStatus.SYNCING -> "Sincronizando..."
    SyncStatus.UPDATED -> "Atualizado agora"
    SyncStatus.FAILED -> "Falha ao atualizar"
}
