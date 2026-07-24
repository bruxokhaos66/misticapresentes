package br.com.misticapresentes.painel.atendimento.sync

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AttendanceSyncLoopTest {

    @Test
    fun `does not tick before the base interval elapses`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(scope = scope, baseIntervalMs = 1_000, tick = { tickCount++; true })

        loop.start()
        dispatcher.scheduler.advanceTimeBy(500)
        dispatcher.scheduler.runCurrent()

        assertEquals(0, tickCount)
        loop.stop()
    }

    @Test
    fun `ticks repeatedly at the base interval while successful`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(scope = scope, baseIntervalMs = 1_000, tick = { tickCount++; true })

        loop.start()
        dispatcher.scheduler.advanceTimeBy(3_500)
        dispatcher.scheduler.runCurrent()

        assertEquals(3, tickCount)
        loop.stop()
    }

    @Test
    fun `start is idempotent -- calling it again while already running does not create a second loop`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(scope = scope, baseIntervalMs = 1_000, tick = { tickCount++; true })

        loop.start()
        loop.start()
        loop.start()
        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()

        // Se um segundo loop tivesse sido criado, teríamos 2+ ticks no mesmo intervalo.
        assertEquals(1, tickCount)
        loop.stop()
    }

    @Test
    fun `stop cancels the loop -- no further ticks happen`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(scope = scope, baseIntervalMs = 1_000, tick = { tickCount++; true })

        loop.start()
        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount)

        loop.stop()
        dispatcher.scheduler.advanceTimeBy(5_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount)
        assertFalse(loop.isRunning)
    }

    @Test
    fun `backoff doubles interval on failure and caps at maxIntervalMs`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(
            scope = scope,
            baseIntervalMs = 1_000,
            maxIntervalMs = 5_000,
            tick = { tickCount++; false },
        )

        loop.start()
        // Ticks esperados (todos falham): 1000, +2000=3000, +4000(capado em 5000)=8000, +5000=13000...
        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount)

        dispatcher.scheduler.advanceTimeBy(1_999)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount) // ainda não chegou em 2000ms de espera

        dispatcher.scheduler.advanceTimeBy(1)
        dispatcher.scheduler.runCurrent()
        assertEquals(2, tickCount)

        loop.stop()
    }

    @Test
    fun `interval returns to base immediately after a successful tick following failures`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var shouldSucceed = false
        var tickCount = 0
        val loop = AttendanceSyncLoop(
            scope = scope,
            baseIntervalMs = 1_000,
            maxIntervalMs = 10_000,
            tick = { tickCount++; shouldSucceed },
        )

        loop.start()
        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount) // falhou, próximo em +2000ms

        shouldSucceed = true
        dispatcher.scheduler.advanceTimeBy(2_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(2, tickCount) // sucesso -- volta ao intervalo-base (1000ms)

        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(3, tickCount)

        loop.stop()
    }

    @Test
    fun `an exception thrown by tick is treated as failure, not a crash`() = runTest {
        val dispatcher = StandardTestDispatcher(testScheduler)
        val scope = TestScope(dispatcher)
        var tickCount = 0
        val loop = AttendanceSyncLoop(
            scope = scope,
            baseIntervalMs = 1_000,
            tick = { tickCount++; throw java.io.IOException("falha de rede simulada") },
        )

        loop.start()
        dispatcher.scheduler.advanceTimeBy(1_000)
        dispatcher.scheduler.runCurrent()
        assertEquals(1, tickCount)
        assertTrue(loop.isRunning)

        loop.stop()
    }
}
