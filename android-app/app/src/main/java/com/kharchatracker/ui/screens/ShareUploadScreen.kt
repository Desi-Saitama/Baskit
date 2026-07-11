package com.kharchatracker.ui.screens

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.data.cache.OfflineCache
import com.kharchatracker.data.model.*
import com.kharchatracker.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * This screen handles both:
 * 1. Incoming share intents (files shared from other apps)
 * 2. Manual file picker for uploading
 *
 * Flow: File → Parse via API → Review/Edit → Save
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ShareUploadScreen(
    sharedUri: Uri? = null,
    onOrderSaved: () -> Unit = {}
) {
    val context = LocalContext.current
    val apiClient = remember { ApiClient.getInstance(context) }
    val offlineCache = remember { OfflineCache(context) }
    val scope = rememberCoroutineScope()

    // State
    var selectedUri by remember { mutableStateOf(sharedUri) }
    var selectedFileName by remember { mutableStateOf<String?>(null) }
    var isParsing by remember { mutableStateOf(false) }
    var isSaving by remember { mutableStateOf(false) }
    var parseError by remember { mutableStateOf<String?>(null) }
    var saveSuccess by remember { mutableStateOf(false) }
    var parsedData by remember { mutableStateOf<ParsedOrder?>(null) }

    // Editable fields (initialized from parsed data)
    var orderDate by remember { mutableStateOf("") }
    var appName by remember { mutableStateOf("") }
    var appCategory by remember { mutableStateOf("") }
    var orderId by remember { mutableStateOf("") }
    var totalAmount by remember { mutableStateOf("") }
    var deliveryFee by remember { mutableStateOf("") }
    var discount by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var editableItems by remember { mutableStateOf<List<MutableEditableItem>>(emptyList()) }

    // File picker
    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            selectedUri = it
            selectedFileName = getFileName(context, it)
            parsedData = null
            saveSuccess = false
        }
    }

    // Auto-parse if shared URI is provided
    LaunchedEffect(sharedUri) {
        if (sharedUri != null) {
            selectedUri = sharedUri
            selectedFileName = getFileName(context, sharedUri)
        }
    }

    // Parse function
    fun parseFile() {
        val uri = selectedUri ?: return
        scope.launch {
            isParsing = true
            parseError = null
            try {
                val service = apiClient.getService()
                val bytes = withContext(Dispatchers.IO) {
                    val inputStream = context.contentResolver.openInputStream(uri)
                        ?: throw Exception("Cannot read file")
                    inputStream.use { it.readBytes() }
                }

                val mimeType = context.contentResolver.getType(uri) ?: "application/octet-stream"
                val fileName = selectedFileName ?: "file"

                val requestBody = bytes.toRequestBody(mimeType.toMediaTypeOrNull())
                val filePart = MultipartBody.Part.createFormData("file", fileName, requestBody)

                val response = service.parseFile(filePart)

                if (response.isSuccessful) {
                    val parsed = response.body()?.parsed
                    parsedData = parsed

                    // Fill editable fields
                    orderDate = parsed?.orderDate ?: ""
                    appName = parsed?.resolvedApp ?: ""
                    appCategory = parsed?.resolvedCategory ?: "groceries"
                    orderId = parsed?.orderId ?: ""
                    totalAmount = String.format("%.2f", parsed?.totalAmount ?: 0.0)
                    deliveryFee = String.format("%.2f", parsed?.deliveryFee ?: 0.0)
                    discount = String.format("%.2f", parsed?.discount ?: 0.0)
                    editableItems = parsed?.items?.map { item ->
                        MutableEditableItem(
                            name = mutableStateOf(item.name),
                            brand = mutableStateOf(item.brand),
                            category = mutableStateOf(item.category),
                            quantity = mutableStateOf(item.quantity),
                            unitPrice = mutableStateOf(String.format("%.2f", item.unitPrice)),
                            totalPrice = mutableStateOf(String.format("%.2f", item.totalPrice)),
                        )
                    } ?: emptyList()
                } else {
                    parseError = "Parse failed: ${response.errorBody()?.string()}"
                }
            } catch (e: Exception) {
                parseError = "Parse failed: ${e.message}"
            } finally {
                isParsing = false
            }
        }
    }

    // Save function
    fun saveOrder() {
        scope.launch {
            isSaving = true
            try {
                val service = apiClient.getService()
                val itemRequests = editableItems.map { item ->
                    OrderItemRequest(
                        name = item.name.value,
                        brand = item.brand.value,
                        category = item.category.value,
                        quantity = item.quantity.value,
                        unitPrice = item.unitPrice.value.toDoubleOrNull() ?: 0.0,
                        totalPrice = item.totalPrice.value.toDoubleOrNull() ?: 0.0,
                    )
                }

                val saveRequest = OrderSaveRequest(
                    orderDate = orderDate,
                    appName = appName,
                    appCategory = appCategory,
                    orderId = orderId,
                    totalAmount = totalAmount.toDoubleOrNull() ?: 0.0,
                    deliveryFee = deliveryFee.toDoubleOrNull() ?: 0.0,
                    discount = discount.toDoubleOrNull() ?: 0.0,
                    notes = notes,
                    items = itemRequests
                )

                val response = service.saveParsedOrder(saveRequest)
                if (response.isSuccessful) {
                    runCatching {
                        val ordersResponse = service.getOrders(limit = 500)
                        if (ordersResponse.isSuccessful) {
                            offlineCache.saveOrders(ordersResponse.body()?.orders ?: emptyList())
                        }
                    }
                    saveSuccess = true
                    // Reset
                    selectedUri = null
                    parsedData = null
                    onOrderSaved()
                } else if (response.code() == 409) {
                    parseError = "⚠️ Duplicate order detected. This order already exists."
                } else {
                    parseError = "Save failed: ${response.errorBody()?.string()}"
                }
            } catch (e: Exception) {
                parseError = "Save failed: ${e.message}"
            } finally {
                isSaving = false
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp)
    ) {
        // Title changes based on whether it's a share intent
        Text(
            text = if (sharedUri != null) "📤 Shared Invoice" else "📤 Upload Invoice",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )

        if (sharedUri != null) {
            Text(
                "File received from another app. Tap Parse to extract order details.",
                style = MaterialTheme.typography.bodySmall,
                color = TextSecondary
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Success banner
        AnimatedVisibility(visible = saveSuccess) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = Green.copy(alpha = 0.15f)
                ),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("✅", fontSize = 24.sp)
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            "Order saved!",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Green
                        )
                        Text(
                            "It's now synced and visible on the web app too.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        // ── Step 1: File Selection ───────────────────────────────────────
        if (selectedUri == null) {
            // File picker zone
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(200.dp)
                    .clip(RoundedCornerShape(16.dp))
                    .border(
                        width = 2.dp,
                        brush = Brush.linearGradient(
                            colors = listOf(Purple50.copy(alpha = 0.5f), Purple40.copy(alpha = 0.3f))
                        ),
                        shape = RoundedCornerShape(16.dp)
                    )
                    .background(
                        brush = Brush.linearGradient(
                            colors = listOf(
                                Purple50.copy(alpha = 0.05f),
                                DarkSurface.copy(alpha = 0.8f)
                            )
                        )
                    )
                    .clickable {
                        filePickerLauncher.launch("*/*")
                    },
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.UploadFile,
                        contentDescription = "Upload",
                        modifier = Modifier.size(48.dp),
                        tint = Purple50
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "Tap to pick a file",
                        style = MaterialTheme.typography.titleMedium,
                        color = Purple50
                    )
                    Text(
                        "PDF invoices or screenshot images",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary
                    )
                }
            }
        } else {
            // File selected — show name + parse button
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        Icons.Default.Description,
                        contentDescription = "File",
                        tint = Purple50,
                        modifier = Modifier.size(32.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            selectedFileName ?: "Selected file",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            "Ready to parse",
                            style = MaterialTheme.typography.bodySmall,
                            color = Green
                        )
                    }
                    if (sharedUri == null) {
                        IconButton(onClick = {
                            selectedUri = null
                            parsedData = null
                            parseError = null
                        }) {
                            Icon(Icons.Default.Close, "Remove", tint = TextMuted)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (parsedData == null) {
                // Parse button
                Button(
                    onClick = { parseFile() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !isParsing,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Purple50)
                ) {
                    if (isParsing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Parsing with AI...")
                    } else {
                        Text("🤖 Parse with Gemini AI", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // Error
        parseError?.let { err ->
            Spacer(modifier = Modifier.height(12.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = Red.copy(alpha = 0.15f)
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(err, color = Red, modifier = Modifier.padding(12.dp),
                    style = MaterialTheme.typography.bodySmall)
            }
        }

        // ── Step 2: Review & Edit ────────────────────────────────────────
        AnimatedVisibility(
            visible = parsedData != null,
            enter = fadeIn() + slideInVertically()
        ) {
            Column {
                Spacer(modifier = Modifier.height(20.dp))
                Text(
                    text = "✏️ Review & Edit",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Text(
                    "Edit any fields the AI got wrong before saving.",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
                Spacer(modifier = Modifier.height(12.dp))

                // Order fields
                val appNames = listOf("zepto", "blinkit", "instamart", "bigbasket", "jiomart", "swiggy", "zomato")

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = orderDate,
                        onValueChange = { orderDate = it },
                        label = { Text("Date") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                    OutlinedTextField(
                        value = orderId,
                        onValueChange = { orderId = it },
                        label = { Text("Order ID") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // App selector
                var appExpanded by remember { mutableStateOf(false) }
                ExposedDropdownMenuBox(
                    expanded = appExpanded,
                    onExpandedChange = { appExpanded = it }
                ) {
                    OutlinedTextField(
                        value = appName.replaceFirstChar { it.uppercase() },
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("App") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = appExpanded) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .menuAnchor(),
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                    ExposedDropdownMenu(
                        expanded = appExpanded,
                        onDismissRequest = { appExpanded = false }
                    ) {
                        appNames.forEach { app ->
                            DropdownMenuItem(
                                text = {
                                    Text("${AppColors.iconForApp(app)} ${app.replaceFirstChar { it.uppercase() }}")
                                },
                                onClick = {
                                    appName = app
                                    appExpanded = false
                                }
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = totalAmount,
                        onValueChange = { totalAmount = it },
                        label = { Text("Total (₹)") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                    OutlinedTextField(
                        value = deliveryFee,
                        onValueChange = { deliveryFee = it },
                        label = { Text("Delivery (₹)") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                    OutlinedTextField(
                        value = discount,
                        onValueChange = { discount = it },
                        label = { Text("Discount (₹)") },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = fieldColors()
                    )
                }

                // Items
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "🛍️ Items (${editableItems.size})",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(8.dp))

                editableItems.forEachIndexed { idx, item ->
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DarkSurface),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            OutlinedTextField(
                                value = item.name.value,
                                onValueChange = { item.name.value = it },
                                label = { Text("Item Name") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true,
                                shape = RoundedCornerShape(8.dp),
                                colors = fieldColors()
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                OutlinedTextField(
                                    value = item.quantity.value,
                                    onValueChange = { item.quantity.value = it },
                                    label = { Text("Qty") },
                                    modifier = Modifier.weight(1f),
                                    singleLine = true,
                                    shape = RoundedCornerShape(8.dp),
                                    colors = fieldColors()
                                )
                                OutlinedTextField(
                                    value = item.unitPrice.value,
                                    onValueChange = { item.unitPrice.value = it },
                                    label = { Text("Unit ₹") },
                                    modifier = Modifier.weight(1f),
                                    singleLine = true,
                                    shape = RoundedCornerShape(8.dp),
                                    colors = fieldColors()
                                )
                                OutlinedTextField(
                                    value = item.totalPrice.value,
                                    onValueChange = { item.totalPrice.value = it },
                                    label = { Text("Total ₹") },
                                    modifier = Modifier.weight(1f),
                                    singleLine = true,
                                    shape = RoundedCornerShape(8.dp),
                                    colors = fieldColors()
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                }

                // Save button
                Spacer(modifier = Modifier.height(16.dp))
                Button(
                    onClick = { saveOrder() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    enabled = !isSaving && appName.isNotBlank(),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Green)
                ) {
                    if (isSaving) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Saving...")
                    } else {
                        Text("💾 Save Order", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    }
                }

                Spacer(modifier = Modifier.height(80.dp))
            }
        }
    }
}

// Helper class for editable items
data class MutableEditableItem(
    val name: MutableState<String>,
    val brand: MutableState<String>,
    val category: MutableState<String>,
    val quantity: MutableState<String>,
    val unitPrice: MutableState<String>,
    val totalPrice: MutableState<String>,
)

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = Purple50,
    unfocusedBorderColor = DarkSurfaceVariant,
    focusedContainerColor = DarkBg,
    unfocusedContainerColor = DarkBg,
)

private fun getFileName(context: Context, uri: Uri): String {
    var name = "file"
    context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
        val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
        if (cursor.moveToFirst() && nameIndex >= 0) {
            name = cursor.getString(nameIndex)
        }
    }
    return name
}

private fun AppColors.iconForApp(appName: String): String = when (appName.lowercase()) {
    "zepto" -> "⚡"
    "blinkit" -> "💛"
    "instamart" -> "🟠"
    "bigbasket" -> "🟢"
    "jiomart" -> "🔵"
    "swiggy" -> "🍊"
    "zomato" -> "🔴"
    else -> "🛒"
}
