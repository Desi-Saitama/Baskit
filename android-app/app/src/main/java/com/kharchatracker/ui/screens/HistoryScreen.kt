package com.kharchatracker.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.cache.OfflineCache
import com.kharchatracker.data.model.Order
import com.kharchatracker.data.model.OrderItem
import com.kharchatracker.ui.components.OrderCard
import com.kharchatracker.ui.components.ShimmerBox
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen() {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val offlineCache = remember { OfflineCache(context) }
    val scope = rememberCoroutineScope()

    var orders by remember { mutableStateOf<List<Order>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var isRefreshing by remember { mutableStateOf(false) }
    var isOffline by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedOrderId by remember { mutableStateOf<Int?>(null) }
    var selectedOrderItems by remember { mutableStateOf<List<OrderItem>>(emptyList()) }
    var selectedItemsLoading by remember { mutableStateOf(false) }
    var selectedItemsError by remember { mutableStateOf<String?>(null) }
    var showDeleteDialog by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val filteredOrders = remember(orders, searchQuery) {
        val query = searchQuery.trim()
        if (query.isBlank()) {
            orders
        } else {
            orders.filter { order ->
                order.appName.contains(query, ignoreCase = true) ||
                    order.orderDate.contains(query, ignoreCase = true) ||
                    order.orderId.orEmpty().contains(query, ignoreCase = true) ||
                    order.notes.orEmpty().contains(query, ignoreCase = true) ||
                    order.totalAmount.toString().contains(query, ignoreCase = true)
            }
        }
    }
    val groupedOrders = remember(filteredOrders) {
        filteredOrders.groupBy { monthKey(it.orderDate) }.toList()
    }

    fun loadOrders() {
        scope.launch {
            val cached = offlineCache.getOrders()
            if (cached != null) {
                orders = cached.orders
                isLoading = false
            } else {
                isLoading = true
            }

            isRefreshing = cached != null
            try {
                val service = apiClient.getService()
                val resp = service.getOrders(limit = 500)
                if (resp.isSuccessful) {
                    val freshOrders = resp.body()?.orders ?: emptyList()
                    orders = freshOrders
                    offlineCache.saveOrders(freshOrders)
                    isOffline = false
                    error = null
                } else {
                    throw Exception("Server returned ${resp.code()}")
                }
            } catch (e: Exception) {
                isOffline = true
                error = if (cached != null) {
                    "Offline mode: showing saved orders. Editing is disabled until the server is reachable."
                } else {
                    "Failed to load orders: ${e.message}"
                }
            } finally {
                isLoading = false
                isRefreshing = false
            }
        }
    }

    LaunchedEffect(Unit) { loadOrders() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "📋 Order History",
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
                modifier = Modifier.weight(1f)
            )
            IconButton(
                onClick = { loadOrders() },
                enabled = !isRefreshing
            ) {
                Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = Purple50)
            }
        }
        Spacer(modifier = Modifier.height(12.dp))

        if (isOffline || isRefreshing) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = Amber.copy(alpha = 0.15f)
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = if (isRefreshing) {
                        "Refreshing latest orders..."
                    } else {
                        error ?: "Offline mode: showing saved orders. Editing is disabled."
                    },
                    color = TextSecondary,
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
        }

        // Search bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search orders...") },
            leadingIcon = {
                Icon(Icons.Default.Search, contentDescription = "Search", tint = TextMuted)
            },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            shape = RoundedCornerShape(12.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Purple50,
                unfocusedBorderColor = DarkSurfaceVariant,
                focusedContainerColor = DarkSurface,
                unfocusedContainerColor = DarkSurface,
            )
        )

        Spacer(modifier = Modifier.height(12.dp))

        Text(
            text = "${filteredOrders.size} order(s)",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        if (isLoading) {
            repeat(5) {
                ShimmerBox(modifier = Modifier.fillMaxWidth().height(80.dp))
                Spacer(modifier = Modifier.height(8.dp))
            }
        } else if (filteredOrders.isEmpty() && error != null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.15f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        error.orEmpty(),
                        color = Red,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
        } else if (filteredOrders.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    "No orders found",
                    style = MaterialTheme.typography.bodyLarge,
                    color = TextSecondary
                )
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(bottom = 80.dp)
            ) {
                groupedOrders.forEach { (month, monthOrders) ->
                    item(key = "month-$month") {
                        MonthHeader(month = month, orders = monthOrders)
                    }

                    items(monthOrders, key = { it.id }) { order ->
                        OrderCard(
                            appName = order.appName,
                            orderDate = order.orderDate,
                            totalAmount = order.totalAmount,
                            discount = order.discount,
                            orderId = order.orderId,
                            onClick = {
                                if (selectedOrderId == order.id) {
                                    selectedOrderId = null
                                    selectedOrderItems = emptyList()
                                } else {
                                    selectedOrderId = order.id
                                    selectedItemsError = null
                                    scope.launch {
                                        val cachedItems = offlineCache.getOrderItems(order.id)
                                        if (cachedItems != null) {
                                            selectedOrderItems = cachedItems.items
                                        } else {
                                            selectedOrderItems = emptyList()
                                        }

                                        selectedItemsLoading = cachedItems == null
                                        try {
                                            val service = apiClient.getService()
                                            val resp = service.getOrder(order.id)
                                            if (resp.isSuccessful) {
                                                val freshItems = resp.body()?.items ?: emptyList()
                                                selectedOrderItems = freshItems
                                                offlineCache.saveOrderItems(order.id, freshItems)
                                                selectedItemsError = null
                                                isOffline = false
                                            } else {
                                                throw Exception("Server returned ${resp.code()}")
                                            }
                                        } catch (_: Exception) {
                                            isOffline = true
                                            selectedItemsError = if (cachedItems == null) {
                                                "Items are not saved offline for this order yet."
                                            } else {
                                                "Showing saved item details."
                                            }
                                        } finally {
                                            selectedItemsLoading = false
                                        }
                                    }
                                }
                            }
                        )

                        // Expanded detail
                        AnimatedVisibility(visible = selectedOrderId == order.id) {
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = DarkSurfaceVariant.copy(alpha = 0.5f)
                                ),
                                shape = RoundedCornerShape(8.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    if (selectedItemsLoading) {
                                        ShimmerBox(modifier = Modifier.fillMaxWidth().height(48.dp))
                                    }

                                    selectedItemsError?.let { message ->
                                        Text(
                                            text = message,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = TextSecondary,
                                            modifier = Modifier.padding(bottom = 8.dp)
                                        )
                                    }

                                    selectedOrderItems.forEach { item ->
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 4.dp),
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Column(modifier = Modifier.weight(1f)) {
                                                Text(
                                                    item.name,
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    color = TextPrimary
                                                )
                                                if (item.brand.isNotBlank()) {
                                                    Text(
                                                        item.brand,
                                                        style = MaterialTheme.typography.bodySmall,
                                                        color = TextMuted
                                                    )
                                                }
                                            }
                                            Column(horizontalAlignment = Alignment.End) {
                                                Text(
                                                    "₹${String.format("%.0f", item.totalPrice)}",
                                                    style = MaterialTheme.typography.bodyMedium,
                                                    fontWeight = FontWeight.Bold,
                                                    color = TextPrimary
                                                )
                                                Text(
                                                    item.quantity,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = TextMuted
                                                )
                                            }
                                        }
                                        if (item != selectedOrderItems.last()) {
                                            HorizontalDivider(
                                                color = DarkSurfaceVariant,
                                                modifier = Modifier.padding(vertical = 2.dp)
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(8.dp))
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.End
                                    ) {
                                        TextButton(
                                            onClick = { showDeleteDialog = order.id },
                                            enabled = !isOffline,
                                            colors = ButtonDefaults.textButtonColors(
                                                contentColor = Red
                                            )
                                        ) {
                                            Icon(Icons.Default.Delete, "Delete", Modifier.size(16.dp))
                                            Spacer(modifier = Modifier.width(4.dp))
                                            Text("Delete Order")
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete confirmation dialog
    showDeleteDialog?.let { orderId ->
        AlertDialog(
            onDismissRequest = { showDeleteDialog = null },
            title = { Text("Delete Order") },
            text = { Text("Are you sure you want to delete this order? This cannot be undone.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        scope.launch {
                            try {
                                val service = apiClient.getService()
                                val response = service.deleteOrder(orderId)
                                if (!response.isSuccessful) {
                                    throw Exception("Server returned ${response.code()}")
                                }
                                offlineCache.removeOrder(orderId)
                                isOffline = false
                                error = null
                                showDeleteDialog = null
                                selectedOrderId = null
                                loadOrders()
                            } catch (e: Exception) {
                                isOffline = true
                                error = "Delete failed while offline or unreachable: ${e.message}"
                                showDeleteDialog = null
                            }
                        }
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = Red)
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = null }) {
                    Text("Cancel")
                }
            },
            containerColor = DarkSurface
        )
    }
}

@Composable
private fun MonthHeader(month: String, orders: List<Order>) {
    val total = orders.sumOf { it.totalAmount }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp, bottom = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(
                text = monthLabel(month),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Text(
                text = "${orders.size} orders",
                style = MaterialTheme.typography.bodySmall,
                color = TextMuted
            )
        }
        Text(
            text = "₹${String.format("%,.0f", total)}",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = Purple50
        )
    }
}

private fun monthKey(orderDate: String): String {
    return try {
        YearMonth.from(LocalDate.parse(orderDate)).toString()
    } catch (_: Exception) {
        "Unknown"
    }
}

private fun monthLabel(month: String): String {
    return try {
        YearMonth.parse(month).format(DateTimeFormatter.ofPattern("MMMM yyyy", Locale.ENGLISH))
    } catch (_: Exception) {
        month
    }
}
