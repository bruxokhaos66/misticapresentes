package br.com.misticapresentes.painel.atendimento.ui.detail

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.ShoppingBag
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import br.com.misticapresentes.painel.app.AppContainer
import br.com.misticapresentes.painel.app.ConversationViewModelFactory
import br.com.misticapresentes.painel.atendimento.model.MediaKind
import br.com.misticapresentes.painel.atendimento.model.Message
import br.com.misticapresentes.painel.atendimento.model.Product
import br.com.misticapresentes.painel.security.ScreenSecurity
import coil.compose.AsyncImage

private const val MAX_CONTENT_WIDTH_DP = 720

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConversationScreen(
    container: AppContainer,
    conversationId: Long,
    onBack: () -> Unit,
    viewModel: ConversationViewModel = viewModel(
        factory = remember(conversationId) { ConversationViewModelFactory(container, conversationId) },
    ),
) {
    val uiState by viewModel.uiState.collectAsState()

    val context = LocalContext.current
    DisposableEffect(Unit) {
        val activity = context as? Activity
        if (activity != null) ScreenSecurity.enable(activity)
        onDispose {
            if (activity != null) ScreenSecurity.disable(activity)
        }
    }

    val listState = rememberLazyListState()
    LaunchedEffect(listState) {
        androidx.compose.runtime.snapshotFlow { listState.firstVisibleItemIndex }
            .collect { index -> if (index == 0) viewModel.loadOlderMessages() }
    }

    // -------- Permissões de câmera/microfone e Photo Picker de galeria --------
    //
    // O Photo Picker (PickVisualMedia) não exige NENHUMA permissão de
    // runtime (é o motivo de existir) -- só câmera/microfone passam pelo
    // fluxo de shouldShowRequestPermissionRationale abaixo.
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            viewModel.openCamera()
        } else {
            val activity = context as? Activity
            val rationale = activity?.let {
                androidx.core.app.ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.CAMERA)
            } ?: false
            viewModel.onMediaPermissionDenied(MediaPermissionType.CAMERA, permanentlyDenied = !rationale)
        }
    }
    val microphonePermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            viewModel.openAudioRecorder()
        } else {
            val activity = context as? Activity
            val rationale = activity?.let {
                androidx.core.app.ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.RECORD_AUDIO)
            } ?: false
            viewModel.onMediaPermissionDenied(MediaPermissionType.MICROPHONE, permanentlyDenied = !rationale)
        }
    }
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri -> if (uri != null) viewModel.onGalleryImageSelected(uri) }

    fun requestCamera() {
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        if (granted) viewModel.openCamera() else cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
    }
    fun requestMicrophone() {
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        if (granted) viewModel.openAudioRecorder() else microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(uiState.conversation?.profileName?.takeIf { it.isNotBlank() } ?: "Conversa")
                },
                navigationIcon = {
                    IconButton(onClick = onBack, modifier = Modifier.semantics { contentDescription = "Voltar" }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = null)
                    }
                },
                actions = {
                    Box {
                        IconButton(
                            onClick = viewModel::openActionsMenu,
                            modifier = Modifier
                                .testTag("conversation_actions_button")
                                .semantics { contentDescription = "Ações do atendimento" },
                        ) {
                            Icon(Icons.Filled.MoreVert, contentDescription = null)
                        }
                        ActionsMenu(
                            expanded = uiState.isActionsMenuOpen,
                            actionInProgress = uiState.isActionInProgress,
                            onDismiss = viewModel::closeActionsMenu,
                            onClaim = viewModel::claim,
                            onRelease = { viewModel.release() },
                            onTransfer = viewModel::openTransferDialog,
                            onResolve = viewModel::resolve,
                        )
                    }
                },
            )
        },
        bottomBar = {
            Column(modifier = Modifier.widthIn(max = MAX_CONTENT_WIDTH_DP.dp)) {
                MessageComposer(
                    draftText = uiState.draftText,
                    isSending = uiState.isSending,
                    onDraftChanged = viewModel::onDraftChanged,
                    onSend = viewModel::sendText,
                    onOpenProductPicker = viewModel::openProductPicker,
                    onOpenCamera = ::requestCamera,
                    onOpenGallery = {
                        galleryLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
                    },
                    onOpenAudioRecorder = ::requestMicrophone,
                )
            }
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .widthIn(max = MAX_CONTENT_WIDTH_DP.dp)
                    .align(Alignment.TopCenter),
            ) {
                (uiState.infoMessage ?: uiState.errorMessage)?.let { message ->
                    Surface(
                        color = if (uiState.errorMessage != null) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                        ) {
                            Text(
                                text = message,
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.weight(1f).testTag("conversation_banner_message"),
                            )
                            TextButton(onClick = viewModel::dismissMessage) { Text("OK") }
                        }
                    }
                }

                AssignmentHistorySection(
                    expanded = uiState.isAssignmentHistoryExpanded,
                    history = uiState.assignmentHistory,
                    onToggle = viewModel::toggleAssignmentHistory,
                )

                when {
                    uiState.isLoading -> Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(modifier = Modifier.testTag("conversation_loading_indicator"))
                    }
                    uiState.messages.isEmpty() -> Box(modifier = Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                        Text(
                            text = "Nenhuma mensagem ainda.",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.testTag("conversation_empty_message"),
                        )
                    }
                    else -> {
                        LazyColumn(
                            state = listState,
                            modifier = Modifier.fillMaxSize().testTag("conversation_message_list"),
                        ) {
                            if (uiState.isLoadingOlderMessages) {
                                item {
                                    Box(modifier = Modifier.fillMaxWidth().padding(8.dp), contentAlignment = Alignment.Center) {
                                        CircularProgressIndicator(modifier = Modifier.size(20.dp))
                                    }
                                }
                            }
                            items(uiState.messages, key = { it.id }) { message ->
                                MessageBubble(message)
                            }
                        }
                    }
                }
            }
        }
    }

    if (uiState.isTransferDialogOpen) {
        TransferDialog(
            agents = uiState.agents,
            onDismiss = viewModel::closeTransferDialog,
            onConfirm = { targetUserId -> viewModel.transfer(targetUserId) },
        )
    }

    if (uiState.isProductPickerOpen) {
        ProductPickerSheet(
            products = uiState.productResults,
            isLoading = uiState.isProductPickerLoading,
            onQueryChanged = viewModel::searchProducts,
            onDismiss = viewModel::closeProductPicker,
            onProductSelected = { product -> viewModel.sendProduct(product.id) },
        )
    }

    uiState.media.cameraOutputFile?.let { outputFile ->
        CameraCaptureScreen(
            outputFile = outputFile,
            onCaptured = viewModel::onPhotoCaptured,
            onCancel = viewModel::closeCamera,
            onError = viewModel::onMediaError,
        )
    }

    uiState.media.audioOutputFile?.let { outputFile ->
        AudioRecorderSheet(
            outputFile = outputFile,
            pendingFile = uiState.media.pendingMedia?.takeIf { it.kind == MediaKind.AUDIO }?.file,
            pendingDurationMs = uiState.media.pendingMedia?.durationMs,
            onRecordingStarted = viewModel::onAudioRecordingStarted,
            onRecordingTick = viewModel::onAudioRecordingTick,
            onRecordingStopped = viewModel::onAudioRecordingStopped,
            onRecordingCancelled = viewModel::onAudioRecordingCancelled,
            onRecordingError = viewModel::onMediaError,
            onDismiss = viewModel::closeAudioRecorder,
            onSend = viewModel::sendPendingMedia,
            isUploading = uiState.media.isUploadingMedia,
            uploadProgress = uiState.media.uploadProgress,
        )
    }

    uiState.media.pendingMedia?.takeIf { it.kind == MediaKind.IMAGE }?.let { pending ->
        MediaPreviewDialog(
            pendingFile = pending.file,
            caption = pending.caption,
            isUploading = uiState.media.isUploadingMedia,
            uploadProgress = uiState.media.uploadProgress,
            onCaptionChanged = viewModel::onPendingMediaCaptionChanged,
            onCancel = viewModel::cancelPendingMedia,
            onCancelUpload = viewModel::cancelMediaUpload,
            onSend = viewModel::sendPendingMedia,
        )
    }

    uiState.media.permissionRationale?.let { permission ->
        AlertDialog(
            onDismissRequest = viewModel::dismissMediaPermissionDialog,
            modifier = Modifier.testTag("media_permission_rationale_dialog"),
            title = { Text("Permissão necessária") },
            text = { Text(mediaPermissionRationaleText(permission)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.dismissMediaPermissionDialog()
                        when (permission) {
                            MediaPermissionType.CAMERA -> cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                            MediaPermissionType.MICROPHONE -> microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    },
                    modifier = Modifier.testTag("media_permission_rationale_retry"),
                ) { Text("Tentar novamente") }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissMediaPermissionDialog) { Text("Cancelar") }
            },
        )
    }

    uiState.media.permissionPermanentlyDenied?.let { permission ->
        AlertDialog(
            onDismissRequest = viewModel::dismissMediaPermissionDialog,
            modifier = Modifier.testTag("media_permission_settings_dialog"),
            title = { Text("Permissão bloqueada") },
            text = { Text("${mediaPermissionRationaleText(permission)} Ative a permissão nas configurações do app.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.dismissMediaPermissionDialog()
                        context.startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.fromParts("package", context.packageName, null),
                            ),
                        )
                    },
                    modifier = Modifier.testTag("media_permission_settings_open"),
                ) { Text("Abrir configurações") }
            },
            dismissButton = {
                TextButton(onClick = viewModel::dismissMediaPermissionDialog) { Text("Cancelar") }
            },
        )
    }
}

