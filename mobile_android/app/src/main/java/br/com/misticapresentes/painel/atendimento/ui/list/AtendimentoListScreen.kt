package br.com.misticapresentes.painel.atendimento.ui.list

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import br.com.misticapresentes.painel.app.MisticaViewModelFactory
import br.com.misticapresentes.painel.atendimento.model.Conversation
import br.com.misticapresentes.painel.atendimento.model.ConversationFilter
import br.com.misticapresentes.painel.atendimento.ui.common.syncStatusLabel
import br.com.misticapresentes.painel.security.ScreenSecurity

private const val MAX_CONTENT_WIDTH_DP = 720

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AtendimentoListScreen(
    factory: MisticaViewModelFactory,
    onOpenConversation: (Long) -> Unit,
    onBack: () -> Unit,
    viewModel: AtendimentoListViewModel = viewModel(factory = factory),
) {
    val uiState by viewModel.uiState.collectAsState()

    // FLAG_SECURE enquanto esta tela (dados de clientes) estiver visível --
    // mesmo padrão de LegacyPanelActivity, desligado ao sair da tela.
    val context = LocalContext.current
    DisposableEffect(Unit) {
        val activity = context as? Activity
        if (activity != null) ScreenSecurity.enable(activity)
        onDispose {
            if (activity != null) ScreenSecurity.disable(activity)
        }
    }

    // Sincronização em primeiro plano (PR #414): liga/desliga o polling só
    // enquanto esta tela está de fato visível (ON_RESUME/ON_PAUSE) -- nunca
    // recriado a cada recomposição, pois a chave do DisposableEffect é o
    // par (lifecycleOwner, viewModel), estável entre recomposições da mesma
    // tela; `onScreenResumed()` também é chamado uma vez de imediato, já que
    // a tela pode já estar em RESUMED quando este efeito entra em execução.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, viewModel) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> viewModel.onScreenResumed()
                Lifecycle.Event.ON_PAUSE -> viewModel.onScreenPaused()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        viewModel.onScreenResumed()
        onDispose {
            viewModel.onScreenPaused()
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Central de Atendimento")
                        if (uiState.totalUnreadCount > 0) {
                            Spacer(modifier = Modifier.size(8.dp))
                            Surface(
                                color = MaterialTheme.colorScheme.error,
                                shape = CircleShape,
                                modifier = Modifier.testTag("atendimento_unread_badge"),
                            ) {
                                Text(
                                    text = uiState.totalUnreadCount.coerceAtMost(99).toString(),
                                    color = MaterialTheme.colorScheme.onError,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                )
                            }
                        }
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack, modifier = Modifier.semantics { contentDescription = "Voltar" }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    IconButton(
                        onClick = viewModel::refresh,
                        modifier = Modifier
                            .testTag("atendimento_refresh_button")
                            .semantics { contentDescription = "Atualizar lista" },
                    ) {
                        Icon(Icons.Filled.Refresh, contentDescription = null)
                    }
                },
            )
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .widthIn(max = MAX_CONTENT_WIDTH_DP.dp)
                    .align(Alignment.TopCenter),
            ) {
                if (!uiState.isOnline) {
                    Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = Modifier.fillMaxWidth()) {
                        Text(
                            text = "Sem conexão com a internet.",
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(12.dp).testTag("atendimento_offline_banner"),
                        )
                    }
                } else {
                    // Indicador discreto de sincronização (PR #414) -- só um
                    // texto pequeno, nunca um diálogo/snackbar repetido a
                    // cada ciclo de polling.
                    syncStatusLabel(uiState.syncStatus)?.let { label ->
                        Text(
                            text = label,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier
                                .padding(horizontal = 16.dp, vertical = 4.dp)
                                .testTag("atendimento_sync_status"),
                        )
                    }
                }

                SingleChoiceSegmentedButtonRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                ) {
                    val visibleFilters = if (uiState.canSeeAllTab) {
                        listOf(ConversationFilter.MINE, ConversationFilter.QUEUE, ConversationFilter.ALL)
                    } else {
                        listOf(ConversationFilter.MINE, ConversationFilter.QUEUE)
                    }
                    visibleFilters.forEachIndexed { index, filter ->
                        SegmentedButton(
                            selected = uiState.filter == filter,
                            onClick = { viewModel.onFilterSelected(filter) },
                            shape = SegmentedButtonDefaults.itemShape(index = index, count = visibleFilters.size),
                            modifier = Modifier.testTag("atendimento_filter_${filter.name.lowercase()}"),
                        ) {
                            Text(filter.label())
                        }
                    }
                }

                when {
                    uiState.isLoading -> LoadingBody()
                    uiState.errorMessage != null -> ErrorBody(message = uiState.errorMessage.orEmpty(), onRetry = viewModel::refresh)
                    uiState.conversations.isEmpty() -> EmptyBody(filter = uiState.filter)
                    else -> ConversationList(
                        conversations = uiState.conversations,
                        agentNamesById = uiState.agentNamesById,
                        onOpenConversation = onOpenConversation,
                    )
                }
            }

            if (uiState.isRefreshing) {
                CircularProgressIndicator(
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(top = 8.dp)
                        .size(28.dp)
                        .testTag("atendimento_refreshing_indicator"),
                )
            }
        }
    }
}

