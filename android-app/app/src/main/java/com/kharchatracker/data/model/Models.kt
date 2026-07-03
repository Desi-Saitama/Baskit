package com.kharchatracker.data.model

import com.google.gson.annotations.SerializedName

// ── Auth ─────────────────────────────────────────────────────────────────────

data class LoginRequest(
    val username: String = "admin",
    val password: String
)

data class TokenResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type") val tokenType: String = "bearer"
)

// ── Orders ───────────────────────────────────────────────────────────────────

data class Order(
    val id: Int,
    @SerializedName("order_date") val orderDate: String,
    @SerializedName("app_name") val appName: String,
    @SerializedName("app_category") val appCategory: String,
    @SerializedName("order_id") val orderId: String?,
    @SerializedName("total_amount") val totalAmount: Double,
    @SerializedName("delivery_fee") val deliveryFee: Double,
    val discount: Double,
    val notes: String?,
    @SerializedName("created_at") val createdAt: String? = null
)

data class OrderItem(
    val id: Int? = null,
    val name: String,
    val brand: String = "",
    val category: String = "Other",
    val quantity: String = "",
    @SerializedName("unit_price") val unitPrice: Double = 0.0,
    @SerializedName("total_price") val totalPrice: Double = 0.0
)

data class OrdersResponse(
    val orders: List<Order>,
    val total: Int,
    val skip: Int,
    val limit: Int
)

data class OrderDetailResponse(
    val order: Order,
    val items: List<OrderItem>
)

data class OrderCreateRequest(
    @SerializedName("order_date") val orderDate: String,
    @SerializedName("app_name") val appName: String,
    @SerializedName("app_category") val appCategory: String = "",
    @SerializedName("order_id") val orderId: String = "",
    @SerializedName("total_amount") val totalAmount: Double = 0.0,
    @SerializedName("delivery_fee") val deliveryFee: Double = 0.0,
    val discount: Double = 0.0,
    val notes: String = "",
    val items: List<OrderItemRequest> = emptyList()
)

data class OrderItemRequest(
    val name: String,
    val brand: String = "",
    val category: String = "Other",
    val quantity: String = "",
    @SerializedName("unit_price") val unitPrice: Double = 0.0,
    @SerializedName("total_price") val totalPrice: Double = 0.0
)

data class OrderSaveRequest(
    @SerializedName("order_date") val orderDate: String,
    @SerializedName("app_name") val appName: String,
    @SerializedName("app_category") val appCategory: String = "",
    @SerializedName("order_id") val orderId: String = "",
    @SerializedName("total_amount") val totalAmount: Double = 0.0,
    @SerializedName("delivery_fee") val deliveryFee: Double = 0.0,
    val discount: Double = 0.0,
    val notes: String = "",
    val items: List<OrderItemRequest> = emptyList(),
    @SerializedName("skip_duplicate_check") val skipDuplicateCheck: Boolean = false
)

data class CreateResponse(
    val id: Int,
    val message: String
)

data class MessageResponse(
    val message: String
)

// ── Stats ────────────────────────────────────────────────────────────────────

data class StatsSummary(
    @SerializedName("today_spend") val todaySpend: Double,
    @SerializedName("week_spend") val weekSpend: Double,
    @SerializedName("month_spend") val monthSpend: Double,
    @SerializedName("total_spend") val totalSpend: Double,
    @SerializedName("total_saved") val totalSaved: Double,
    @SerializedName("total_fees") val totalFees: Double,
    @SerializedName("total_orders") val totalOrders: Int,
    @SerializedName("avg_order") val avgOrder: Double
)

data class AppStat(
    @SerializedName("app_name") val appName: String,
    val orders: Int,
    @SerializedName("total_spent") val totalSpent: Double,
    @SerializedName("total_saved") val totalSaved: Double,
    @SerializedName("total_fees") val totalFees: Double,
    @SerializedName("avg_order") val avgOrder: Double
)

data class AppStatsResponse(
    val apps: List<AppStat>
)

data class CategoryStat(
    val category: String,
    @SerializedName("item_count") val itemCount: Int,
    @SerializedName("total_spent") val totalSpent: Double,
    @SerializedName("avg_price") val avgPrice: Double
)

data class CategoryStatsResponse(
    val categories: List<CategoryStat>
)

// ── Parse ────────────────────────────────────────────────────────────────────

data class ParsedItem(
    val name: String = "",
    val brand: String = "",
    val category: String = "Other",
    val quantity: String = "",
    @SerializedName("unit_price") val unitPrice: Double = 0.0,
    @SerializedName("total_price") val totalPrice: Double = 0.0
)

data class ParsedOrder(
    @SerializedName("detected_app") val detectedApp: String? = null,
    @SerializedName("resolved_app") val resolvedApp: String? = null,
    @SerializedName("resolved_category") val resolvedCategory: String? = null,
    @SerializedName("order_date") val orderDate: String? = null,
    @SerializedName("order_id") val orderId: String? = null,
    @SerializedName("total_amount") val totalAmount: Double = 0.0,
    @SerializedName("delivery_fee") val deliveryFee: Double = 0.0,
    val discount: Double = 0.0,
    val items: List<ParsedItem> = emptyList()
)

data class ParseResponse(
    val parsed: ParsedOrder
)

// ── Health ────────────────────────────────────────────────────────────────────

data class HealthResponse(
    val status: String,
    val app: String,
    val version: String
)
