package br.com.misticapresentes.painel.atendimento.media

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaRecorder
import android.os.Build
import java.io.File

/**
 * Wrapper fino sobre MediaRecorder (API 23..30 usa o construtor legado sem
 * argumento; 31+ exige `MediaRecorder(Context)` -- ver [Build.VERSION_CODES.S]).
 * Também disputa foco de áudio transiente exclusivo e para a gravação (sem
 * corromper o arquivo, via `stop()`/`release()` normais) se outro app tomar
 * o foco -- ex.: uma chamada telefônica chegando. Nunca faz upload nem
 * qualquer chamada de rede, só grava em [start]'s outputFile.
 */
class AudioRecorderController(private val context: Context) {

    private var recorder: MediaRecorder? = null
    private var audioManager: AudioManager? = null
    private var focusRequest: AudioFocusRequest? = null

    /** Chamado quando a gravação é interrompida por perda de foco (não por ação do usuário). */
    var onInterrupted: (() -> Unit)? = null

    val isRecording: Boolean get() = recorder != null

    /** @return true se a gravação começou com sucesso. */
    fun start(outputFile: File): Boolean {
        if (recorder != null) return false
        if (!requestAudioFocus()) return false
        return try {
            val mediaRecorder = createRecorder()
            mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC)
            mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            mediaRecorder.setAudioEncodingBitRate(64_000)
            mediaRecorder.setAudioSamplingRate(44_100)
            mediaRecorder.setOutputFile(outputFile.absolutePath)
            mediaRecorder.prepare()
            mediaRecorder.start()
            recorder = mediaRecorder
            true
        } catch (_: Exception) {
            releaseRecorderQuietly()
            abandonAudioFocus()
            false
        }
    }

    /** Para a gravação normalmente, preservando o arquivo já gravado. @return true se conseguiu parar com sucesso. */
    fun stop(): Boolean {
        val mediaRecorder = recorder ?: return false
        return try {
            mediaRecorder.stop()
            true
        } catch (_: Exception) {
            false
        } finally {
            releaseRecorderQuietly()
            abandonAudioFocus()
        }
    }

    /** Cancela a gravação sem se preocupar com o resultado -- quem chama é responsável por descartar o arquivo. */
    fun cancel() {
        try {
            recorder?.stop()
        } catch (_: Exception) {
            // Ignorado -- o arquivo será descartado por quem chamou de qualquer forma.
        }
        releaseRecorderQuietly()
        abandonAudioFocus()
    }

    private fun createRecorder(): MediaRecorder =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }

    private fun releaseRecorderQuietly() {
        try {
            recorder?.reset()
            recorder?.release()
        } catch (_: Exception) {
            // Best-effort.
        }
        recorder = null
    }

    private fun requestAudioFocus(): Boolean {
        val manager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return false
        audioManager = manager
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION_SIGNALLING)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
                .setAudioAttributes(attributes)
                .setOnAudioFocusChangeListener(::onAudioFocusChange)
                .build()
            focusRequest = request
            manager.requestAudioFocus(request) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        } else {
            @Suppress("DEPRECATION")
            manager.requestAudioFocus(
                ::onAudioFocusChange,
                AudioManager.STREAM_VOICE_CALL,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE,
            ) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        }
    }

    private fun onAudioFocusChange(focusChange: Int) {
        if (focusChange == AudioManager.AUDIOFOCUS_LOSS || focusChange == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {
            // Chamada chegando ou outro app tomou o foco -- para a gravação
            // (o que já foi gravado continua um arquivo válido) e avisa a UI.
            val wasRecording = isRecording
            stop()
            if (wasRecording) onInterrupted?.invoke()
        }
    }

    private fun abandonAudioFocus() {
        val manager = audioManager ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            focusRequest?.let { manager.abandonAudioFocusRequest(it) }
        } else {
            @Suppress("DEPRECATION")
            manager.abandonAudioFocus(::onAudioFocusChange)
        }
        focusRequest = null
        audioManager = null
    }
}
