package br.com.misticapresentes.painel.atendimento.ui.detail

import android.media.MediaPlayer
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import br.com.misticapresentes.painel.atendimento.media.AudioRecorderController
import br.com.misticapresentes.painel.atendimento.media.formatRecordingDuration
import java.io.File
import kotlinx.coroutines.delay

/**
 * Bottom sheet de gravação de áudio: o MediaRecorder real (via
 * [AudioRecorderController]) e o MediaPlayer de pré-escuta vivem só aqui --
 * o ViewModel nunca guarda nenhum dos dois, só recebe eventos terminais
 * (iniciado/parado/cancelado/erro), mesmo desenho de [CameraCaptureScreen].
 *
 * Nota de cobertura: como [CameraCaptureScreen], a gravação/reprodução real
 * depende de hardware de áudio e não é coberta por teste automatizado nesta
 * PR -- limitação conhecida documentada no relatório final.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AudioRecorderSheet(
    outputFile: File,
    pendingFile: File?,
    pendingDurationMs: Long?,
    onRecordingStarted: () -> Unit,
    onRecordingTick: (Long) -> Unit,
    onRecordingStopped: (File, Long) -> Unit,
    onRecordingCancelled: () -> Unit,
    onRecordingError: (String) -> Unit,
    onDismiss: () -> Unit,
    onSend: () -> Unit,
    isUploading: Boolean,
    uploadProgress: Float,
) {
    val context = LocalContext.current
    val sheetState = rememberModalBottomSheetState()
    val controller = remember { AudioRecorderController(context) }
    val mediaPlayer = remember { MediaPlayer() }
    var isRecording by remember { mutableStateOf(false) }
    var elapsedMs by remember { mutableStateOf(0L) }
    var isPlaying by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        controller.onInterrupted = {
            isRecording = false
            onRecordingError("Gravação interrompida (ex.: chamada recebida).")
        }
        onDispose {
            controller.cancel()
            mediaPlayer.release()
        }
    }

    LaunchedEffect(isRecording) {
        while (isRecording) {
            delay(200)
            elapsedMs += 200
            onRecordingTick(elapsedMs)
        }
    }

    ModalBottomSheet(
        onDismissRequest = {
            if (isRecording) {
                controller.cancel()
                onRecordingCancelled()
            }
            onDismiss()
        },
        sheetState = sheetState,
        modifier = Modifier.testTag("audio_recorder_sheet"),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("Gravar áudio")

            when {
                pendingFile != null -> {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        IconButton(
                            onClick = {
                                if (isPlaying) {
                                    mediaPlayer.stop()
                                    isPlaying = false
                                } else {
                                    mediaPlayer.reset()
                                    mediaPlayer.setDataSource(pendingFile.absolutePath)
                                    mediaPlayer.setOnCompletionListener { isPlaying = false }
                                    mediaPlayer.prepare()
                                    mediaPlayer.start()
                                    isPlaying = true
                                }
                            },
                            modifier = Modifier.testTag("audio_playback_button")
                                .semantics { contentDescription = if (isPlaying) "Parar reprodução" else "Reproduzir áudio gravado" },
                        ) {
                            Icon(if (isPlaying) Icons.Filled.Stop else Icons.Filled.PlayArrow, contentDescription = null)
                        }
                        Text(formatRecordingDuration(pendingDurationMs ?: 0L), modifier = Modifier.testTag("audio_duration_label"))
                        IconButton(
                            onClick = {
                                if (isPlaying) {
                                    mediaPlayer.stop()
                                    isPlaying = false
                                }
                                onRecordingCancelled()
                            },
                            modifier = Modifier.testTag("audio_discard_button").semantics { contentDescription = "Descartar gravação" },
                        ) {
                            Icon(Icons.Filled.Delete, contentDescription = null)
                        }
                    }

                    if (isUploading) {
                        LinearProgressIndicator(
                            progress = { uploadProgress },
                            modifier = Modifier.fillMaxWidth().padding(top = 12.dp).testTag("audio_upload_progress"),
                        )
                    } else {
                        IconButton(
                            onClick = onSend,
                            modifier = Modifier.testTag("audio_send_button").semantics { contentDescription = "Enviar áudio" },
                        ) {
                            Icon(Icons.Filled.Send, contentDescription = null)
                        }
                    }
                }
                isRecording -> {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(formatRecordingDuration(elapsedMs), modifier = Modifier.testTag("audio_recording_duration"))
                        IconButton(
                            onClick = {
                                val stopped = controller.stop()
                                isRecording = false
                                if (stopped) {
                                    onRecordingStopped(outputFile, elapsedMs)
                                } else {
                                    onRecordingError("Não foi possível salvar a gravação.")
                                }
                            },
                            modifier = Modifier.testTag("audio_stop_button").semantics { contentDescription = "Parar gravação" },
                        ) {
                            Icon(Icons.Filled.Stop, contentDescription = null)
                        }
                    }
                }
                else -> {
                    IconButton(
                        onClick = {
                            elapsedMs = 0L
                            val started = controller.start(outputFile)
                            if (started) {
                                isRecording = true
                                onRecordingStarted()
                            } else {
                                onRecordingError("Não foi possível iniciar a gravação de áudio.")
                            }
                        },
                        modifier = Modifier.testTag("audio_record_button").semantics { contentDescription = "Iniciar gravação de áudio" },
                    ) {
                        Icon(Icons.Filled.Mic, contentDescription = null)
                    }
                }
            }
        }
    }
}