@Composable
private fun LoadingBody() {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(modifier = Modifier.testTag("atendimento_loading_indicator"))
    }
}

@Composable
private fun ErrorBody(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.error,
            modifier = Modifier.testTag("atendimento_error_message"),
        )
        Spacer(modifier = Modifier.size(16.dp))
        OutlinedButton(onClick = onRetry, modifier = Modifier.testTag("atendimento_retry_button")) {
            Text("Tentar novamente")
        }
    }
}

@Composable
private fun EmptyBody(filter: ConversationFilter) {
    val message = when (filter) {
        ConversationFilter.MINE -> "Você ainda não tem conversas em atendimento."
        ConversationFilter.QUEUE -> "Nenhuma conversa aguardando na fila."
        ConversationFilter.ALL -> "Nenhuma conversa encontrada."
    }
    Box(modifier = Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(
            text = message,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("atendimento_empty_message"),
        )
    }
}

@Composable
private fun ConversationList(
    conversations: List<Conversation>,
    agentNamesById: Map<Long, String>,
    onOpenConversation: (Long) -> Unit,
) {
    LazyColumn(modifier = Modifier.fillMaxSize().testTag("atendimento_conversation_list")) {
        items(conversations, key = { it.id }) { conversation ->
            ConversationRow(
                conversation = conversation,
                assignedName = conversation.assignedUserId?.let { agentNamesById[it] },
                onClick = { onOpenConversation(conversation.id) },
            )
            HorizontalDivider()
        }
    }
}

@Composable
private fun ConversationRow(
    conversation: Conversation,
    assignedName: String?,
    onClick: () -> Unit,
) {
    val displayName = conversation.profileName?.takeIf { it.isNotBlank() } ?: "Cliente"
    val phoneSuffix = conversation.phoneLast4?.let { "•••$it" } ?: "sem telefone"
    val lastContact = conversation.lastMessageAt ?: conversation.lastInboundAt ?: conversation.createdAt
    val responsavel = assignedName ?: conversation.assignedUserId?.toString() ?: "—"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .semantics {
                contentDescription = buildString {
                    append("Conversa com $displayName, telefone $phoneSuffix")
                    if (conversation.unreadCount > 0) append(", ${conversation.unreadCount} não lidas")
                    conversation.status?.let { append(", status $it") }
                }
            },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (conversation.unreadCount > 0) {
            Box(
                modifier = Modifier
                    .size(10.dp)
                    .background(MaterialTheme.colorScheme.secondary, CircleShape)
                    .testTag("atendimento_unread_dot_${conversation.id}"),
            )
            Spacer(modifier = Modifier.size(8.dp))
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(text = displayName, style = MaterialTheme.typography.titleMedium)
            Text(
                text = phoneSuffix,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "Responsável: $responsavel",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            lastContact?.let {
                Text(
                    text = "Último contato: $it",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Column(horizontalAlignment = Alignment.End) {
            conversation.status?.let {
                Text(text = it, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
            if (conversation.unreadCount > 0) {
                Text(
                    text = "${conversation.unreadCount}",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
        }
    }
}

private fun ConversationFilter.label(): String = when (this) {
    ConversationFilter.MINE -> "Minhas"
    ConversationFilter.QUEUE -> "Fila"
    ConversationFilter.ALL -> "Todas"
}
