package br.com.misticapresentes.painel.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ApiErrorMappingTest {

    @Test
    fun `401 maps to Unauthorized with session-expired message`() {
        val error = ApiError.fromHttpCode(401)
        assertTrue(error is ApiError.Unauthorized)
        assertEquals("Sessão expirada. Faça login novamente.", error.friendlyMessage)
    }

    @Test
    fun `403 maps to Forbidden`() {
        assertTrue(ApiError.fromHttpCode(403) is ApiError.Forbidden)
    }

    @Test
    fun `404 maps to NotFound`() {
        assertTrue(ApiError.fromHttpCode(404) is ApiError.NotFound)
    }

    @Test
    fun `409 maps to Conflict`() {
        assertTrue(ApiError.fromHttpCode(409) is ApiError.Conflict)
    }

    @Test
    fun `422 maps to ValidationFailed`() {
        assertTrue(ApiError.fromHttpCode(422) is ApiError.ValidationFailed)
    }

    @Test
    fun `429 maps to TooManyRequests`() {
        assertTrue(ApiError.fromHttpCode(429) is ApiError.TooManyRequests)
    }

    @Test
    fun `5xx maps to ServerError`() {
        assertTrue(ApiError.fromHttpCode(500) is ApiError.ServerError)
        assertTrue(ApiError.fromHttpCode(503) is ApiError.ServerError)
    }

    @Test
    fun `unmapped code becomes Unknown`() {
        val error = ApiError.fromHttpCode(418)
        assertTrue(error is ApiError.Unknown)
        assertEquals(418, (error as ApiError.Unknown).code)
    }
}
