package br.com.misticapresentes.painel.app

import android.app.Application

class MisticaApplication : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
