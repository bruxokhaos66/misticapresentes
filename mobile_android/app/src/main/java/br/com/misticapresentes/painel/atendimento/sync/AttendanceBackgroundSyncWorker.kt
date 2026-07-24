package br.com.misticapresentes.painel.atendimento.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.common.AppPreferences
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.network.ApiError
import br.com.misticapresentes.painel.network.ApiResult
import br.com.misticapresentes.painel.notifications.AttendanceNotifier
import br.com.misticapresentes.painel.security.SecureSessionStore
import kotlinx.coroutines.flow.first

/**
 * Worker de background da Central de Atendimento (PR #414).
 *
 * Escopo DELIBERADAMENTE pequeno: nunca substitui o polling em primeiro
 * plano (esse cobre conversa aberta/lista/fila com intervalo curto -- ver
 * [SyncConfig]). Este Worker só faz uma checagem leve e periódica ("o app
 * está fechado/em background há um tempo, há alguma mensagem nova?") para
 * poder disparar uma notificação local -- nunca baixa/mantém histórico de
 * mensagens.
 *
 * Guardas de segurança verificadas DENTRO do próprio `doWork` (nunca só na
 * hora de agendar o trabalho, já que o Android pode rodar um Worker
 * agendado antes de um cancelamento assíncrono ser processado):
 * 1. `BACKGROUND_SYNC_ENABLED` desligada -> sucesso imediato, nenhuma
 *    chamada de rede.
 * 2. Sem sessão local (`SecureSessionStore.hasSession()`) -> sucesso
 *    imediato, nenhuma chamada de rede (nunca tenta autenticar em
 *    background, e nunca roda depois de um logout que ainda não cancelou o
 *    agendamento).
 * 3. `ATTENDANCE_NOTIFICATIONS_ENABLED` desligada -> ainda sincroniza (para
 *    manter o contador salvo em dia), mas nunca dispara notificação.
 *
 * Não persiste NENHUM conteúdo de mensagem/cliente -- só um inteiro (total
 * de não lidas já visto) em [AppPreferences], que já é o armazenamento
 * usado para dado explicitamente não sensível deste app.
 */
class AttendanceBackgroundSyncWorker(
    context: Context,
    params: WorkerParameters,
    private val secureSessionStore: SecureSessionStore,
    private val featureFlagsRepository: FeatureFlagsRepository,
    private val repository: AtendimentoRepository,
    private val notifier: AttendanceNotifier,
    private val appPreferences: AppPreferences,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val backgroundSyncEnabled = featureFlagsRepository.isEnabled(FeatureFlag.BACKGROUND_SYNC_ENABLED).first()
        if (!backgroundSyncEnabled) return Result.success()

        if (!secureSessionStore.hasSession()) return Result.success()

        val notificationsEnabled = featureFlagsRepository.isEnabled(FeatureFlag.ATTENDANCE_NOTIFICATIONS_ENABLED).first()

        return when (val result = repository.listMine(page = 1, pageSize = SyncConfig.BACKGROUND_SYNC_PAGE_SIZE)) {
            is ApiResult.Success -> {
                if (notificationsEnabled) {
                    val previousTotal = appPreferences.lastKnownUnreadTotal.first()
                    val currentTotal = result.data.items.sumOf { it.unreadCount }
                    if (currentTotal > previousTotal) {
                        // Deep link para a conversa específica só quando dá
                        // para identificar uma única candidata óbvia (maior
                        // unreadCount); senão abre a lista (ver AttendanceNotifier
                        // e o tratamento do deep link em MainActivity).
                        val target = result.data.items.maxByOrNull { it.unreadCount }
                        notifier.notifyNewMessage(target?.id ?: 0L)
                    }
                    appPreferences.setLastKnownUnreadTotal(currentTotal)
                }
                Result.success()
            }
            is ApiResult.Failure -> when (result.error) {
                // 401/403: sessão inválida/sem permissão -- tentar de novo
                // não resolve nada (não é uma falha transiente) e retry aqui
                // criaria exatamente o loop infinito que este Worker precisa
                // evitar; sucesso "vazio" e deixa a sessão expirada ser
                // tratada da forma normal quando o app voltar ao primeiro
                // plano (AuthInterceptor/SessionExpiryInterceptor).
                is ApiError.Unauthorized, is ApiError.Forbidden -> Result.success()
                // Falhas transientes (timeout, sem conexão, 5xx, 429, DNS
                // via IOException): deixa o WorkManager reagendar com o
                // BackoffPolicy.EXPONENTIAL já configurado no agendamento.
                else -> Result.retry()
            }
        }
    }
}
