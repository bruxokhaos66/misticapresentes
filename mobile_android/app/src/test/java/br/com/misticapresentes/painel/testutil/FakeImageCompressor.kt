package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.atendimento.media.CompressResult
import br.com.misticapresentes.painel.atendimento.media.ImageCompressor
import java.io.File

/** Fake de [ImageCompressor] -- não decodifica Bitmap de verdade (evita depender de Robolectric nos testes de ViewModel), só copia bytes. */
class FakeImageCompressor : ImageCompressor {

    var shouldFail = false
    var callCount = 0

    override fun compress(source: File, destination: File): CompressResult {
        callCount++
        if (shouldFail) throw IllegalStateException("fake compress failure")
        val bytes = if (source.exists()) source.readBytes() else ByteArray(16)
        destination.writeBytes(bytes)
        return CompressResult(file = destination, originalBytes = source.length(), compressedBytes = destination.length())
    }
}
