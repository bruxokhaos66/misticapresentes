package br.com.misticapresentes.painel.network

import java.io.IOException
import okhttp3.MediaType
import okhttp3.RequestBody
import okio.Buffer
import okio.BufferedSink
import okio.ForwardingSink
import okio.buffer

/**
 * Decorador de [RequestBody] que reporta progresso de escrita (bytes já
 * enviados) -- usado só no upload de mídia da Central de Atendimento
 * (câmera/galeria/áudio), para alimentar a barra de progresso do
 * compositor. Nunca loga path, bytes ou qualquer conteúdo, só números de
 * progresso (0..total).
 */
class ProgressRequestBody(
    private val delegate: RequestBody,
    private val onProgress: (bytesWritten: Long, totalBytes: Long) -> Unit,
) : RequestBody() {

    override fun contentType(): MediaType? = delegate.contentType()

    override fun contentLength(): Long = delegate.contentLength()

    @Throws(IOException::class)
    override fun writeTo(sink: BufferedSink) {
        val total = contentLength()
        var written = 0L
        val forwardingSink = object : ForwardingSink(sink) {
            override fun write(source: Buffer, byteCount: Long) {
                super.write(source, byteCount)
                written += byteCount
                onProgress(written, total)
            }
        }
        val bufferedSink = forwardingSink.buffer()
        delegate.writeTo(bufferedSink)
        bufferedSink.flush()
    }
}
