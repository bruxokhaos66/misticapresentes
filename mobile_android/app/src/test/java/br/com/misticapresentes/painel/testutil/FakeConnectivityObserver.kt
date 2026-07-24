package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.common.ConnectivityObserver
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class FakeConnectivityObserver(initiallyOnline: Boolean = true) : ConnectivityObserver {
    private val state = MutableStateFlow(initiallyOnline)

    fun setOnline(online: Boolean) {
        state.value = online
    }

    override fun isOnlineNow(): Boolean = state.value

    override fun observe(): StateFlow<Boolean> = state
}
