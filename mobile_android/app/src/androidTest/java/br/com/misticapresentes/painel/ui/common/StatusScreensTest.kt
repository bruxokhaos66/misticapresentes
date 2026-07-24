package br.com.misticapresentes.painel.ui.common

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import br.com.misticapresentes.painel.ui.theme.MisticaTheme
import org.junit.Rule
import org.junit.Test

class StatusScreensTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun noConnectionScreenRetryButtonTriggersCallback() {
        var retried = false
        composeRule.setContent {
            MisticaTheme { NoConnectionScreen(onRetry = { retried = true }) }
        }

        composeRule.onNodeWithTag("no_connection_retry_button").performClick()
        assert(retried)
    }

    @Test
    fun sessionExpiredScreenLoginButtonTriggersCallback() {
        var wentToLogin = false
        composeRule.setContent {
            MisticaTheme { SessionExpiredScreen(onGoToLogin = { wentToLogin = true }) }
        }

        composeRule.onNodeWithTag("session_expired_login_button").assertIsDisplayed()
        composeRule.onNodeWithTag("session_expired_login_button").performClick()
        assert(wentToLogin)
    }
}
