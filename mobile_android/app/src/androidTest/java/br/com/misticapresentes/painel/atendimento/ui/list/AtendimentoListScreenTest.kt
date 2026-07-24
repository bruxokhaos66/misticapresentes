package br.com.misticapresentes.painel.atendimento.ui.list

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
import br.com.misticapresentes.painel.testutil.FakeMisticaApi
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import br.com.misticapresentes.painel.ui.theme.MisticaTheme
import kotlinx.coroutines.runBlocking
import org.junit.Rule
import org.junit.Test

/**
 * Testes instrumentados de [AtendimentoListScreen] -- ViewModel construído
 * com [FakeAtendimentoApi] (nunca rede real), só a Compose UI é exercitada
 * de verdade aqui (mesmo padrão de `ui/login/LoginScreenTest.kt`).
 */
class AtendimentoListScreenTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    private fun buildViewModel(api: FakeAtendimentoApi): AtendimentoListViewModel {
        val store = FakeSecureSessionStore()
        val authRepository = AuthRepository(FakeMisticaApi(), store, PersistentCookieJar(store))
        runBlocking { authRepository.login("luna", "senha-correta") }
        return AtendimentoListViewModel(
            repository = AtendimentoRepository(api),
            authRepository = authRepository,
            connectivityObserver = FakeConnectivityObserver(initiallyOnline = true),
        )
    }

    @Test
    fun listRendersConversationItem() {
        val api = FakeAtendimentoApi()
        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                AtendimentoListScreen(
                    factory = factory,
                    onOpenConversation = {},
                    onBack = {},
                    viewModel = buildViewModel(api),
                )
            }
        }

        composeRule.waitForIdle()
        composeRule.onNodeWithTag("atendimento_conversation_list").assertIsDisplayed()
    }

    @Test
    fun emptyStateIsShownWhenNoConversations() {
        val api = FakeAtendimentoApi().apply { myConversations = emptyList() }
        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                AtendimentoListScreen(
                    factory = factory,
                    onOpenConversation = {},
                    onBack = {},
                    viewModel = buildViewModel(api),
                )
            }
        }

        composeRule.waitForIdle()
        composeRule.onNodeWithTag("atendimento_empty_message").assertIsDisplayed()
    }

    @Test
    fun errorStateShowsRetryButton() {
        val api = FakeAtendimentoApi().apply { responseCode = 500 }
        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                AtendimentoListScreen(
                    factory = factory,
                    onOpenConversation = {},
                    onBack = {},
                    viewModel = buildViewModel(api),
                )
            }
        }

        composeRule.waitForIdle()
        composeRule.onNodeWithTag("atendimento_error_message").assertIsDisplayed()
        composeRule.onNodeWithTag("atendimento_retry_button").assertIsDisplayed()
    }
}
