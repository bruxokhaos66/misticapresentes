package br.com.misticapresentes.painel.atendimento.sync

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.Configuration
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Testes do agendamento único do WorkManager (PR #414) -- prova que
 * agendar duas vezes NUNCA duplica o trabalho (unique work) e que
 * [AttendanceBackgroundSyncScheduler.cancel] remove o agendamento.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AttendanceBackgroundSyncSchedulerTest {

    private lateinit var context: Context
    private lateinit var workManager: WorkManager

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        val config = Configuration.Builder().setMinimumLoggingLevel(android.util.Log.DEBUG).build()
        WorkManagerTestInitHelper.initializeTestWorkManager(context, config)
        workManager = WorkManager.getInstance(context)
    }

    private fun enqueuedWorkInfos(): List<WorkInfo> =
        workManager.getWorkInfosForUniqueWork("attendance_background_sync").get()

    @Test
    fun `ensureScheduled enqueues exactly one unique periodic work`() {
        AttendanceBackgroundSyncScheduler(context).ensureScheduled()

        val infos = enqueuedWorkInfos().filter { it.state != WorkInfo.State.CANCELLED }
        assertEquals(1, infos.size)
    }

    @Test
    fun `calling ensureScheduled twice never creates a duplicate unique work`() {
        val scheduler = AttendanceBackgroundSyncScheduler(context)
        scheduler.ensureScheduled()
        scheduler.ensureScheduled()
        scheduler.ensureScheduled()

        val infos = enqueuedWorkInfos().filter { it.state != WorkInfo.State.CANCELLED }
        assertEquals(1, infos.size)
    }

    @Test
    fun `cancel removes the scheduled unique work`() {
        val scheduler = AttendanceBackgroundSyncScheduler(context)
        scheduler.ensureScheduled()

        scheduler.cancel()

        val infos = enqueuedWorkInfos()
        assertTrue(infos.all { it.state == WorkInfo.State.CANCELLED })
    }

    @Test
    fun `the enqueued work requires a connected network constraint`() {
        AttendanceBackgroundSyncScheduler(context).ensureScheduled()

        val info = enqueuedWorkInfos().first { it.state != WorkInfo.State.CANCELLED }
        assertEquals(androidx.work.NetworkType.CONNECTED, info.constraints.requiredNetworkType)
    }
}
