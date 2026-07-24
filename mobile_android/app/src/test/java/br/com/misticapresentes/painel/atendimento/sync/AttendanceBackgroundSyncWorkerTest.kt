package br.com.misticapresentes.painel.atendimento.sync

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.common.AppPreferences
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeAttendanceNotifier
import br.com.misticapresentes.painel.testutil.FakeFeatureFlagsRepository
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Testes do [AttendanceBackgroundSyncWorker] (PR #414). Cada teste constrói
 * o Worker diretamente com fakes (mesmo padrão do resto do app) via
 * `TestListenableWorkerBuilder`, exercitando o MESMO `doWork()` que o
 * WorkManager real chamaria em produção.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class AttendanceBackgroundSyncWorkerTest {

    private lateinit var context: Context
    private lateinit var atendimentoApi: FakeAtendimentoApi

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        atendimentoApi = FakeAtendimentoApi()
    }

    private fun buildWorker(
        backgroundSyncEnabled: Boolean = true,
        notificationsEnabled: Boolean = true,
        hasSession: Boolean = true,
        notifier: FakeAttendanceNotifier = FakeAttendanceNotifier(),
        appPreferences: AppPreferences = AppPreferences(context),
    ): AttendanceBackgroundSyncWorker {
        val secureSessionStore = FakeSecureSessionStore().apply {
            if (hasSession) cookieJarState = "sessao-de-teste"
        }
        val flags = FakeFeatureFlagsRepository(
            mapOf(
                FeatureFlag.BACKGROUND_SYNC_ENABLED to backgroundSyncEnabled,
                FeatureFlag.ATTENDANCE_NOTIFICATIONS_ENABLED to notificationsEnabled,
            ),
        )
        return TestListenableWorkerBuilder<AttendanceBackgroundSyncWorker>(context)
            .setWorkerFactory(
                object : androidx.work.WorkerFactory() {
                    override fun createWorker(
                        appContext: Context,
                        workerClassName: String,
                        workerParameters: androidx.work.WorkerParameters,
                    ) = AttendanceBackgroundSyncWorker(
                        context = appContext,
                        params = workerParameters,
                        secureSessionStore = secureSessionStore,
                        featureFlagsRepository = flags,
                        repository = AtendimentoRepository(atendimentoApi),
                        notifier = notifier,
                        appPreferences = appPreferences,
                    )
                },
            )
            .build()
    }

    @Test
    fun `does not call the network when BACKGROUND_SYNC_ENABLED is off`() = runTest {
        val worker = buildWorker(backgroundSyncEnabled = false)

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Success)
        assertTrue(atendimentoApi.callLog.isEmpty())
    }

    @Test
    fun `does not call the network without a local session (e_g_ after logout)`() = runTest {
        val worker = buildWorker(hasSession = false)

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Success)
        assertTrue(atendimentoApi.callLog.isEmpty())
    }

    @Test
    fun `succeeds and calls listMine once when enabled with a valid session`() = runTest {
        val worker = buildWorker()

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Success)
        assertEquals(listOf("myConversations"), atendimentoApi.callLog)
    }

    @Test
    fun `notifies when unread total increases since the last known value`() = runTest {
        val appPreferences = AppPreferences(context)
        val notifier = FakeAttendanceNotifier()
        atendimentoApi.myConversations = listOf(FakeAtendimentoApi.defaultQueueConversation().copy(id = 5, unreadCount = 3))
        val worker = buildWorker(notifier = notifier, appPreferences = appPreferences)

        worker.doWork()

        assertEquals(listOf(5L), notifier.notifiedConversationIds)
    }

    @Test
    fun `does not notify when notifications flag is off even if unread increased`() = runTest {
        val notifier = FakeAttendanceNotifier()
        atendimentoApi.myConversations = listOf(FakeAtendimentoApi.defaultQueueConversation().copy(id = 5, unreadCount = 3))
        val worker = buildWorker(notificationsEnabled = false, notifier = notifier)

        worker.doWork()

        assertTrue(notifier.notifiedConversationIds.isEmpty())
    }

    @Test
    fun `does not notify again on a second run with the same unread total`() = runTest {
        val appPreferences = AppPreferences(context)
        val notifier = FakeAttendanceNotifier()
        atendimentoApi.myConversations = listOf(FakeAtendimentoApi.defaultQueueConversation().copy(id = 5, unreadCount = 3))

        buildWorker(notifier = notifier, appPreferences = appPreferences).doWork()
        buildWorker(notifier = notifier, appPreferences = appPreferences).doWork()

        assertEquals(1, notifier.notifiedConversationIds.size)
    }

    @Test
    fun `returns retry on a transient 500 failure`() = runTest {
        atendimentoApi.responseCode = 500
        val worker = buildWorker()

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Retry)
    }

    @Test
    fun `returns success (not retry) on 401 to avoid an infinite retry loop`() = runTest {
        atendimentoApi.responseCode = 401
        val worker = buildWorker()

        val result = worker.doWork()

        assertTrue(result is ListenableWorker.Result.Success)
    }
}
