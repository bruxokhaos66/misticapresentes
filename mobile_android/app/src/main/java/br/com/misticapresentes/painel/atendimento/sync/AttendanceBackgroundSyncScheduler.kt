package br.com.misticapresentes.painel.atendimento.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

private const val UNIQUE_WORK_NAME = "attendance_background_sync"

/**
 * Único ponto de agendamento/cancelamento do [AttendanceBackgroundSyncWorker].
 * Nunca chamado pela UI diretamente -- [br.com.misticapresentes.painel.app.MisticaApplication]
 * o aciona ao observar a flag `BACKGROUND_SYNC_ENABLED`, e
 * [br.com.misticapresentes.painel.auth.AuthRepository] o cancela no logout.
 *
 * `ExistingPeriodicWorkPolicy.UPDATE` (nome de trabalho único) garante que
 * nunca existam dois agendamentos concorrentes do mesmo Worker -- reagendar
 * com os mesmos parâmetros é inofensivo (atualiza in-place em vez de
 * duplicar).
 */
class AttendanceBackgroundSyncScheduler(context: Context) {

    private val workManager = WorkManager.getInstance(context.applicationContext)

    fun ensureScheduled() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<AttendanceBackgroundSyncWorker>(
            SyncConfig.BACKGROUND_SYNC_INTERVAL_MINUTES,
            TimeUnit.MINUTES,
        )
            .setConstraints(constraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                SyncConfig.BACKGROUND_SYNC_BACKOFF_DELAY_SECONDS,
                TimeUnit.SECONDS,
            )
            .build()

        workManager.enqueueUniquePeriodicWork(UNIQUE_WORK_NAME, ExistingPeriodicWorkPolicy.UPDATE, request)
    }

    /** Chamado quando a flag `BACKGROUND_SYNC_ENABLED` está desligada ou no logout -- nenhum trabalho agendado sobrevive a nenhum dos dois. */
    fun cancel() {
        workManager.cancelUniqueWork(UNIQUE_WORK_NAME)
    }
}
