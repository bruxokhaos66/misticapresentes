package br.com.misticapresentes.painel.atendimento.media

import android.graphics.Bitmap
import java.io.File
import java.io.FileOutputStream
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * [AndroidImageCompressor] usa `android.graphics.Bitmap`/`BitmapFactory`,
 * por isso roda sob Robolectric (mesmo padrão de `FeatureFlagsTest`) em vez
 * de um teste JVM puro -- é a única forma de exercitar o path real de
 * decode/rotate/scale/compress sem um dispositivo/emulador.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ImageCompressorTest {

    private lateinit var source: File
    private lateinit var destination: File

    @Before
    fun setUp() {
        source = File.createTempFile("image_compressor_source", ".jpg")
        destination = File.createTempFile("image_compressor_dest", ".jpg")
        val bitmap = Bitmap.createBitmap(600, 400, Bitmap.Config.ARGB_8888)
        FileOutputStream(source).use { out -> bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out) }
    }

    @After
    fun tearDown() {
        source.delete()
        destination.delete()
    }

    @Test
    fun `compress writes a valid JPEG to destination without touching the source file`() {
        val sourceBytesBefore = source.readBytes()
        val compressor = AndroidImageCompressor(maxDimensionPx = 300, jpegQuality = 70)

        val result = compressor.compress(source, destination)

        assertTrue(destination.exists())
        assertTrue(destination.length() > 0)
        val destinationBytes = destination.readBytes()
        // Magic bytes de JPEG (0xFFD8) -- garante que o reencode produziu um arquivo válido.
        assertTrue(destinationBytes[0] == 0xFF.toByte() && destinationBytes[1] == 0xD8.toByte())
        assertTrue(result.compressedBytes == destination.length())
        assertTrue(result.originalBytes == sourceBytesBefore.size.toLong())
        // Nunca sobrescreve/muta o arquivo de origem.
        assertTrue(source.readBytes().contentEquals(sourceBytesBefore))
    }

    @Test
    fun `compress with an unreadable source throws instead of silently producing an empty file`() {
        val brokenSource = File.createTempFile("image_compressor_broken", ".jpg").apply { writeBytes(ByteArray(4)) }
        val compressor = AndroidImageCompressor()

        try {
            compressor.compress(brokenSource, destination)
            throw AssertionError("esperava exceção para arquivo que não é uma imagem válida")
        } catch (expected: IllegalArgumentException) {
            // Esperado.
        } finally {
            brokenSource.delete()
        }
    }
}
