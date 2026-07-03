package com.kharchatracker.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val scope = rememberCoroutineScope()

    var serverUrl by remember { mutableStateOf("") }
    var isTestingConnection by remember { mutableStateOf(false) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    var connectionOk by remember { mutableStateOf<Boolean?>(null) }

    LaunchedEffect(Unit) {
        serverUrl = apiClient.getServerUrl()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        Text(
            text = "⚙️ Settings",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(24.dp))

        // ── Server Connection ────────────────────────────────────────────
        Card(
            colors = CardDefaults.cardColors(containerColor = DarkSurface),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Dns, "Server", tint = Purple50)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "Server Connection",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))

                OutlinedTextField(
                    value = serverUrl,
                    onValueChange = { serverUrl = it },
                    label = { Text("Server URL") },
                    placeholder = { Text(ApiClient.DEFAULT_SERVER_URL) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    shape = RoundedCornerShape(8.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Purple50,
                        unfocusedBorderColor = DarkSurfaceVariant,
                        focusedContainerColor = DarkBg,
                        unfocusedContainerColor = DarkBg,
                    )
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = "• For emulator: http://10.0.2.2:8000/\n• For physical device: http://YOUR_PC_IP:8000/",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMuted
                )

                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            scope.launch {
                                apiClient.saveServerUrl(serverUrl)
                            }
                        },
                        shape = RoundedCornerShape(8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Purple50),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("Save URL")
                    }

                    OutlinedButton(
                        onClick = {
                            isTestingConnection = true
                            connectionStatus = null
                            scope.launch {
                                try {
                                    apiClient.saveServerUrl(serverUrl)
                                    val service = apiClient.getService()
                                    val response = service.healthCheck()
                                    if (response.isSuccessful) {
                                        connectionOk = true
                                        connectionStatus = "✅ Connected — ${response.body()?.app} v${response.body()?.version}"
                                    } else {
                                        connectionOk = false
                                        connectionStatus = "❌ Server returned ${response.code()}"
                                    }
                                } catch (e: Exception) {
                                    connectionOk = false
                                    connectionStatus = "❌ ${e.message}"
                                } finally {
                                    isTestingConnection = false
                                }
                            }
                        },
                        enabled = !isTestingConnection,
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.weight(1f)
                    ) {
                        if (isTestingConnection) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text("Test Connection")
                        }
                    }
                }

                connectionStatus?.let { status ->
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = status,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (connectionOk == true) Green else Red
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // ── About ────────────────────────────────────────────────────────
        Card(
            colors = CardDefaults.cardColors(containerColor = DarkSurface),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Info, "About", tint = Purple50)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "About",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))

                Text("🛒 Kharcha Tracker", fontSize = 18.sp, fontWeight = FontWeight.Bold, color = Purple50)
                Text("v1.0.0 • Android Companion App", style = MaterialTheme.typography.bodySmall, color = TextSecondary)
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Track your expenses from Indian delivery apps. " +
                    "Share bills directly from any app to parse and save them. " +
                    "All data syncs with the web dashboard.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextMuted
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // ── How to Use Share ─────────────────────────────────────────────
        Card(
            colors = CardDefaults.cardColors(containerColor = DarkSurface),
            shape = RoundedCornerShape(12.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Share, "Share", tint = Amber)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        "How to Share Bills",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = TextPrimary
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))

                val steps = listOf(
                    "Open your invoice in any app (WhatsApp, Email, Files)",
                    "Tap the Share button",
                    "Select \"Kharcha Tracker\" from the share menu",
                    "The app will parse the bill using AI",
                    "Review the extracted data and tap Save"
                )
                steps.forEachIndexed { idx, step ->
                    Row(modifier = Modifier.padding(vertical = 4.dp)) {
                        Text(
                            "${idx + 1}.",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Bold,
                            color = Purple50
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            step,
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // ── Logout ───────────────────────────────────────────────────────
        Button(
            onClick = {
                scope.launch {
                    apiClient.clearToken()
                    onLogout()
                }
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Red.copy(alpha = 0.8f))
        ) {
            Icon(Icons.Default.Logout, "Logout", modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text("Sign Out", fontWeight = FontWeight.Bold)
        }

        Spacer(modifier = Modifier.height(80.dp))
    }
}
