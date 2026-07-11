package com.kharchatracker.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.cache.OfflineCache
import com.kharchatracker.data.model.*
import com.kharchatracker.ui.components.*
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import retrofit2.Response

@Composable
fun DashboardScreen() {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val offlineCache = remember { OfflineCache(context) }

    var summary by remember { mutableStateOf<StatsSummary?>(null) }
    var appStats by remember { mutableStateOf<List<AppStat>>(emptyList()) }
    var recentOrders by remember { mutableStateOf<List<Order>>(emptyList()) }
    var monthlyStats by remember { mutableStateOf<MonthlyStatsResponse?>(null) }
    var selectedMonth by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(true) }
    var isRefreshing by remember { mutableStateOf(false) }
    var showingCachedData by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        val cached = offlineCache.getDashboard()
        if (cached != null) {
            summary = cached.summary
            appStats = cached.appStats
            recentOrders = cached.recentOrders
            monthlyStats = cached.monthlyStats
            selectedMonth = cached.monthlyStats?.months?.maxByOrNull { it.month }?.month
            showingCachedData = true
            isLoading = false
        }

        isRefreshing = cached != null
        try {
            val service = apiClient.getService()

            val (summaryResp, appResp, recentResp, monthlyResp) = coroutineScope {
                val summaryDeferred = async { service.getSummary() }
                val appDeferred = async { service.getStatsByApp() }
                val recentDeferred = async { service.getRecentOrders(5) }
                val monthlyDeferred = async { service.getMonthlyStats(months = 24, populatedOnly = true) }
                DashboardResponses(
                    summaryDeferred.await(),
                    appDeferred.await(),
                    recentDeferred.await(),
                    monthlyDeferred.await()
                )
            }

            if (!summaryResp.isSuccessful || !appResp.isSuccessful || !recentResp.isSuccessful || !monthlyResp.isSuccessful) {
                throw Exception("Server returned ${summaryResp.code()}/${appResp.code()}/${recentResp.code()}/${monthlyResp.code()}")
            }

            summary = summaryResp.body()
            appStats = appResp.body()?.apps ?: emptyList()
            recentOrders = recentResp.body()?.orders ?: emptyList()
            monthlyStats = monthlyResp.body()
            selectedMonth = monthlyStats?.months?.maxByOrNull { it.month }?.month
            offlineCache.saveDashboard(summary, appStats, recentOrders, monthlyStats)
            showingCachedData = false
            error = null
            runCatching {
                val ordersResp = service.getOrders(limit = 500)
                if (ordersResp.isSuccessful) {
                    offlineCache.saveOrders(ordersResp.body()?.orders ?: emptyList())
                }
            }
        } catch (e: Exception) {
            error = if (cached != null) {
                "Offline mode: showing saved dashboard data."
            } else {
                "Failed to load dashboard: ${e.message}"
            }
        } finally {
            isLoading = false
            isRefreshing = false
        }
    }

    LaunchedEffect(selectedMonth) {
        val month = selectedMonth ?: return@LaunchedEffect
        runCatching {
            apiClient.getService().getStatsByApp(month)
        }.onSuccess { response ->
            if (response.isSuccessful) {
                appStats = response.body()?.apps ?: emptyList()
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "Dashboard",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(16.dp))

        monthlyStats?.months?.takeIf { it.isNotEmpty() }?.let { months ->
            MonthPicker(
                months = months,
                selectedMonth = selectedMonth,
                onSelected = { selectedMonth = it }
            )
            Spacer(modifier = Modifier.height(16.dp))
        }

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

        if (showingCachedData || isRefreshing) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = Amber.copy(alpha = 0.15f)
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = if (isRefreshing) "Refreshing latest data..." else "Offline mode: showing saved data.",
                    color = TextSecondary,
                    modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
        }

        error?.let {
            if (summary == null && appStats.isEmpty() && recentOrders.isEmpty()) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.15f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(it, color = Red, modifier = Modifier.padding(16.dp))
                }
                return@Column
            }
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

        monthlyStats?.let { monthly ->
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "Monthly expenses",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(12.dp))

            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        MonthCompareItem(
                            title = "This Month",
                            amount = monthly.currentMonth.totalSpend,
                            orders = monthly.currentMonth.totalOrders,
                            modifier = Modifier.weight(1f)
                        )
                        MonthCompareItem(
                            title = "Last Month",
                            amount = monthly.previousMonth.totalSpend,
                            orders = monthly.previousMonth.totalOrders,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    val deltaColor = if (monthly.comparison.spendDelta <= 0) Green else Orange
                    Card(
                        colors = CardDefaults.cardColors(containerColor = deltaColor.copy(alpha = 0.12f)),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(
                                text = "Compared with last month",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "${formatSignedAmount(monthly.comparison.spendDelta)} ${formatPercent(monthly.comparison.spendDeltaPercent)}",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = deltaColor
                            )
                            Text(
                                text = "${formatSignedCount(monthly.comparison.ordersDelta)} orders, avg order ${formatSignedAmount(monthly.comparison.avgOrderDelta)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = TextSecondary
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            val maxSpend = monthly.months.maxOfOrNull { it.totalSpend }?.takeIf { it > 0 } ?: 1.0
            monthly.months.asReversed().forEach { month ->
                MonthExpenseRow(month = month, maxSpend = maxSpend)
                Spacer(modifier = Modifier.height(8.dp))
            }
        }

        // ── App Breakdown ────────────────────────────────────────────────
        if (appStats.isNotEmpty()) {
            Spacer(modifier = Modifier.height(24.dp))
            Text(
                text = "App breakdown${selectedMonth?.let { selected -> " · ${monthlyStats?.months?.find { row -> row.month == selected }?.label.orEmpty()}" }.orEmpty()}",
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

private data class DashboardResponses(
    val summary: Response<StatsSummary>,
    val apps: Response<AppStatsResponse>,
    val recent: Response<OrdersResponse>,
    val monthly: Response<MonthlyStatsResponse>
)

@Composable
private fun MonthPicker(
    months: List<MonthlyStat>,
    selectedMonth: String?,
    onSelected: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val current = months.find { it.month == selectedMonth } ?: months.maxByOrNull { it.month }

    Box {
        OutlinedButton(
            onClick = { expanded = true },
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = Purple50)
        ) {
            Text("Month · ${current?.label ?: "Choose"}")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            months.sortedByDescending { it.month }.forEach { month ->
                DropdownMenuItem(
                    text = { Text(month.label) },
                    onClick = {
                        onSelected(month.month)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
private fun MonthCompareItem(
    title: String,
    amount: Double,
    orders: Int,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = title,
            style = MaterialTheme.typography.bodySmall,
            color = TextSecondary
        )
        Text(
            text = "₹${formatAmount(amount)}",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Text(
            text = "$orders orders",
            style = MaterialTheme.typography.bodySmall,
            color = TextMuted
        )
    }
}

@Composable
private fun MonthExpenseRow(month: MonthlyStat, maxSpend: Double) {
    val progress = (month.totalSpend / maxSpend).coerceIn(0.0, 1.0).toFloat()
    Card(
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        shape = RoundedCornerShape(10.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = month.label,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                    Text(
                        text = "${month.totalOrders} orders · saved ₹${formatAmount(month.totalSaved)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted
                    )
                }
                Text(
                    text = "₹${formatAmount(month.totalSpend)}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Purple50
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(DarkSurfaceVariant.copy(alpha = 0.6f))
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(progress)
                        .fillMaxHeight()
                        .background(Purple50)
                )
            }
        }
    }
}

private fun formatAmount(amount: Double): String {
    return when {
        amount >= 100000 -> "${String.format("%.1f", amount / 100000)}L"
        amount >= 1000 -> String.format("%,.0f", amount)
        else -> String.format("%.0f", amount)
    }
}

private fun formatSignedAmount(amount: Double): String {
    val sign = if (amount >= 0) "+" else "-"
    return "$sign₹${formatAmount(kotlin.math.abs(amount))}"
}

private fun formatSignedCount(value: Int): String {
    return if (value >= 0) "+$value" else value.toString()
}

private fun formatPercent(percent: Double?): String {
    return percent?.let { "(${if (it >= 0) "+" else ""}${String.format("%.1f", it)}%)" } ?: "(no baseline)"
}
