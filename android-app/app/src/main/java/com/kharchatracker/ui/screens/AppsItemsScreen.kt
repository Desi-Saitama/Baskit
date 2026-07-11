package com.kharchatracker.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.model.AppStat
import com.kharchatracker.data.model.AvailableMonth
import com.kharchatracker.data.model.ItemFrequency
import com.kharchatracker.ui.components.AppStatCard
import com.kharchatracker.ui.components.ShimmerBox
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope

@Composable
fun AppsItemsScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    var months by remember { mutableStateOf<List<AvailableMonth>>(emptyList()) }
    var selectedMonth by remember { mutableStateOf<String?>(null) }
    var apps by remember { mutableStateOf<List<AppStat>>(emptyList()) }
    var items by remember { mutableStateOf<List<ItemFrequency>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            val response = apiClient.getService().getAvailableMonths()
            if (!response.isSuccessful) throw Exception("Server returned ${response.code()}")
            months = response.body()?.months ?: emptyList()
            selectedMonth = months.firstOrNull()?.month
            if (months.isEmpty()) loading = false
        } catch (e: Exception) {
            error = "Could not load recorded months: ${e.message}"
            loading = false
        }
    }

    LaunchedEffect(selectedMonth) {
        val month = selectedMonth ?: return@LaunchedEffect
        loading = true
        try {
            val service = apiClient.getService()
            val (appsResponse, itemsResponse) = coroutineScope {
                val appRequest = async { service.getStatsByApp(month) }
                val itemRequest = async { service.getItemFrequency(limit = 50, month = month) }
                appRequest.await() to itemRequest.await()
            }
            if (!appsResponse.isSuccessful || !itemsResponse.isSuccessful) {
                throw Exception("Server returned ${appsResponse.code()}/${itemsResponse.code()}")
            }
            apps = appsResponse.body()?.apps ?: emptyList()
            items = itemsResponse.body()?.items ?: emptyList()
            error = null
        } catch (e: Exception) {
            error = "Could not load this month: ${e.message}"
        } finally {
            loading = false
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "Apps & items",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = "Compare apps and the items you bought in a recorded month.",
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary
        )
        Spacer(modifier = Modifier.height(16.dp))

        MonthChooser(months = months, selectedMonth = selectedMonth, onSelected = { selectedMonth = it })
        Spacer(modifier = Modifier.height(20.dp))

        if (loading) {
            repeat(3) {
                ShimmerBox(modifier = Modifier.fillMaxWidth().height(88.dp))
                Spacer(modifier = Modifier.height(8.dp))
            }
        } else if (error != null) {
            Card(
                colors = CardDefaults.cardColors(containerColor = Red.copy(alpha = 0.12f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(error.orEmpty(), color = Red, modifier = Modifier.padding(14.dp))
            }
        } else if (months.isEmpty()) {
            EmptyState("No recorded months yet", "Upload an invoice to start tracking apps and items.")
        } else {
            Text("App breakdown", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = TextPrimary)
            Spacer(modifier = Modifier.height(10.dp))
            if (apps.isEmpty()) {
                EmptyState("No app activity", "There are no app totals for this month.")
            } else {
                apps.forEach { app ->
                    AppStatCard(app.appName, app.orders, app.totalSpent, app.totalSaved)
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }

            Spacer(modifier = Modifier.height(20.dp))
            Text("Items", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = TextPrimary)
            Spacer(modifier = Modifier.height(10.dp))
            if (items.isEmpty()) {
                EmptyState("No item details", "This month's orders do not contain item details.")
            } else {
                items.forEach { item ->
                    ItemRow(item)
                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }
        Spacer(modifier = Modifier.height(80.dp))
    }
}

@Composable
private fun MonthChooser(months: List<AvailableMonth>, selectedMonth: String?, onSelected: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    val selected = months.find { it.month == selectedMonth }
    Box {
        OutlinedButton(
            onClick = { expanded = true },
            enabled = months.isNotEmpty(),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.outlinedButtonColors(contentColor = Purple50)
        ) {
            Text("Month · ${selected?.label ?: "No data"}")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            months.forEach { month ->
                DropdownMenuItem(
                    text = { Text("${month.label} · ${month.totalOrders} orders") },
                    onClick = { onSelected(month.month); expanded = false }
                )
            }
        }
    }
}

@Composable
private fun ItemRow(item: ItemFrequency) {
    Card(
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(item.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = TextPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    text = listOf(item.brand, item.category).filter { it.isNotBlank() }.joinToString(" · ").ifBlank { "Uncategorised" },
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text("${item.times} purchases · avg ₹${formatItemAmount(item.avgPrice)}", style = MaterialTheme.typography.bodySmall, color = TextMuted)
            }
            Text("₹${formatItemAmount(item.totalSpent)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = Purple50)
        }
    }
}

@Composable
private fun EmptyState(title: String, message: String) {
    Card(colors = CardDefaults.cardColors(containerColor = DarkSurface), modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(18.dp)) {
            Text(title, fontWeight = FontWeight.Bold, color = TextPrimary)
            Spacer(modifier = Modifier.height(4.dp))
            Text(message, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
        }
    }
}

private fun formatItemAmount(amount: Double): String = when {
    amount >= 100000 -> "${String.format("%.1f", amount / 100000)}L"
    amount >= 1000 -> String.format("%,.0f", amount)
    else -> String.format("%.0f", amount)
}
