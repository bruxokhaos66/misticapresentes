package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.network.MisticaApi
import br.com.misticapresentes.painel.network.dto.LoginRequestDto
import br.com.misticapresentes.painel.network.dto.LoginResponseDto
import br.com.misticapresentes.painel.network.dto.LogoutResponseDto
import br.com.misticapresentes.painel.network.dto.MeResponseDto
import br.com.misticapresentes.painel.network.dto.UsuarioDto
import okhttp3.ResponseBody.Companion.toResponseBody
import retrofit2.Response

/** Fake de [MisticaApi] para testar AuthRepository/ViewModels sem rede real. */
class FakeMisticaApi : MisticaApi {

    var loginResponseCode = 200
    var loginUsuario = UsuarioDto(id = 1, nome = "Vendedora Luna", login = "luna", perfil = "vendedor")
    var meResponseCode = 200
    var meUsuario = loginUsuario
    var logoutCalls = 0
    var loginCallCount = 0

    override suspend fun login(body: LoginRequestDto): Response<LoginResponseDto> {
        loginCallCount++
        return if (loginResponseCode in 200..299) {
            Response.success(LoginResponseDto(status = "ok", usuario = loginUsuario))
        } else {
            Response.error(loginResponseCode, "erro".toResponseBody(null))
        }
    }

    override suspend fun logout(): Response<LogoutResponseDto> {
        logoutCalls++
        return Response.success(LogoutResponseDto(status = "ok", mensagem = "Sessão encerrada"))
    }

    override suspend fun me(): Response<MeResponseDto> {
        return if (meResponseCode in 200..299) {
            Response.success(MeResponseDto(status = "ok", usuario = meUsuario))
        } else {
            Response.error(meResponseCode, "erro".toResponseBody(null))
        }
    }
}
