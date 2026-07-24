package br.com.misticapresentes.painel.ui.login

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.ui.theme.MisticaTheme
import org.junit.Rule
import org.junit.Test

class LoginScreenTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun submittingEmptyFieldsShowsValidationError() {
        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                LoginScreen(factory = factory, onLoginSuccess = {})
            }
        }

        composeRule.onNodeWithTag("login_button").performClick()
        composeRule.onNodeWithTag("login_error").assertIsDisplayed()
    }

    @Test
    fun fieldsAcceptInput() {
        composeRule.setContent {
            val factory = MisticaViewModelFactory(AppContainer(composeRule.activity))
            MisticaTheme {
                LoginScreen(factory = factory, onLoginSuccess = {})
            }
        }

        composeRule.onNodeWithTag("login_field").performTextInput("vendedora")
        composeRule.onNodeWithTag("senha_field").performTextInput("segredo123")
        composeRule.onNodeWithTag("login_button").assertIsDisplayed()
    }
}
