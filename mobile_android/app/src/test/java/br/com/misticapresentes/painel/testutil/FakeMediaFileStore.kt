package br.com.misticapresentes.painel.testutil

import android.net.Uri
import br.com.misticapresentes.painel.atendimento.media.MediaFileStore
import java.io.File

/** Fake de [MediaFileStore] para testar [br.com.misticapresentes.painel.atendimento.ui.detail.ConversationViewModel] sem tocar cacheDir/ContentResolver reais. */
class FakeMediaFileStore : MediaFileStore {

    val deletedFiles = mutableListOf<File>()
    val createdFiles = mutableListOf<File>()
    var importResult: File? = null
    var importCallCount = 0
    private var counter = 0

    override fun newCameraCaptureFile(): File = newTempFile("fake_camera", ".jpg")

    override fun newAudioRecordingFile(): File = newTempFile("fake_audio", ".m4a")

    override fun newCompressedImageFile(): File = newTempFile("fake_compressed", ".jpg")

    override suspend fun importFromGallery(uri: Uri): File? {
        importCallCount++
        return importResult
    }

    override fun delete(file: File?) {
        if (file != null) deletedFiles += file
        file?.delete()
    }

    private fun newTempFile(prefix: String, suffix: String): File {
        val file = File.createTempFile("${prefix}_${counter++}", suffix)
        createdFiles += file
        return file
    }
}
