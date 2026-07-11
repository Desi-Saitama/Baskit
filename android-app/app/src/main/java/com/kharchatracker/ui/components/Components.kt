package com.kharchatracker.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.kharchatracker.ui.theme.*

/**
 * Gradient KPI card matching the web app's dashboard style.
 */
@Composable
fun KpiCard(
    icon: String,
    value: String,
    label: String,
    accentColor: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .height(112.dp),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = DarkSurface
        ),
        border = BorderStroke(1.dp, DarkSurfaceVariant.copy(alpha = 0.65f)),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(RoundedCornerShape(99.dp))
                        .background(accentColor)
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = value,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.ExtraBold,
                    color = TextPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            Spacer(modifier = Modifier.weight(1f))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(RoundedCornerShape(99.dp))
                    .background(accentColor.copy(alpha = 0.16f))
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.68f)
                        .fillMaxHeight()
                        .background(accentColor)
                )
            }
        }
    }
}

/**
 * Order card for the history list.
 */
@Composable
fun OrderCard(
    appName: String,
    orderDate: String,
    totalAmount: Double,
    discount: Double,
    orderId: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val appColor = AppColors.forApp(appName)
    val appIcon = AppColors.iconForApp(appName)

    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // App icon + color bar
            Box(
                modifier = Modifier
                    .width(4.dp)
                    .height(48.dp)
                    .clip(RoundedCornerShape(2.dp))
                    .background(appColor)
            )
            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(appIcon, fontSize = 16.sp)
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = appName.replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = appColor
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = orderDate,
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
                if (!orderId.isNullOrBlank()) {
                    Text(
                        text = "#$orderId",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = "₹${String.format("%,.0f", totalAmount)}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                if (discount > 0) {
                    Text(
                        text = "-₹${String.format("%,.0f", discount)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Green
                    )
                }
            }
        }
    }
}

/**
 * App stat card for the stats breakdown.
 */
@Composable
fun AppStatCard(
    appName: String,
    orders: Int,
    totalSpent: Double,
    totalSaved: Double,
    modifier: Modifier = Modifier
) {
    val appColor = AppColors.forApp(appName)
    val appIcon = AppColors.iconForApp(appName)

    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .width(4.dp)
                        .height(32.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(appColor)
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(appIcon, fontSize = 20.sp)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = appName.replaceFirstChar { it.uppercase() },
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = appColor
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StatItem("Orders", "$orders")
                StatItem("Spent", "₹${String.format("%,.0f", totalSpent)}")
                StatItem("Saved", "₹${String.format("%,.0f", totalSaved)}", Green)
            }
        }
    }
}

@Composable
private fun StatItem(label: String, value: String, valueColor: Color = TextPrimary) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Bold,
            color = valueColor
        )
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = TextSecondary
        )
    }
}

/**
 * Shimmer loading placeholder.
 */
@Composable
fun ShimmerBox(
    modifier: Modifier = Modifier
) {
    val shimmerColors = listOf(
        DarkSurfaceVariant.copy(alpha = 0.3f),
        DarkSurfaceVariant.copy(alpha = 0.5f),
        DarkSurfaceVariant.copy(alpha = 0.3f),
    )

    val transition = rememberInfiniteTransition(label = "shimmer")
    val translateAnim by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1000f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "shimmer_translate"
    )

    Box(
        modifier = modifier
            .clip(RoundedCornerShape(8.dp))
            .background(
                brush = Brush.linearGradient(
                    colors = shimmerColors,
                    start = Offset(translateAnim - 200f, 0f),
                    end = Offset(translateAnim + 200f, 0f)
                )
            )
    )
}
