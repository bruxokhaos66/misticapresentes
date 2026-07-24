package br.com.misticapresentes.painel.atendimento.media

import android.content.Context
import android.net.Uri
import java.io.File
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Único ponto de escrita de arquivo temporário de mídia (foto capturada,
 * áudio gravado, imagem comprimida, cópia de item da galeria) -- sempre sob
 * `cacheDir`, NUNCA em armazenamento externo/público (nunca sobrevive além
 * do cache do app, nunca é indexado pela galeria do sistema). Quem chama é
 * sempre responsável por invocar [delete] em todo caminho terminal
 * (sucesso, cancelamento, erro) -- ver `ConversationViewModel`.
 */
interface MediaFileStore {
    fun newCameraCaptureFile(): File
    fun newAudioRecordingFile(): File
    fun newCompressedImageFile(): File

    /** Copia o conteúdo de uma Uri do Photo Picker/galeria para um arquivo próprio em cache. Retorna null em falha. */
    suspend fun importFromGallery(uri: Uri): File?

    /** Apaga um arquivo temporário desta store, sem propagar falha (best-effort). Aceita null por conveniência dos call sites. */
    fun delete(file: File?)
}

class AndroidMediaFileStore(context: Context) : MediaFileStore {

    private val appContext = context.applicationContext

    private val mediaCacheDir: File by lazy {
        File(appContext.cacheDir, "atendimento_media").apply { mkdirs() }
    }

    override fun newCameraCaptureFile(): File = File(mediaCacheDir, "camera_${UUID.randomUUID()}.jpg")

    override fun newAudioRecordingFile(): File = File(mediaCacheDir, "audio_${UUID.randomUUID()}.m4a")

    override fun newCompressedImageFile(): File = File(mediaCacheDir, "compressed_${UUID.randomUUID()}.jpg")

    override suspend fun importFromGallery(uri: Uri): File? = withContext(Dispatchers.IO) {
        val destination = File(mediaCacheDir, "gallery_${UUID.randomUUID()}.tmp")
        try {
            val copied = appContext.contentResolver.openInputStream(uri)?.use { input ->
                destination.outputStream().use { output -> input.copyTo(output) }
                true
            } ?: false
            if (copied) destination else null
        } catch (_: Exception) {
            destination.delete()
            null
        }
    }

    override fun delete(file: File?) {
        if (file == null) return
        try {
            file.delete()
        } catch (_: Exception) {
            // Best-effort -- limpeza de temp file nunca deve propagar falha.
        }
    }
}