private fun mediaPermissionRationaleText(permission: MediaPermissionType): String = when (permission) {
    MediaPermissionType.CAMERA -> "Precisamos da permissão de câmera para tirar fotos nesta conversa."
    MediaPermissionType.MICROPHONE -> "Precisamos da permissão de microfone para gravar áudios nesta conversa."
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MediaPreviewDialog(
    pendingFile: java.io.File,
    caption: String,
    isUploading: Boolean,
    uploadProgress: Float,
    onCaptionChanged: (String) -> Unit,
    onCancel: () -> Unit,
    onCancelUpload: () -> Unit,
    onSend: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { if (!isUploading) onCancel() },
        modifier = Modifier.testTag("media_preview_dialog"),
        title = { Text("Enviar foto") },
        text = {
            Column {
                AsyncImage(
                    model = pendingFile,
                    contentDescription = null,
                    modifier = Modifier.fillMaxWidth().heightIn(max = 240.dp).testTag("media_preview_image"),
                )
                OutlinedTextField(
                    value = caption,
                    onValueChange = onCaptionChanged,
                    enabled = !isUploading,
                    placeholder = { Text("Legenda (opcional)") },
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp).testTag("media_preview_caption_field"),
                )
                if (isUploading) {
                    LinearProgressIndicator(
                        progress = { uploadProgress },
                        modifier = Modifier.fillMaxWidth().padding(top = 8.dp).testTag("media_preview_upload_progress"),
                    )
                }
            }
        },
        confirmButton = {
            if (isUploading) {
                TextButton(onClick = onCancelUpload, modifier = Modifier.testTag("media_preview_cancel_upload")) {
                    Text("Cancelar envio")
                }
            } else {
                TextButton(onClick = onSend, modifier = Modifier.testTag("media_preview_send")) { Text("Enviar") }
            }
        },
        dismissButton = {
            if (!isUploading) {
                TextButton(onClick = onCancel, modifier = Modifier.testTag("media_preview_discard")) { Text("Descartar") }
            }
        },
    )
}

