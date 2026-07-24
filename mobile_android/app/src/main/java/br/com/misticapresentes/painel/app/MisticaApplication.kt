package br.com.misticapresentes.painel.app

import android.app.Application
import androidx.work.Configuration
import br.com.misticapresentes.painel.auth.AuthState
import br.com.misticapresentes.painel.common.FeatureFlag
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class MisticaApplication : Application(), Configuration.Provider {

    /**
     * `by lazy` (não mais um `lateinit` setado em `onCreate`) DE PROPÓSITO:
     * o WorkManager se auto-inicializa via um `ContentProvider` interno da
     * androidx-startup, cujo `onCreate()` roda ANTES de `Application.onCreate()`
     * -- e é nesse momento que ele lê [workManagerConfiguration] (que depende
     * de [container]) para descobrir a [AttendanceWorkerFactory] customizada.
     * Um `lateinit` setado só em `onCreate()` quebraria essa ordem
     * (`UninitializedPropertyAccessException`); `by lazy` constrói sob
     * demanda, na primeira leitura, seja ela vinda do ContentProvider ou do
     * restante do app.
     */
    val container: AppContainer by lazy { AppContainer(this) }

    /**
     * Escopo PRÓPRIO desta instância de [Application] -- deliberadamente NÃO
     * `ProcessLifecycleOwner.get().lifecycleScope` (usado numa versão
     * anterior desta PR). `ProcessLifecycleOwner` é um singleton ESTÁTICO que
     * sobrevive entre instâncias de `Application`; como o Robolectric recria
     * `MisticaApplication` (e portanto [container]) a cada teste unitário, um
     * escopo preso a esse singleton fazia cada teste empilhar mais dois
     * coletores de Flow que nunca eram cancelados, todos competindo pelo
     * mesmo `Dispatchers.Main` -- degradando progressivamente a suíte inteira
     * até travar o step de testes no CI. Um escopo próprio, cancelado em
     * [onTerminate] (chamado pelo Robolectric entre testes), elimina esse
     * acúmulo. Em produção `onTerminate()` raramente é chamado, mas cancelar
     * aqui não é necessário nesse caso: o processo morre e leva o escopo
     * junto de qualquer forma.
     */
    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    override fun onCreate() {
        super.onCreate()
        observeBackgroundSyncFlagAndSession()
    }

    override fun onTerminate() {
        applicationScope.cancel()
        super.onTerminate()
    }

    /** Visibilidade `internal` só para teste: prova que [onTerminate] realmente cancela [applicationScope]. */
    internal val isApplicationScopeActiveForTest: Boolean
        get() = applicationScope.coroutineContext[Job]?.isActive == true

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(AttendanceWorkerFactory(container))
            .build()

    /**
     * Único ponto que decide se o WorkManager de background deve estar
     * agendado: liga quando `BACKGROUND_SYNC_ENABLED` está ligada E existe
     * sessão logada; desliga (cancela) assim que qualquer uma das duas deixa
     * de valer -- inclusive logout, para nenhum Worker sobreviver a ele.
     * [applicationScope] (processo inteiro, não uma Activity) porque este
     * agendamento não é amarrado a nenhuma tela específica.
     */
    private fun observeBackgroundSyncFlagAndSession() {
        applicationScope.launch {
            container.featureFlagsRepository.isEnabled(FeatureFlag.BACKGROUND_SYNC_ENABLED).collect { enabled ->
                updateBackgroundSyncSchedule(enabled)
            }
        }
        applicationScope.launch {
            container.authRepository.authState.collect { state ->
                if (state is AuthState.LoggedOut || state is AuthState.SessionExpired) {
                    // Nenhum Worker/notificação/contador de não lidas
                    // sobrevive a um logout (ou sessão expirada).
                    container.backgroundSyncScheduler.cancel()
                    container.attendanceNotifier.clearAll()
                    container.appPreferences.clearLastKnownUnreadTotal()
                }
            }
        }
    }

    private suspend fun updateBackgroundSyncSchedule(backgroundSyncEnabled: Boolean) {
        val hasSession = container.secureSessionStore.hasSession()
        if (backgroundSyncEnabled && hasSession) {
            container.backgroundSyncScheduler.ensureScheduled()
        } else {
            container.backgroundSyncScheduler.cancel()
        }
    }
}
