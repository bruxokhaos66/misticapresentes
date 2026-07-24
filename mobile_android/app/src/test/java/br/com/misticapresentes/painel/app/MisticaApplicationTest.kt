package br.com.misticapresentes.painel.app

import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * [MisticaApplication] usa um `CoroutineScope` próprio (não o singleton
 * estático `ProcessLifecycleOwner`) exatamente para que cada instância de
 * `Application` recriada pelo Robolectric a cada teste consiga ser
 * corretamente cancelada -- sem isso, os coletores de Flow de
 * `observeBackgroundSyncFlagAndSession` se acumulavam entre testes e
 * degradavam/travavam o step de testes unitários no CI.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class MisticaApplicationTest {

    @Test
    fun `application scope is active after onCreate`() {
        val app = ApplicationProvider.getApplicationContext<MisticaApplication>()

        assertTrue(app.isApplicationScopeActiveForTest)
    }

    @Test
    fun `onTerminate cancels the application scope -- no dangling collectors survive it`() {
        val app = ApplicationProvider.getApplicationContext<MisticaApplication>()

        app.onTerminate()

        assertFalse(app.isApplicationScopeActiveForTest)
    }
}
