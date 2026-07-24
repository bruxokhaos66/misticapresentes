package br.com.misticapresentes.painel.atendimento.ui.detail

import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Cameraswitch
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material.icons.filled.Lens
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import java.io.File

/**
 * Tela de captura de foto em CameraX (preview ao vivo + captura, flash,
 * troca frontal/traseira), exibida full-screen por cima de
 * [ConversationScreen] -- herda o FLAG_SECURE já aplicado por
 * `ScreenSecurity.enable` naquela tela (não reaplica/remove aqui). Nunca
 * grava nada fora de [outputFile] (sempre em cacheDir, ver `MediaFileStore`);
 * quem chama decide o destino do arquivo (comprimir, descartar em
 * erro/cancelamento) -- esta Composable não tem conhecimento de rede.
 *
 * Nota de cobertura: lógica de binding do CameraX (Preview/ImageCapture,
 * ciclo de vida da câmera) depende de um dispositivo/emulador real com
 * câmera e não é coberta por teste automatizado nesta PR -- documentado como
 * limitação conhecida.
 */
@Composable
fun CameraCaptureScreen(
    outputFile: File,
    onCaptured: (File) -> Unit,
    onCancel: () -> Unit,
    onError: (String) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember { PreviewView(context) }

    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var lensFacing by remember { mutableStateOf(CameraSelector.LENS_FACING_BACK) }
    var flashEnabled by remember { mutableStateOf(false) }
    var isCapturing by remember { mutableStateOf(false) }
    var hasFrontCamera by remember { mutableStateOf(false) }
    var cameraProvider by remember { mutableStateOf<ProcessCameraProvider?>(null) }

    DisposableEffect(Unit) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        providerFuture.addListener(
            {
                try {
                    cameraProvider = providerFuture.get()
                } catch (exc: Exception) {
                    onError("Não foi possível iniciar a câmera.")
                }
            },
            ContextCompat.getMainExecutor(context),
        )
        onDispose { cameraProvider?.unbindAll() }
    }

    LaunchedEffect(cameraProvider, lensFacing, flashEnabled) {
        val provider = cameraProvider ?: return@LaunchedEffect
        try {
            val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
            val capture = ImageCapture.Builder()
                .setFlashMode(if (flashEnabled) ImageCapture.FLASH_MODE_ON else ImageCapture.FLASH_MODE_OFF)
                .build()
            val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
            provider.unbindAll()
            provider.bindToLifecycle(lifecycleOwner, selector, preview, capture)
            imageCapture = capture
            hasFrontCamera = try {
                provider.hasCamera(CameraSelector.DEFAULT_FRONT_CAMERA)
            } catch (exc: Exception) {
                false
            }
        } catch (exc: Exception) {
            onError("Não foi possível abrir a câmera.")
        }
    }

    Box(modifier = Modifier.fillMaxSize().testTag("camera_capture_screen")) {
        AndroidView(modifier = Modifier.fillMaxSize(), factory = { previewView })

        Row(
            modifier = Modifier.fillMaxWidth().align(Alignment.TopStart).padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            IconButton(
                onClick = onCancel,
                modifier = Modifier.testTag("camera_close_button").semantics { contentDescription = "Fechar câmera" },
            ) {
                Icon(Icons.Filled.Close, contentDescription = null)
            }
            Row {
                IconButton(
                    onClick = { flashEnabled = !flashEnabled },
                    modifier = Modifier.testTag("camera_flash_toggle").semantics { contentDescription = "Alternar flash" },
                ) {
                    Icon(if (flashEnabled) Icons.Filled.FlashOn else Icons.Filled.FlashOff, contentDescription = null)
                }
                if (hasFrontCamera) {
                    IconButton(
                        onClick = {
                            lensFacing = if (lensFacing == CameraSelector.LENS_FACING_BACK) {
                                CameraSelector.LENS_FACING_FRONT
                            } else {
                                CameraSelector.LENS_FACING_BACK
                            }
                        },
                        modifier = Modifier.testTag("camera_switch_button")
                            .semantics { contentDescription = "Alternar câmera frontal/traseira" },
                    ) {
                        Icon(Icons.Filled.Cameraswitch, contentDescription = null)
                    }
                }
            }
        }

        Box(modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(24.dp)) {
            if (isCapturing) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center))
            } else {
                IconButton(
                    onClick = {
                        val capture = imageCapture ?: return@IconButton
                        isCapturing = true
                        val outputOptions = ImageCapture.OutputFileOptions.Builder(outputFile).build()
                        capture.takePicture(
                            outputOptions,
                            ContextCompat.getMainExecutor(context),
                            object : ImageCapture.OnImageSavedCallback {
                                override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                                    isCapturing = false
                                    onCaptured(outputFile)
                                }

                                override fun onError(exception: ImageCaptureException) {
                                    isCapturing = false
                                    onError("Falha ao capturar a foto. Tente novamente.")
                                }
                            },
                        )
                    },
                    modifier = Modifier.align(Alignment.Center)
                        .testTag("camera_shutter_button")
                        .semantics { contentDescription = "Capturar foto" },
                ) {
                    Icon(Icons.Filled.Lens, contentDescription = null, modifier = Modifier.size(72.dp))
                }
            }
        }
    }
}
