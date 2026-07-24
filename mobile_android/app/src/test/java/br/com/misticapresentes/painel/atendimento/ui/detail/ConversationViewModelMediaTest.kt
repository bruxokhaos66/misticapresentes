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

    /**
     * Regressão do bug de rotação: `AudioRecorderSheet.onDispose` (ver
     * AudioRecorderSheet.kt) agora chama `onAudioRecordingCancelled()` sempre
     * que a composable sai de composição com uma gravação em andamento --
     * exatamente a chamada exercitada abaixo. Isso é o que acontece quando a
     * Activity é recriada por uma mudança de configuração (ex.: rotação de
     * tela): a composição antiga é descartada e sua `DisposableEffect`
     * dispara `onDispose` ANTES da nova composição montar, sobre o mesmo
     * ViewModel (que sobrevive à recriação) -- não há como simular a
     * recriação de Activity num teste JVM/Robolectric de ViewModel puro, mas
     * a invariante que a correção estabelece ("gravação em andamento + esta
     * UI sumir == cancelamento") é inteiramente testável aqui, no único
     * ponto que tinha lógica de verdade (o que `onAudioRecordingCancelled`
     * faz ao estado). A causa raiz do bug nunca esteve nesta função -- ela
     * já limpava o estado corretamente antes desta PR (ver o teste anterior);
     * o bug era o `onDispose` da UI nunca chamá-la fora do caminho de
     * dismiss explícito do usuário.
     */
    @Test
    fun `a recording torn down mid-flight (simulating a configuration change like rotation) fully resets ViewModel state`() {
        viewModel.openAudioRecorder()
        val outputFile = viewModel.uiState.value.media.audioOutputFile!!
        viewModel.onAudioRecordingStarted()
        viewModel.onAudioRecordingTick(2_500)
        assertTrue(viewModel.uiState.value.media.isRecordingAudio)

        // Simula exatamente o que o onDispose corrigido faz quando a
        // composable é destruída (rotação/recriação de Activity) com uma
        // gravação em andamento.
        viewModel.onAudioRecordingCancelled()

        // ViewModel totalmente sincronizado: nada preso em "gravando".
        assertFalse(viewModel.uiState.value.media.isRecordingAudio)
        // UI reagiria a isso automaticamente: audioOutputFile nulo faz
        // ConversationScreen parar de compor o AudioRecorderSheet (ver
        // `uiState.media.audioOutputFile?.let { AudioRecorderSheet(...) }`).
        assertNull(viewModel.uiState.value.media.audioOutputFile)
        // Nenhum áudio pendente fantasma (não existia antes da rotação, e a
        // correção nunca cria um a partir do cancelamento).
        assertNull(viewModel.uiState.value.media.pendingMedia)
        // Nenhum arquivo temporário restante.
        assertTrue(mediaFileStore.deletedFiles.contains(outputFile))

        // Nova gravação continua possível (nenhum estado preso bloqueando um
        // novo ciclo) -- gera um arquivo de saída novo e distinto do anterior.
        viewModel.openAudioRecorder()
        val newOutputFile = viewModel.uiState.value.media.audioOutputFile
        assertNotNull(newOutputFile)
        assertNotEquals(outputFile, newOutputFile)
        viewModel.onAudioRecordingStarted()
        assertTrue(viewModel.uiState.value.media.isRecordingAudio)

        // Nenhuma coroutine pendente/vazando: todo o fluxo de câmera/áudio
        // acima é síncrono sobre o StateFlow (nunca passa por
        // viewModelScope.launch) -- então advanceUntilIdle() não tem nada a
        // executar, e o estado permanece exatamente o mesmo antes e depois.
        val stateBeforeIdle = viewModel.uiState.value
        dispatcher.scheduler.advanceUntilIdle()
        assertEquals(stateBeforeIdle, viewModel.uiState.value)
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
    fun `a SocketTimeoutException during upload ends the attempt cleanly and allows a manual retry with a new idempotency key`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaThrows = java.net.SocketTimeoutException("timeout")

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        // Upload encerrado e progresso finalizado (nunca fica "travado" em andamento).
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
        assertEquals(0f, viewModel.uiState.value.media.uploadProgress, 0.001f)
        // Nenhuma mídia enviada parcialmente: nada foi confirmado como enviado, o
        // arquivo pendente é preservado para um retry manual (nunca reenviado sozinho).
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
        assertNotNull(viewModel.uiState.value.errorMessage)
        assertEquals(1, atendimentoApi.sendMediaCallCount)
        val firstKey = atendimentoApi.sendMediaIdempotencyKeys.single()

        // Retry manual explícito (usuário toca em enviar de novo) -- gera uma nova tentativa.
        atendimentoApi.sendMediaThrows = null
        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, atendimentoApi.sendMediaCallCount)
        assertNotEquals(firstKey, atendimentoApi.sendMediaIdempotencyKeys[1])
        assertNull(viewModel.uiState.value.media.pendingMedia)
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
    }

    @Test
    fun `an IOException (network failure) during upload preserves the pending file and touches nothing else`() = runTest {
        stagePendingImage(bytes = ByteArray(10))
        atendimentoApi.sendMediaThrows = java.io.IOException("network down")
        val conversationBefore = viewModel.uiState.value.conversation
        val messagesBefore = viewModel.uiState.value.messages

        viewModel.sendPendingMedia()
        dispatcher.scheduler.advanceUntilIdle()

        // Estado consistente, progresso encerrado.
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
        assertEquals(0f, viewModel.uiState.value.media.uploadProgress, 0.001f)
        // Arquivo temporário preservado para retry (nunca apagado numa falha).
        assertNotNull(viewModel.uiState.value.media.pendingMedia)
        assertNotNull(viewModel.uiState.value.errorMessage)
        // Nenhuma mensagem "enviada": a lista de mensagens não mudou (nenhum
        // refreshMessagesQuietly aconteceu, que só roda no caminho de sucesso).
        assertEquals(messagesBefore, viewModel.uiState.value.messages)
        // Nenhuma conversa alterada: IOException não é Conflict, então
        // handleActionFailure nunca recarrega a conversa a partir do backend.
        assertEquals(conversationBefore, viewModel.uiState.value.conversation)
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

    /**
     * Troca de conversa durante um upload em voo: cada conversa tem sua
     * própria instância de [ConversationViewModel] (mesmo padrão de
     * `ConversationViewModelFactory` em produção -- uma nova instância por
     * `conversationId`, compartilhando só o `AtendimentoRepository`
     * subjacente). Isso prova que a resposta atrasada do upload de A não tem
     * como "vazar" para o StateFlow de B: são objetos totalmente distintos.
     */
    @Test
    fun `a delayed upload started in one conversation never updates a different conversation's ViewModel`() = runTest {
        atendimentoApi.sendMediaDelayMs = 5_000
        val storeB = FakeMediaFileStore()
        val compressorB = FakeImageCompressor()

        // Conversa A (o `viewModel` da classe, conversationId = 1): inicia
        // upload que só vai responder bem mais tarde.
        stagePendingImage(bytes = ByteArray(10))
        viewModel.sendPendingMedia()
        dispatcher.scheduler.runCurrent()
        assertTrue(viewModel.uiState.value.media.isUploadingMedia)

        // Usuário navega para a conversa B ANTES do upload de A terminar.
        val viewModelB = ConversationViewModel(
            repository = AtendimentoRepository(atendimentoApi),
            conversationId = 2,
            mediaFileStore = storeB,
            imageCompressor = compressorB,
        )
        dispatcher.scheduler.advanceUntilIdle()
        val stateBBeforeAFinishes = viewModelB.uiState.value

        // O upload de A finalmente termina (o delay de 5s decorre).
        dispatcher.scheduler.advanceUntilIdle()

        // Nenhuma atualização chegou em B: nem progresso, nem mídia
        // pendente, nem qualquer outro campo do estado de B mudou.
        assertEquals(stateBBeforeAFinishes, viewModelB.uiState.value)
        assertFalse(viewModelB.uiState.value.media.isUploadingMedia)
        assertEquals(0f, viewModelB.uiState.value.media.uploadProgress, 0.001f)
        assertNull(viewModelB.uiState.value.media.pendingMedia)

        // O upload de A completou normalmente na própria instância -- e foi
        // para o destinatário certo (conversationId 1, nunca 2).
        assertFalse(viewModel.uiState.value.media.isUploadingMedia)
        assertNull(viewModel.uiState.value.media.pendingMedia)
        assertEquals(1, atendimentoApi.sendMediaCallCount)
        assertEquals(listOf(1L), atendimentoApi.sendMediaConversationIds)
    }

    private fun stagePendingImage(bytes: ByteArray) {
        viewModel.openCamera()
        val rawFile = viewModel.uiState.value.media.cameraOutputFile!!
        rawFile.writeBytes(bytes)
        viewModel.onPhotoCaptured(rawFile)
        dispatcher.scheduler.advanceUntilIdle()
    }
}
