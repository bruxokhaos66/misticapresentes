package br.com.misticapresentes.painel

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import br.com.misticapresentes.painel.app.MisticaApplication
import br.com.misticapresentes.painel.legacy.LegacyPanelActivity
import br.com.misticapresentes.painel.navigation.MisticaNavHost
import br.com.misticapresentes.painel.ui.theme.MisticaTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val container = (application as MisticaApplication).container

        setContent {
            MisticaTheme {
                MisticaNavHost(
                    container = container,
                    onOpenLegacyPanel = { startActivity(Intent(this, LegacyPanelActivity::class.java)) },
                    onEnterLegacyOnly = {
                        startActivity(Intent(this, LegacyPanelActivity::class.java))
                        finish()
                    },
                )
            }
        }
    }
}
