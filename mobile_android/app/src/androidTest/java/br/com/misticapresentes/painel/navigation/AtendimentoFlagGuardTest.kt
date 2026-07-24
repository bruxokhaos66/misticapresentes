package br.com.misticapresentes.painel.navigation

import androidx.activity.ComponentActivity
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertDoesNotExist
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.atendimento.ui.detail.ConversationScreen
import br.com.misticapresentes.painel.atendimento.ui.detail.ConversationViewModel
import br.com.misticapresentes.painel.atendimento.ui.list.AtendimentoListScreen
import br.com.misticapresentes.painel.atendimento.ui.list.AtendimentoListViewModel
import br.com.misticapresentes.painel.auth.AuthRepository
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import br.com.misticapresentes.painel.network.PersistentCookieJar
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeConnectivityObserver
import br.com.misticapresentes.painel.testutil.FakeFeatureFlagsRepository
import br.com.misticapresentes.painel.testutil.FakeMisticaApi
import br.com.misticapresentes.painel.testutil.FakeSecureSessionStore
import br.com.misticapresentes.painel.ui.theme.MisticaTheme
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

/**
 * Testes instrumentados de [AtendimentoFlagGuard] -- cobre a defesa em
 * profundidade da flag `NATIVE_WHATSAPP_ENABLED` (PR #412, rodada de ajustes
 * de robustez): a Central de Atendimento não deve renderizar nem instanciar
 * ViewModel/Repository quando a flag está desligada, tanto no guard isolado
 * quanto acoplado ao conteúdo real das telas (lista/detalhe) por trás dele.
 */
class AtendimentoFlagGuardTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    // -------- Guard isolado (sem depender das telas reais da Central) --------

    @Test
    fun contentIsNotRenderedAndOnDeniedFiresWhenFlagIsFalse() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to false))
        var deniedCalls = 0

        composeRule.setContent {
            AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                Text("conteúdo protegido", modifier = Modifier.testTag("guard_content"))
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("guard_content").assertDoesNotExist()
        assertTrue("onDenied deveria ter sido chamado ao menos uma vez", deniedCalls >= 1)
    }

    @Test
    fun contentRendersNormallyWhenFlagIsTrue() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to true))
        var deniedCalls = 0

        composeRule.setContent {
            AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                Text("conteúdo protegido", modifier = Modifier.testTag("guard_content"))
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("guard_content").assertIsDisplayed()
        assertEquals(0, deniedCalls)
    }

    @Test
    fun guardReevaluatesFlagAndRevokesAccessWhenItTurnsFalseWhileMounted() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to true))
        var deniedCalls = 0

        composeRule.setContent {
            AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                Text("conteúdo protegido", modifier = Modifier.testTag("guard_content"))
            }
        }
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("guard_content").assertIsDisplayed()
        assertEquals(0, deniedCalls)

        // Simula a flag sendo desligada enquanto a tela ainda está montada
        // (ex.: restauração de back stack com um valor de flag diferente do
        // que havia quando a rota foi originalmente aberta).
        runBlocking { flags.setEnabled(FeatureFlag.NATIVE_WHATSAPP_ENABLED, false) }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("guard_content").assertDoesNotExist()
        assertEquals(1, deniedCalls)
    }

    // -------- Guard acoplado às telas reais da Central (fim a fim) --------

    private fun buildListViewModel(api: FakeAtendimentoApi): AtendimentoListViewModel {
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
    fun atendimentoListScreenNeverCallsApiWhenFlagIsFalse() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to false))
        val api = FakeAtendimentoApi()
        var deniedCalls = 0

        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                    AtendimentoListScreen(
                        factory = factory,
                        onOpenConversation = {},
                        onBack = {},
                        viewModel = buildListViewModel(api),
                    )
                }
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("atendimento_conversation_list").assertDoesNotExist()
        assertTrue(deniedCalls >= 1)
        assertTrue("nenhuma chamada de API deveria ter acontecido com a flag desligada", api.callLog.isEmpty())
    }

    @Test
    fun conversationScreenNeverCallsApiWhenFlagIsFalse() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to false))
        val api = FakeAtendimentoApi()
        var deniedCalls = 0

        composeRule.setContent {
            MisticaTheme {
                AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                    ConversationScreen(
                        container = AppContainer(composeRule.activity),
                        conversationId = 1,
                        onBack = {},
                        viewModel = ConversationViewModel(AtendimentoRepository(api), conversationId = 1),
                    )
                }
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("conversation_message_field").assertDoesNotExist()
        assertTrue(deniedCalls >= 1)
        assertTrue("nenhuma chamada de API deveria ter acontecido com a flag desligada", api.callLog.isEmpty())
    }

    @Test
    fun atendimentoListScreenRendersAndCallsApiWhenFlagIsTrue() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to true))
        val api = FakeAtendimentoApi()
        var deniedCalls = 0

        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                AtendimentoFlagGuard(featureFlagsRepository = flags, onDenied = { deniedCalls++ }) {
                    AtendimentoListScreen(
                        factory = factory,
                        onOpenConversation = {},
                        onBack = {},
                        viewModel = buildListViewModel(api),
                    )
                }
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("atendimento_conversation_list").assertIsDisplayed()
        assertEquals(0, deniedCalls)
        assertTrue("a tela real deveria ter chamado a API com a flag ligada", api.callLog.isNotEmpty())
    }

    // -------- Guard acoplado à navegação (redireciona para Home) --------

    /**
     * NavHost mínimo que reproduz só o trecho relevante de [MisticaNavHost]
     * (HOME + ATENDIMENTO_LIST atrás do guard) -- evita depender de
     * Splash/Login/autenticação reais (irrelevantes para este comportamento)
     * só para poder observar o redirecionamento de verdade via
     * NavHostController, com `popUpTo` limpando a pilha da Central.
     */
    @Composable
    private fun TestGuardedNavHost(
        featureFlagsRepository: FeatureFlagsRepository,
        navController: NavHostController,
        listViewModel: AtendimentoListViewModel,
    ) {
        NavHost(navController = navController, startDestination = NavRoutes.ATENDIMENTO_LIST) {
            composable(NavRoutes.HOME) {
                Text("Home", modifier = Modifier.testTag("test_home_screen"))
            }
            composable(NavRoutes.ATENDIMENTO_LIST) {
                // Este NavHost de teste começa direto em ATENDIMENTO_LIST (sem
                // Home ainda empilhada) para simular navegação programática
                // direta pulando o botão da Home -- por isso o redirecionamento
                // aqui não usa popUpTo(HOME) (que exigiria Home já na pilha,
                // como acontece de fato em [MisticaNavHost]); popUpTo(0) limpa
                // tudo e deixa só a Home, o que também satisfaz "nunca deixar a
                // rota nativa acessível via voltar".
                AtendimentoFlagGuard(
                    featureFlagsRepository = featureFlagsRepository,
                    onDenied = {
                        navController.navigate(NavRoutes.HOME) {
                            popUpTo(0)
                        }
                    },
                ) {
                    AtendimentoListScreen(
                        factory = MisticaViewModelFactory(AppContainer(composeRule.activity)),
                        onOpenConversation = {},
                        onBack = {},
                        viewModel = listViewModel,
                    )
                }
            }
        }
    }

    @Test
    fun openingAtendimentoListDirectlyWithFlagFalseEndsUpOnHome() {
        val flags = FakeFeatureFlagsRepository(mapOf(FeatureFlag.NATIVE_WHATSAPP_ENABLED to false))
        val api = FakeAtendimentoApi()
        lateinit var navController: NavHostController

        composeRule.setContent {
            navController = rememberNavController()
            MisticaTheme {
                // Navegação programática direta para ATENDIMENTO_LIST (pulando o
                // botão da Home) -- é o startDestination deste NavHost de teste.
                TestGuardedNavHost(
                    featureFlagsRepository = flags,
                    navController = navController,
                    listViewModel = buildListViewModel(api),
                )
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("test_home_screen").assertIsDisplayed()
        assertEquals(NavRoutes.HOME, navController.currentDestination?.route)
        assertTrue("nenhuma chamada de API deveria ter acontecido antes do redirecionamento", api.callLog.isEmpty())
    }
}
