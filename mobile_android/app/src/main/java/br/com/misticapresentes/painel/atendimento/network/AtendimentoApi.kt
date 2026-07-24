package br.com.misticapresentes.painel.atendimento.network

import br.com.misticapresentes.painel.atendimento.network.dto.AgentsResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.AssignmentHistoryResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ClaimReleaseResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ConversationDetailResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.InboxConversationsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.MessagesResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ProductsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.QueueConversationsPageDto
import br.com.misticapresentes.painel.atendimento.network.dto.RecentProductsResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.ReleaseRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.ResolveRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendMessageRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendMessageResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendProductRequestDto
import br.com.misticapresentes.painel.atendimento.network.dto.SendProductResponseDto
import br.com.misticapresentes.painel.atendimento.network.dto.TransferRequestDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Superfície de API da Central de Atendimento nativa (PR #412). Todas as
 * rotas são exatamente as já existentes em `backend/whatsapp_atendimento_routes.py`,
 * `backend/whatsapp_inbox_routes.py` e `backend/whatsapp_catalog_routes.py`
 * (prefixo `/api/admin/whatsapp`) -- nenhum endpoint novo. Reaproveita o
 * mesmo client HTTP (cookie de sessão + Origin + retry + sessão expirada)
 * montado em [br.com.misticapresentes.painel.network.ApiClient], só numa
 * interface Retrofit irmã de [br.com.misticapresentes.painel.network.MisticaApi].
 */
interface AtendimentoApi {

    @GET("api/admin/whatsapp/queue")
    suspend fun queue(
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int,
    ): Response<QueueConversationsPageDto>

    @GET("api/admin/whatsapp/my-conversations")
    suspend fun myConversations(
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int,
    ): Response<QueueConversationsPageDto>

    @GET("api/admin/whatsapp/conversations")
    suspend fun conversations(
        @Query("status") status: String?,
        @Query("unread_only") unreadOnly: Boolean?,
        @Query("q") q: String?,
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int,
    ): Response<InboxConversationsPageDto>

    @GET("api/admin/whatsapp/conversations/{conversationId}")
    suspend fun getConversation(@Path("conversationId") conversationId: Long): Response<ConversationDetailResponseDto>

    @GET("api/admin/whatsapp/conversations/{conversationId}/messages")
    suspend fun getMessages(
        @Path("conversationId") conversationId: Long,
        @Query("before_id") beforeId: Long?,
        @Query("limit") limit: Int,
    ): Response<MessagesResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/messages")
    suspend fun sendMessage(
        @Path("conversationId") conversationId: Long,
        @Body body: SendMessageRequestDto,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<SendMessageResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/send-product")
    suspend fun sendProduct(
        @Path("conversationId") conversationId: Long,
        @Body body: SendProductRequestDto,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<SendProductResponseDto>

    /**
     * Envio de imagem/áudio (compose avançado de mídia, PR #413). Multipart
     * porque o backend (`rota_enviar_midia`) recebe `Form(...)` + `File(...)`,
     * não JSON -- `caption`/`assignment_version` seguem opcionais igual ao
     * endpoint de texto acima. Resposta tem a mesma forma de
     * [SendMessageResponseDto] (`ok`/`message_id`/`status`), reaproveitada
     * aqui em vez de duplicar um DTO idêntico.
     */
    @Multipart
    @POST("api/admin/whatsapp/conversations/{conversationId}/media")
    suspend fun sendMedia(
        @Path("conversationId") conversationId: Long,
        @Part("media_kind") mediaKind: RequestBody,
        @Part("caption") caption: RequestBody?,
        @Part("assignment_version") assignmentVersion: RequestBody?,
        @Part file: MultipartBody.Part,
        @Header("Idempotency-Key") idempotencyKey: String,
    ): Response<SendMessageResponseDto>

    @GET("api/admin/whatsapp/catalog/products")
    suspend fun searchProducts(
        @Query("q") q: String,
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int,
    ): Response<ProductsPageDto>

    @GET("api/admin/whatsapp/catalog/recent-products")
    suspend fun recentProducts(@Query("limit") limit: Int): Response<RecentProductsResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/claim")
    suspend fun claim(@Path("conversationId") conversationId: Long): Response<ClaimReleaseResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/release")
    suspend fun release(
        @Path("conversationId") conversationId: Long,
        @Body body: ReleaseRequestDto,
    ): Response<ClaimReleaseResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/transfer")
    suspend fun transfer(
        @Path("conversationId") conversationId: Long,
        @Body body: TransferRequestDto,
    ): Response<ClaimReleaseResponseDto>

    @POST("api/admin/whatsapp/conversations/{conversationId}/resolve")
    suspend fun resolve(
        @Path("conversationId") conversationId: Long,
        @Body body: ResolveRequestDto,
    ): Response<ClaimReleaseResponseDto>

    @GET("api/admin/whatsapp/conversations/{conversationId}/assignment-history")
    suspend fun assignmentHistory(
        @Path("conversationId") conversationId: Long,
        @Query("page") page: Int,
        @Query("page_size") pageSize: Int,
    ): Response<AssignmentHistoryResponseDto>

    @GET("api/admin/whatsapp/agents")
    suspend fun agents(): Response<AgentsResponseDto>
}
