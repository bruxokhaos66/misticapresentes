package br.com.misticapresentes.painel.atendimento.media

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import java.io.File
import java.io.FileOutputStream

private const val HEADER_BYTES_TO_READ = 12

data class CompressResult(val file: File, val originalBytes: Long, val compressedBytes: Long)

interface ImageCompressor {
    /** Lê [source], redimensiona/reencoda e escreve em [destination] (nunca sobrescreve [source]). */
    fun compress(source: File, destination: File): CompressResult
}

/**
 * Redimensiona e reencoda a imagem capturada/selecionada (JPEG) antes do
 * upload -- nunca sobrescreve o arquivo de origem, sempre escreve em
 * [destination] (um novo arquivo temporário de [MediaFileStore]). O reencode
 * em si já descarta o bloco EXIF original (orientação é lida e aplicada como
 * rotação de pixels antes de recomprimir; o JPEG de saída não carrega mais o
 * EXIF de origem, incluindo GPS se houver).
 */
class AndroidImageCompressor(
    private val maxDimensionPx: Int = 1600,
    private val jpegQuality: Int = 82,
) : ImageCompressor {

    override fun compress(source: File, destination: File): CompressResult {
        val originalBytes = source.length()
        // BitmapFactory.decodeFile pode devolver um bitmap "placeholder" não
        // nulo para bytes corrompidos em vez de `null` (comportamento
        // observado sob Robolectric, mas não exclusivo dele) -- por isso a
        // validação de formato acontece pelos magic bytes reais primeiro,
        // igual ao backend (ver identificar_imagem_saida em
        // backend/whatsapp_media_service.py), nunca só pelo retorno do decode.
        if (!isRecognizedImageHeader(readHeaderBytes(source, HEADER_BYTES_TO_READ))) {
            throw IllegalArgumentException("Arquivo não é uma imagem JPEG/PNG/WEBP válida.")
        }
        val orientation = readOrientation(source)

        val bounds = android.graphics.BitmapFactory.Options().apply { inJustDecodeBounds = true }
        android.graphics.BitmapFactory.decodeFile(source.absolutePath, bounds)
        val sampleSize = computeSampleSize(bounds.outWidth, bounds.outHeight, maxDimensionPx)

        val decodeOptions = android.graphics.BitmapFactory.Options().apply { inSampleSize = sampleSize }
        val decoded = android.graphics.BitmapFactory.decodeFile(source.absolutePath, decodeOptions)
            ?: throw IllegalArgumentException("Não foi possível decodificar a imagem.")

        val rotated = applyOrientation(decoded, orientation)
        val scaled = scaleDownIfNeeded(rotated, maxDimensionPx)

        FileOutputStream(destination).use { out ->
            scaled.compress(Bitmap.CompressFormat.JPEG, jpegQuality, out)
        }

        // Recicla todo bitmap intermediário distinto (algumas etapas podem
        // ter devolvido a mesma instância recebida, quando não havia
        // rotação/escala a aplicar -- nunca reciclar a mesma instância 2x).
        setOf(decoded, rotated, scaled).forEach { it.recycle() }

        return CompressResult(file = destination, originalBytes = originalBytes, compressedBytes = destination.length())
    }

    private fun readHeaderBytes(source: File, maxBytes: Int): ByteArray {
        val buffer = ByteArray(maxBytes)
        source.inputStream().use { stream ->
            var totalRead = 0
            while (totalRead < maxBytes) {
                val read = stream.read(buffer, totalRead, maxBytes - totalRead)
                if (read == -1) break
                totalRead += read
            }
            return buffer.copyOf(totalRead)
        }
    }

    private fun isRecognizedImageHeader(header: ByteArray): Boolean {
        val isJpeg = header.size >= 3 &&
            header[0] == 0xFF.toByte() && header[1] == 0xD8.toByte() && header[2] == 0xFF.toByte()
        val isPng = header.size >= 8 &&
            header[0] == 0x89.toByte() && header[1] == 0x50.toByte() && header[2] == 0x4E.toByte() && header[3] == 0x47.toByte() &&
            header[4] == 0x0D.toByte() && header[5] == 0x0A.toByte() && header[6] == 0x1A.toByte() && header[7] == 0x0A.toByte()
        val isWebp = header.size >= 12 &&
            header[0] == 'R'.code.toByte() && header[1] == 'I'.code.toByte() && header[2] == 'F'.code.toByte() && header[3] == 'F'.code.toByte() &&
            header[8] == 'W'.code.toByte() && header[9] == 'E'.code.toByte() && header[10] == 'B'.code.toByte() && header[11] == 'P'.code.toByte()
        return isJpeg || isPng || isWebp
    }

    private fun readOrientation(source: File): Int = try {
        ExifInterface(source.absolutePath).getAttributeInt(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL,
        )
    } catch (_: Exception) {
        ExifInterface.ORIENTATION_NORMAL
    }

    private fun computeSampleSize(width: Int, height: Int, maxDimension: Int): Int {
        if (width <= 0 || height <= 0) return 1
        var sample = 1
        var w = width
        var h = height
        while (w / 2 >= maxDimension || h / 2 >= maxDimension) {
            w /= 2
            h /= 2
            sample *= 2
        }
        return sample
    }

    private fun applyOrientation(bitmap: Bitmap, orientation: Int): Bitmap {
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            else -> return bitmap
        }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    private fun scaleDownIfNeeded(bitmap: Bitmap, maxDimension: Int): Bitmap {
        val largestSide = maxOf(bitmap.width, bitmap.height)
        if (largestSide <= maxDimension || largestSide <= 0) return bitmap
        val scale = maxDimension.toFloat() / largestSide
        val newWidth = (bitmap.width * scale).toInt().coerceAtLeast(1)
        val newHeight = (bitmap.height * scale).toInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(bitmap, newWidth, newHeight, true)
    }
}
