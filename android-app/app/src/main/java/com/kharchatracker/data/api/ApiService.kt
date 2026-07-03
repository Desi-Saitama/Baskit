package com.kharchatracker.data.api

import com.kharchatracker.data.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

/**
 * Retrofit interface matching the FastAPI server endpoints.
 */
interface ApiService {

    // ── Auth ─────────────────────────────────────────────────────────────────

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<TokenResponse>

    // ── Orders ───────────────────────────────────────────────────────────────

    @GET("api/orders")
    suspend fun getOrders(
        @Query("skip") skip: Int = 0,
        @Query("limit") limit: Int = 50,
        @Query("app_name") appName: String? = null,
        @Query("search") search: String? = null,
    ): Response<OrdersResponse>

    @GET("api/orders/{id}")
    suspend fun getOrder(@Path("id") id: Int): Response<OrderDetailResponse>

    @POST("api/orders")
    suspend fun createOrder(@Body order: OrderCreateRequest): Response<CreateResponse>

    @PUT("api/orders/{id}")
    suspend fun updateOrder(
        @Path("id") id: Int,
        @Body order: OrderCreateRequest
    ): Response<MessageResponse>

    @DELETE("api/orders/{id}")
    suspend fun deleteOrder(@Path("id") id: Int): Response<MessageResponse>

    // ── Upload / Parse ───────────────────────────────────────────────────────

    @Multipart
    @POST("api/upload/parse")
    suspend fun parseFile(
        @Part file: MultipartBody.Part,
        @Part("app_name") appName: RequestBody? = null,
    ): Response<ParseResponse>

    @POST("api/upload/save")
    suspend fun saveParsedOrder(@Body order: OrderSaveRequest): Response<CreateResponse>

    // ── Stats ────────────────────────────────────────────────────────────────

    @GET("api/stats/summary")
    suspend fun getSummary(): Response<StatsSummary>

    @GET("api/stats/by-app")
    suspend fun getStatsByApp(): Response<AppStatsResponse>

    @GET("api/stats/by-category")
    suspend fun getStatsByCategory(): Response<CategoryStatsResponse>

    @GET("api/stats/recent-orders")
    suspend fun getRecentOrders(@Query("limit") limit: Int = 5): Response<OrdersResponse>

    // ── Health ────────────────────────────────────────────────────────────────

    @GET("api/health")
    suspend fun healthCheck(): Response<HealthResponse>
}
