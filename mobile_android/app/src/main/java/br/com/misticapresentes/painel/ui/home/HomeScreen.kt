package br.com.misticapresentes.painel.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.common.Environment

@Composable
fun HomeScreen(
    factory: MisticaViewModelFactory,
    onOpenLegacyPanel: () -> Unit,
    onOpenAtendimento: () -> Unit,
    onLoggedOut: () -> Unit,
    viewModel: HomeViewModel = viewModel(factory = factory),
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(uiState.loggedOut) {
        if (uiState.loggedOut) onLoggedOut()
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "🌙 Mística",
                    style = MaterialTheme.typography.headlineSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                br.com.misticapresentes.painel.ui.common.EnvironmentBadge(Environment.current())
            }

            Text(
                text = uiState.userName.ifBlank { "Usuário" },
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
            )
            Text(
                text = "Perfil: ${uiState.userProfile.ifBlank { "-" }}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = if (uiState.isOnline) "Conectado" else "Sem conexão",
                style = MaterialTheme.typography.bodyMedium,
                color = if (uiState.isOnline) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics {
                    contentDescription = if (uiState.isOnline) "Status: conectado" else "Status: sem conexão"
                },
            )

            Button(
                onClick = onOpenLegacyPanel,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("open_legacy_button"),
            ) {
                Text("Abrir painel legado")
            }

            Text(
                text = "Em breve",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp),
            )
            OutlinedButton(
                onClick = onOpenAtendimento,
                enabled = uiState.nativeWhatsAppEnabled,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("open_atendimento_button"),
            ) {
                Text("Central de Atendimento")
            }
            OutlinedButton(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) {
                Text("Dashboard")
            }
            OutlinedButton(onClick = {}, enabled = false, modifier = Modifier.fillMaxWidth()) {
                Text("Notificações")
            }

            Button(
                onClick = viewModel::logout,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp)
                    .testTag("logout_button"),
            ) {
                Text("Sair")
            }
        }
    }
}
