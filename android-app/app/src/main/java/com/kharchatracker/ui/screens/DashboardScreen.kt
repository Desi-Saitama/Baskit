package com.kharchatracker.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.model.*
import com.kharchatracker.ui.components.*
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun DashboardScreen() {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val scope = rememberCoroutineScope()

    var summary by remember { mutableStateOf<StatsSummary?>(null) }
    var appStats by remember { mutableStateOf<List<AppStat>>(emptyList()) }
    var recentOrders by remember { mutableStateOf<List<Order>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            val service = apiClient.getService()

            // Fetch all data in parallel
            val summaryResp = service.getSummary()
            val appResp = service.getStatsByApp()
            val recentResp = service.getRecentOrders(5)

            if (summaryResp.isSuccessful) summary = summaryResp.body()
            if (appResp.isSuccessful) appStats = appResp.body()?.apps ?: emptyList()
            if (recentResp.isSuccessful) recentOrders = recentResp.body()?.orders ?: emptyList()
        } catch (e: Exception) {
            error = "Failed to load dashboard: ${e.message}"
        } finally {
            isLoading = false
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "📊 Dashboard",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(16.dp))

        if (isLoading) {
            // Shimmer loading
            repeat(2) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    repeat(4) {
                        ShimmerBox(
                            modifier = Modifier
                                .weight(1f)
                                .height(100.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }
            return@Column
        }

        error?.let {
            Card(
                colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.15f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(it, color = Red, modifier = Modifier.padding(16.dp))
            }
            return@Column
        }

        summary?.let { stats ->
            if (stats.totalOrders == 0) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = DarkSurface),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text("📭", fontSize = 48.sp)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "No orders yet!",
                            style = MaterialTheme.typography.titleMedium,
                            color = TextPrimary
                        )
                        Text(
                            "Share an invoice from any app to get started",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
                return@Column
            }

            // ── KPI Cards ────────────────────────────────────────────────
            // Row 1
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                KpiCard(
                    icon = "🗓️", value = "₹${formatAmount(stats.todaySpend)}",
                    label = "Today", accentColor = Purple40,
                    modifier = Modifier.weight(1f)
                )
                KpiCard(
                    icon = "📅", value = "₹${formatAmount(stats.weekSpend)}",
                    label = "This Week", accentColor = Purple50,
                    modifier = Modifier.weight(1f)
                )
                KpiCard(
                    icon = "📆", value = "₹${formatAmount(stats.monthSpend)}",
                    label = "This Month", accentColor = Purple60,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Row 2
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                KpiCard(
                    icon = "💰", value = "₹${formatAmount(stats.totalSpend)}",
                    label = "All Time", accentColor = Amber,
                    modifier = Modifier.weight(1f)
                )
                KpiCard(
                    icon = "🏷️", value = "₹${formatAmount(stats.totalSaved)}",
                    label = "Saved", accentColor = Green,
                    modifier = Modifier.weight(1f)
                )
                KpiCard(
                    icon = "📦", value = "${stats.totalOrders}",
                    label = "Orders", accentColor = Blue,
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                KpiCard(
                    icon = "📊", value = "₹${formatAmount(stats.avgOrder)}",
                    label = "Avg Order", accentColor = Pink,
                    modifier = Modifier.weight(1f)
                )
                KpiCard(
                    icon = "🛵", value = "₹${formatAmount(stats.totalFees)}",
                    label = "Delivery Fees", accentColor = Red,
                    modifier = Modifier.weight(1f)
                )
            }
        }

        // ── App Breakdown ────────────────────────────────────────────────
        if (appStats.isNotEmpty()) {
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "📱 App Breakdown",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(12.dp))

            appStats.forEach { stat ->
                AppStatCard(
                    appName = stat.appName,
                    orders = stat.orders,
                    totalSpent = stat.totalSpent,
                    totalSaved = stat.totalSaved
                )
                Spacer(modifier = Modifier.height(8.dp))
            }
        }

        // ── Recent Orders ────────────────────────────────────────────────
        if (recentOrders.isNotEmpty()) {
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "🕐 Recent Orders",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(12.dp))

            recentOrders.forEach { order ->
                OrderCard(
                    appName = order.appName,
                    orderDate = order.orderDate,
                    totalAmount = order.totalAmount,
                    discount = order.discount,
                    orderId = order.orderId,
                    onClick = {}
                )
                Spacer(modifier = Modifier.height(8.dp))
            }
        }

        Spacer(modifier = Modifier.height(80.dp)) // Bottom nav padding
    }
}

private fun formatAmount(amount: Double): String {
    return when {
        amount >= 100000 -> "${String.format("%.1f", amount / 100000)}L"
        amount >= 1000 -> String.format("%,.0f", amount)
        else -> String.format("%.0f", amount)
    }
}