@Composable
private fun MessageBubble(message: Message) {
    val isOutbound = message.direction == "outbound"
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = if (isOutbound) Arrangement.End else Arrangement.Start,
    ) {
        Surface(
            color = if (isOutbound) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Column(modifier = Modifier.padding(10.dp)) {
                Text(
                    text = message.textBody ?: describeNonTextMessage(message),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Row(
                    modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = message.timestamp.orEmpty(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (isOutbound) {
                        Text(
                            text = message.status.orEmpty(),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(start = 8.dp),
                        )
                    }
                }
                if (isOutbound && !message.sentByAdmin.isNullOrBlank()) {
                    Text(
                        text = "Por: ${message.sentByAdmin}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

private fun describeNonTextMessage(message: Message): String = when (message.messageType) {
    "product" -> "Produto enviado"
    "template" -> "Template enviado"
    "image" -> "Imagem"
    "audio" -> "Áudio"
    else -> "Mensagem sem texto"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MessageComposer(
    draftText: String,
    isSending: Boolean,
    onDraftChanged: (String) -> Unit,
    onSend: () -> Unit,
    onOpenProductPicker: () -> Unit,
    onOpenCamera: () -> Unit,
    onOpenGallery: () -> Unit,
    onOpenAudioRecorder: () -> Unit,
) {
    Surface(tonalElevation = 2.dp) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            IconButton(
                onClick = onOpenProductPicker,
                enabled = !isSending,
                modifier = Modifier
                    .testTag("conversation_open_product_picker")
                    .semantics { contentDescription = "Enviar produto" },
            ) {
                Icon(Icons.Filled.ShoppingBag, contentDescription = null)
            }

            IconButton(
                onClick = onOpenCamera,
                enabled = !isSending,
                modifier = Modifier
                    .testTag("conversation_open_camera")
                    .semantics { contentDescription = "Tirar foto" },
            ) {
                Icon(Icons.Filled.CameraAlt, contentDescription = null)
            }

            IconButton(
                onClick = onOpenGallery,
                enabled = !isSending,
                modifier = Modifier
                    .testTag("conversation_open_gallery")
                    .semantics { contentDescription = "Enviar foto da galeria" },
            ) {
                Icon(Icons.Filled.PhotoLibrary, contentDescription = null)
            }

            IconButton(
                onClick = onOpenAudioRecorder,
                enabled = !isSending,
                modifier = Modifier
                    .testTag("conversation_open_audio_recorder")
                    .semantics { contentDescription = "Gravar áudio" },
            ) {
                Icon(Icons.Filled.Mic, contentDescription = null)
            }

            OutlinedTextField(
                value = draftText,
                onValueChange = onDraftChanged,
                placeholder = { Text("Digite uma mensagem") },
                modifier = Modifier
                    .weight(1f)
                    .heightIn(min = 48.dp)
                    .testTag("conversation_message_field")
                    .semantics { contentDescription = "Campo de mensagem" }
                    .onPreviewKeyEvent { event ->
                        // Enter de teclado físico (hardware) sem Shift envia a
                        // mensagem; teclado virtual não gera este KeyEvent para
                        // Enter (usa a IME action do teclado), então nunca
                        // interfere com quebra de linha no teclado virtual.
                        if (event.type == KeyEventType.KeyDown && event.key == Key.Enter && !event.nativeKeyEvent.isShiftPressed) {
                            onSend()
                            true
                        } else {
                            false
                        }
                    },
            )

            Spacer(modifier = Modifier.size(8.dp))

            IconButton(
                onClick = onSend,
                enabled = !isSending && draftText.isNotBlank(),
                modifier = Modifier
                    .testTag("conversation_send_button")
                    .semantics { contentDescription = "Enviar mensagem" },
            ) {
                if (isSending) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp))
                } else {
                    Icon(Icons.Filled.Send, contentDescription = null)
                }
            }
        }
    }
}

@Composable
private fun ActionsMenu(
    expanded: Boolean,
    actionInProgress: Boolean,
    onDismiss: () -> Unit,
    onClaim: () -> Unit,
    onRelease: () -> Unit,
    onTransfer: () -> Unit,
    onResolve: () -> Unit,
) {
    DropdownMenu(expanded = expanded, onDismissRequest = onDismiss) {
        DropdownMenuItem(
            text = { Text("Assumir") },
            enabled = !actionInProgress,
            onClick = onClaim,
            modifier = Modifier.testTag("conversation_action_claim"),
        )
        DropdownMenuItem(
            text = { Text("Liberar") },
            enabled = !actionInProgress,
            onClick = onRelease,
            modifier = Modifier.testTag("conversation_action_release"),
        )
        DropdownMenuItem(
            text = { Text("Transferir") },
            enabled = !actionInProgress,
            onClick = onTransfer,
            modifier = Modifier.testTag("conversation_action_transfer"),
        )
        DropdownMenuItem(
            text = { Text("Resolver") },
            enabled = !actionInProgress,
            onClick = onResolve,
            modifier = Modifier.testTag("conversation_action_resolve"),
        )
    }
}

@Composable
private fun AssignmentHistorySection(
    expanded: Boolean,
    history: List<br.com.misticapresentes.painel.atendimento.model.AssignmentHistoryEntry>,
    onToggle: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxWidth()) {
        TextButton(onClick = onToggle, modifier = Modifier.testTag("conversation_history_toggle")) {
            Text(if (expanded) "Ocultar histórico de atribuição" else "Ver histórico de atribuição")
        }
        if (expanded) {
            if (history.isEmpty()) {
                Text(
                    text = "Sem histórico registrado.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            } else {
                Column(modifier = Modifier.padding(horizontal = 16.dp)) {
                    history.forEach { entry ->
                        Text(
                            text = "${entry.action ?: "-"} • ${entry.createdAt ?: "-"}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun TransferDialog(
    agents: List<br.com.misticapresentes.painel.atendimento.model.Agent>,
    onDismiss: () -> Unit,
    onConfirm: (Long) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag("conversation_transfer_dialog"),
        title = { Text("Transferir conversa") },
        text = {
            if (agents.isEmpty()) {
                Text("Carregando atendentes...")
            } else {
                Column {
                    agents.forEach { agent ->
                        TextButton(
                            onClick = { onConfirm(agent.id) },
                            modifier = Modifier.fillMaxWidth().testTag("conversation_transfer_agent_${agent.id}"),
                        ) {
                            Text("${agent.nome} (${agent.activeConversations} ativas)")
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancelar") }
        },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProductPickerSheet(
    products: List<Product>,
    isLoading: Boolean,
    onQueryChanged: (String) -> Unit,
    onDismiss: () -> Unit,
    onProductSelected: (Product) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()
    var query by remember { mutableStateOf("") }

    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
        modifier = Modifier.testTag("product_picker_sheet"),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("Enviar produto", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = query,
                onValueChange = {
                    query = it
                    onQueryChanged(it)
                },
                placeholder = { Text("Buscar por nome ou SKU") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp)
                    .testTag("product_picker_search_field"),
            )

            if (isLoading) {
                Box(modifier = Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(modifier = Modifier.testTag("product_picker_loading"))
                }
            } else if (products.isEmpty()) {
                Text(
                    text = "Nenhum produto encontrado.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(24.dp).testTag("product_picker_empty"),
                )
            } else {
                LazyColumn(modifier = Modifier.heightIn(max = 420.dp)) {
                    items(products, key = { it.id }) { product ->
                        ProductRow(product = product, onClick = { onProductSelected(product) })
                    }
                }
            }
        }
    }
}

@Composable
private fun ProductRow(product: Product, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
            .testTag("product_picker_item_${product.id}")
            .semantics { contentDescription = "Enviar produto ${product.nome}" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (product.imagemUrl != null) {
            AsyncImage(
                model = product.imagemUrl,
                contentDescription = null,
                modifier = Modifier.size(48.dp),
            )
            Spacer(modifier = Modifier.size(12.dp))
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(text = product.nome, style = MaterialTheme.typography.bodyLarge)
            Text(
                text = "R$ %.2f".format(product.precoPromocional ?: product.preco),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!product.disponivel) {
                Text(
                    text = "Indisponível",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
        Button(onClick = onClick, enabled = product.disponivel, modifier = Modifier.testTag("product_picker_send_${product.id}")) {
            Text("Enviar")
        }
    }
}
