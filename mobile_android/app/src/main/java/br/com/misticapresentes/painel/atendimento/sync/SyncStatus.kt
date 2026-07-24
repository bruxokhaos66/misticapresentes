package br.com.misticapresentes.painel.atendimento.sync

/**
 * Estado discreto de sincronização exibido na UI (indicador pequeno, nunca
 * um redesenho de tela) -- ver requisito de "sem erro repetitivo a cada
 * ciclo": uma falha de polling atualiza este estado para [FAILED] uma única
 * vez, nunca dispara snackbar/diálogo repetido a cada tentativa.
 */
enum class SyncStatus {
    /** Sincronização desligada (flag off) ou ainda não iniciada. */
    IDLE,

    /** Requisição de sincronização em voo. */
    SYNCING,

    /** Última sincronização concluída com sucesso. */
    UPDATED,

    /** Sem conexão com a internet -- detectado via [br.com.misticapresentes.painel.common.ConnectivityObserver]. */
    OFFLINE,

    /** Última tentativa de sincronização falhou (timeout, 5xx, DNS etc.) enquanto online. */
    FAILED,
}
