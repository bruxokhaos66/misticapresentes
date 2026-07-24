package br.com.misticapresentes.painel.atendimento.ui.detail

import android.net.Uri
import br.com.misticapresentes.painel.atendimento.repository.AtendimentoRepository
import br.com.misticapresentes.painel.testutil.FakeAtendimentoApi
import br.com.misticapresentes.painel.testutil.FakeImageCompressor
import br.com.misticapresentes.painel.testutil.FakeMediaFileStore
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Testes de suporte de mídia (PR #413) do [ConversationViewModel]: fluxo de
 * permissão, ciclo de vida de câmera/galeria/áudio, upload (progresso,
 * cancelamento, timeout/rede, retry) -- usa Robolectric só porque alguns
 * cenários constroem `Uri.parse(...)` (galeria); a lógica em si não depende
 * de Android real, sempre passando por [FakeMediaFileStore]/[FakeImageCompressor].
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ConversationViewModelMediaTest {

    private val dispatcher = StandardTestDispatcher()
    private lateinit var atendimentoApi: FakeAtendimentoApi
    private lateinit var mediaFileStore: FakeMediaFileStore
    private lateinit var imageCompressor: FakeImageCompressor
    private lateinit var viewModel: ConversationViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
        atendimentoApi = FakeAtendimentoApi()
        mediaFileStore = FakeMediaFileStore()
        imageCompressor = FakeImageCompressor()
        viewModel = ConversationViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            conversationId = 1,
            mediaFileStore = mediaFileStore,
            imageCompressor = imageCompressor,
        )
        dispatcher.scheduler.advanceUntilIdle()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    // -------- Permissões --------

    @Test
    fun `camera permission denied with rationale shows rationale dialog, not the settings one`() {
        viewModel.onMediaPermissionDenied(MediaPermissionType.CAMERA, permanentlyDenied = false)

        assertEquals(MediaPermissionType.CAMERA, viewModel.uiState.value.media.permissionRationale)
        assertNull(viewModel.uiState.value.media.permissionPermanentlyDenied)
    }

    @Test
    fun `microphone permission permanently denied shows settings dialog, not the rationale one`() {
        viewModel.onMediaPermissionDenied(MediaPermissionType.MICROPHONE, permanentlyDenied = true)

        assertEquals(MediaPermissionType.MICROPHONE, viewModel.uiState.value.media.permissionPermanentlyDenied)
        assertNull(viewModel.uiState.value.media.permissionRationale)
    }

    @Test
    fun `dismissMediaPermissionDialog clears both permission dialogs`() {
        viewModel.onMediaPermissionDenied(MediaPermissionType.CAMERA, permanentlyDenied = true)

        viewModel.dismissMediaPermissionDialog()

        assertNull(viewModel.uiState.value.media.permissionRationale)
        assertNull(viewModel.uiState.value.media.permissionPermanentlyDenied)
    }

    // -------- Câmera --------

    @Test
    fun `openCamera creates an output file and closeCamera deletes it`() {
        viewModel.openCamera()
        val file = viewModel.uiState.value.media.cameraOutputFile
        assertNotNull(file)

        viewModel.closeCamera()

        assertNull(viewModel.uiState.value.media.cameraOutputFile)
        assertTrue(mediaFileStore.deletedFiles.contains(file))
    }

    @Test
    fun `onPhotoCaptured compresses the raw file, deletes it and stages pending image media`() = runTest {
        viewModel.openCamera()
        val rawFile = viewModel.uiState.value.media.cameraOutputFile!!
        rawFile.writeBytes(byteArrayOf(1, 2, 3))

        viewModel.onPhotoCaptured(rawFile)
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, imageCompressor.callCount)
        assertTrue(mediaFileStore.deletedFiles.contains(rawFile))
        assertNull(viewModel.uiState.value.media.cameraOutputFile)
        val pending = viewModel.uiState.value.media.pendingMedia
        assertNotNull(pending)
        assertEquals(br.com.misticapresentes.painel.atendimento.model.MediaKind.IMAGE, pending!!.kind)
    }

    @Test
    fun `a compression failure surfaces an error and cleans up the raw file`() = runTest {
        viewModel.openCamera()
        val rawFile = viewModel.uiState.value.media.cameraOutputFile!!
        imageCompressor.shouldFail = true

        viewModel.onPhotoCaptured(rawFile)
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.errorMessage)
        assertTrue(mediaFileStore.deletedFiles.contains(rawFile))
        assertNull(viewModel.uiState.value.media.pendingMedia)
    }

    // -------- Galeria --------

    @Test
    fun `onGalleryImageSelected imports, compresses and stages a pending image`() = runTest {
        val imported = File.createTempFile("gallery_import", ".tmp").apply { writeBytes(byteArrayOf(9)) }
        mediaFileStore.importResult = imported

        viewModel.onGalleryImageSelected(Uri.parse("content://media/external/images/1"))
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, mediaFileStore.importCallCount)
        assertEquals(1, imageCompressor.callCount)
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
        assertTrue(mediaFileStore.deletedFiles.contains(imported))
    }

    @Test
    fun `a gallery import failure surfaces a friendly error message`() = runTest {
        mediaFileStore.importResult = null

        viewModel.onGalleryImageSelected(Uri.parse("content://media/external/images/2"))
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.errorMessage)
        assertNull(viewModel.uiState.value.media.pendingMedia)
    }

    // -------- Áudio --------

    @Test
    fun `audio recording lifecycle updates state through start, tick and stop`() {
        viewModel.openAudioRecorder()
        val outputFile = viewModel.uiState.value.media.audioOutputFile!!

        viewModel.onAudioRecordingStarted()
        assertTrue(viewModel.uiState.value.media.isRecordingAudio)

        viewModel.onAudioRecordingTick(1_500)
        assertEquals(1_500L, viewModel.uiState.value.media.recordingElapsedMs)

        viewModel.onAudioRecordingStopped(outputFile, 4_200)
        assertFalse(viewModel.uiState.value.media.isRecordingAudio)
        val pending = viewModel.uiState.value.media.pendingMedia
        assertNotNull(pending)
        assertEquals(4_200L, pending!!.durationMs)
    }

    @Test
    fun `cancelling an in-progress recording deletes the file and clears state`() {
        viewModel.openAudioRecorder()
        val outputFile = viewModel.uiState.value.media.audioOutputFile!!
        viewModel.onAudioRecordingStarted()

        viewModel.onAudioRecordingCancelled()

        assertFalse(viewModel.uiState.value.media.isRecordingAudio)
        assertNull(viewModel.uiState.value.media.pendingMedia)
        assertTrue(mediaFileStore.deletedFiles.contains(outputFile))
    }

    @Test
    fun `closing the audio sheet while a clip is pending discards it`() {
        viewModel.openAudioRecorder()
        val outputFile = viewModel.uiState.value.media.audioOutputFile!!
        viewModel.onAudioRecordingStopped(outputFile, 1_000)

        viewModel.closeAudioRecorder()

        assertNull(viewModel.uiState.value.media.audioOutputFile)
        assertNull(viewModel.uiState.value.media.pendingMedia)
    }

    // -------- Upload --------

    @Test
    fun `sendPendingMedia succeeds, deletes the file, clears pending state and refreshes messages`() = runTest {
        stagePendingImage(bytes = ByteArray(10))

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, atendimentoApi.sendMediaCallCount)
        assertNull(viewModel.uiState.value.media.pendingMedia)
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
    }

    @Test
    fun `sendPendingMedia reports progress while uploading`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaDelayMs = 100

        viewModel.sendPendingMedia()
        dispatcher.scheduler.runCurrent()

        assertTrue(viewModel.uiState.value.media.isUploadingMedia)
        dispatcher.scheduler.advanceUntilIdle()
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
    }

    @Test
    fun `a soft failure (ok=false) keeps the pending media for a manual retry`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaOk = false

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.errorMessage)
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
    }

    @Test
    fun `retrying after a failure uses a new idempotency key`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaOk = false

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(1, atendimentoApi.sendMediaIdempotencyKeys.size)

        atendimentoApi.sendMediaOk = true
        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, atendimentoApi.sendMediaIdempotencyKeys.size)
        val (first, second) = atendimentoApi.sendMediaIdempotencyKeys
        assertNotEquals(first, second)
    }

    @Test
    fun `409 while uploading reloads the conversation instead of a generic error`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.responseCode = 409

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertNotNull(viewModel.uiState.value.infoMessage)
    }

    @Test
    fun `cancelMediaUpload cancels the in-flight call but keeps the pending media for retry`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaDelayMs = 10_000

        viewModel.sendPendingMedia()
        dispatcher.scheduler.runCurrent()
        assertTrue(viewModel.uiState.value.media.isUploadingMedia)

        viewModel.cancelMediaUpload()

        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
    }

    @Test
    fun `cancelPendingMedia deletes the temp file and clears the pending state`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        val file = viewModel.uiState.value.media.pendingMedia!!.file

        viewModel.cancelPendingMedia()

        assertNull(viewModel.uiState.value.media.pendingMedia)
        assertTrue(mediaFileStore.deletedFiles.contains(file))
    }

    @Test
    fun `a file over the size limit is rejected client-side without calling the API`() = runTest {
        stagePendingImage(bytes = ByteArray((br.com.misticapresentes.painel.atendimento.media.MediaLimits.MAX_IMAGE_BYTES + 1).toInt()))

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(0, atendimentoApi.sendMediaCallCount)
        assertNotNull(viewModel.uiState.value.errorMessage)
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
    }

    @Test
    fun `a second concurrent call to sendPendingMedia while already uploading is ignored`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaDelayMs = 1_000

        viewModel.sendPendingMedia()
        dispatcher.scheduler.runCurrent()
        viewModel.sendPendingMedia() // segunda chamada enquanto a primeira está em voo
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, atendimentoApi.sendMediaCallCount)
    }

    private fun stagePendingImage(bytes: ByteArray) {
        viewModel.openCamera()
        val rawFile = viewModel.uiState.value.media.cameraOutputFile!!
        rawFile.writeBytes(bytes)
        viewModel.onPhotoCaptured(rawFile)
        dispatcher.scheduler.advanceUntilIdle()
    }
}
