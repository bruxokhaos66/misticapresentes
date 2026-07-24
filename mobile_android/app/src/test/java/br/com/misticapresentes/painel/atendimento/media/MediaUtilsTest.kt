package br.com.misticapresentes.painel.atendimento.media

import org.junit.Assert.assertEquals
import org.junit.Test

/** [formatRecordingDuration] é lógica pura (sem framework Android) -- teste JVM comum. */
class MediaUtilsTest {

    @Test
    fun `formats seconds under a minute`() {
        assertEquals("0:05", formatRecordingDuration(5_000))
    }

    @Test
    fun `formats minutes and seconds with zero-padded seconds`() {
        assertEquals("1:05", formatRecordingDuration(65_000))
    }

    @Test
    fun `never returns a negative duration for zero or negative input`() {
        assertEquals("0:00", formatRecordingDuration(0))
        assertEquals("0:00", formatRecordingDuration(-500))
    }

    @Test
    fun `formats several minutes correctly`() {
        assertEquals("10:00", formatRecordingDuration(600_000))
    }
}
