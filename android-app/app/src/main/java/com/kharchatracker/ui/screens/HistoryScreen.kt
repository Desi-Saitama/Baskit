package com.kharchatracker.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.model.Order
import com.kharchatracker.data.model.OrderItem
import com.kharchatracker.ui.components.OrderCard
import com.kharchatracker.ui.components.ShimmerBox
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen() {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val scope = rememberCoroutineScope()

    var orders by remember { mutableStateOf<List<Order>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var searchQuery by remember { mutableStateOf("") }
    var selectedOrderId by remember { mutableStateOf<Int?>(null) }
    var selectedOrderItems by remember { mutableStateOf<List<OrderItem>>(emptyList()) }
    var showDeleteDialog by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    fun loadOrders() {
        scope.launch {
            isLoading = true
            try {
                val service = apiClient.getService()
                val resp = service.getOrders(
                    limit = 200,
                    search = searchQuery.ifBlank { null }
                )
                if (resp.isSuccessful) {
                    orders = resp.body()?.orders ?: emptyList()
                }
            } catch (e: Exception) {
                error = "Failed to load orders: ${e.message}"
            } finally {
                isLoading = false
            }
        }
    }

    LaunchedEffect(Unit) { loadOrders() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text(
            text = "📋 Order History",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(12.dp))

        // Search bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = {
                searchQuery = it
                loadOrders()
            },
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
            text = "${orders.size} order(s)",
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(8.dp))

        if (isLoading) {
            repeat(5) {
                ShimmerBox(modifier = Modifier.fillMaxWidth().height(80.dp))
                Spacer(modifier = Modifier.height(8.dp))
            }
        } else if (orders.isEmpty()) {
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
                items(orders, key = { it.id }) { order ->
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
                                scope.launch {
                                    try {
                                        val service = apiClient.getService()
                                        val resp = service.getOrder(order.id)
                                        if (resp.isSuccessful) {
                                            selectedOrderItems = resp.body()?.items ?: emptyList()
                                        }
                                    } catch (_: Exception) {}
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
                                service.deleteOrder(orderId)
                                showDeleteDialog = null
                                selectedOrderId = null
                                loadOrders()
                            } catch (_: Exception) {}
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
