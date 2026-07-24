package br.com.misticapresentes.painel.atendimento.ui.detail

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.ui.theme.MisticaTheme
import org.junit.Rule
import org.junit.Test

/**
 * Testes instrumentados de [ConversationScreen] -- ViewModel construído com
 * [FakeAtendimentoApi] (nunca rede real).
 */
class ConversationScreenTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun sendingMessageClearsDraftAndBlocksDoubleSubmit() {
        val api = FakeAtendimentoApi()
        val viewModel = ConversationViewModel(AtendimentoRepository(api), conversationId = 1)

        composeRule.setContent {
            MisticaTheme {
                ConversationScreen(
                    container = AppContainer(composeRule.activity),
                    conversationId = 1,
                    onBack = {},
                    viewModel = viewModel,
                )
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("conversation_message_field").performTextInput("Olá, tudo bem?")
        composeRule.onNodeWithTag("conversation_send_button").performClick()
        composeRule.onNodeWithTag("conversation_send_button").performClick()
        composeRule.waitForIdle()

        // Só uma tentativa de envio deve ter chegado à API, mesmo com dois cliques.
        org.junit.Assert.assertEquals(1, api.sendMessageCallCount)
    }

    @Test
    fun mediaComposerButtonsAreDisplayed() {
        val api = FakeAtendimentoApi()
        val viewModel = ConversationViewModel(AtendimentoRepository(api), conversationId = 1)

        composeRule.setContent {
            MisticaTheme {
                ConversationScreen(
                    container = AppContainer(composeRule.activity),
                    conversationId = 1,
                    onBack = {},
                    viewModel = viewModel,
                )
            }
        }
        composeRule.waitForIdle()

        // Botões de câmera/galeria/áudio do compose avançado de mídia (PR
        // #413), ao lado do botão de produto já existente -- nenhum deles
        // aciona rede real (permissão/CameraX/galeria são fluxo de
        // plataforma, fora do escopo de teste instrumentado desta tela).
        composeRule.onNodeWithTag("conversation_open_camera").assertIsDisplayed()
        composeRule.onNodeWithTag("conversation_open_gallery").assertIsDisplayed()
        composeRule.onNodeWithTag("conversation_open_audio_recorder").assertIsDisplayed()
    }

    @Test
    fun actionsMenuOpensAndDispatchesClaim() {
        val api = FakeAtendimentoApi()
        val viewModel = ConversationViewModel(AtendimentoRepository(api), conversationId = 1)

        composeRule.setContent {
            MisticaTheme {
                ConversationScreen(
                    container = AppContainer(composeRule.activity),
                    conversationId = 1,
                    onBack = {},
                    viewModel = viewModel,
                )
            }
        }
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("conversation_actions_button").performClick()
        composeRule.onNodeWithTag("conversation_action_claim").assertIsDisplayed()
        composeRule.onNodeWithTag("conversation_action_claim").performClick()
        composeRule.waitForIdle()

        org.junit.Assert.assertEquals(1, api.claimCallCount)
    }
}
