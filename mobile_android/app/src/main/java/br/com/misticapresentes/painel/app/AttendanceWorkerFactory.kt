package br.com.misticapresentes.painel.app

import android.content.Context
import androidx.work.ListenableWorker
import androidx.work.WorkerFactory
import androidx.work.WorkerParameters
import br.com.misticapresentes.painel.atendimento.sync.AttendanceBackgroundSyncWorker

/**
 * WorkerFactory manual (este projeto usa DI manual via [AppContainer], sem
 * Hilt) que sabe construir [AttendanceBackgroundSyncWorker] com as MESMAS
 * instâncias de repository/secureSessionStore/featureFlagsRepository/
 * notifier já usadas pelo resto do app -- nunca cria uma segunda instância
 * paralela de nada (ex.: um segundo `AtendimentoRepository` com outro
 * client HTTP).
 */
class AttendanceWorkerFactory(private val container: AppContainer) : WorkerFactory() {

    override fun createWorker(
        appContext: Context,
        workerClassName: String,
        workerParameters: WorkerParameters,
    ): ListenableWorker? {
        return when (workerClassName) {
            AttendanceBackgroundSyncWorker::class.java.name -> AttendanceBackgroundSyncWorker(
                context = appContext,
                params = workerParameters,
                secureSessionStore = container.secureSessionStore,
                featureFlagsRepository = container.featureFlagsRepository,
                repository = container.atendimentoRepository,
                notifier = container.attendanceNotifier,
                appPreferences = container.appPreferences,
            )
            else -> null
        }
    }
}
