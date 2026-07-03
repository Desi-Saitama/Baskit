package com.kharchatracker.ui.theme

import androidx.compose.ui.graphics.Color

// ── Primary palette (matching web app's purple gradient) ─────────────────────
val Purple80 = Color(0xFFD0BCFF)
val Purple60 = Color(0xFFA78BFA)
val Purple50 = Color(0xFF8B5CF6)
val Purple40 = Color(0xFF6366F1)
val Purple30 = Color(0xFF4F46E5)
val Purple20 = Color(0xFF3730A3)

// ── Accent colors ────────────────────────────────────────────────────────────
val Amber = Color(0xFFF59E0B)
val Green = Color(0xFF22C55E)
val Red = Color(0xFFEF4444)
val Blue = Color(0xFF3B82F6)
val Pink = Color(0xFFEC4899)
val Orange = Color(0xFFF97316)
val Cyan = Color(0xFF06B6D4)

// ── Surfaces (dark theme) ────────────────────────────────────────────────────
val DarkBg = Color(0xFF0F172A)
val DarkSurface = Color(0xFF1E293B)
val DarkSurfaceVariant = Color(0xFF334155)
val DarkCard = Color(0xFF1E293B)
val TextPrimary = Color(0xFFE2E8F0)
val TextSecondary = Color(0xFF94A3B8)
val TextMuted = Color(0xFF64748B)

// ── App brand colors ─────────────────────────────────────────────────────────
object AppColors {
    val zepto = Color(0xFF8B5CF6)
    val blinkit = Color(0xFFF59E0B)
    val instamart = Color(0xFFF97316)
    val bigbasket = Color(0xFF22C55E)
    val jiomart = Color(0xFF3B82F6)
    val swiggy = Color(0xFFEA580C)
    val zomato = Color(0xFFEF4444)

    fun forApp(appName: String): Color = when (appName.lowercase()) {
        "zepto" -> zepto
        "blinkit" -> blinkit
        "instamart" -> instamart
        "bigbasket" -> bigbasket
        "jiomart" -> jiomart
        "swiggy" -> swiggy
        "zomato" -> zomato
        else -> Purple50
    }

    fun iconForApp(appName: String): String = when (appName.lowercase()) {
        "zepto" -> "⚡"
        "blinkit" -> "💛"
        "instamart" -> "🟠"
        "bigbasket" -> "🟢"
        "jiomart" -> "🔵"
        "swiggy" -> "🍊"
        "zomato" -> "🔴"
        else -> "🛒"
    }
}

// ── Category colors ──────────────────────────────────────────────────────────
object CategoryColors {
    fun forCategory(cat: String): Color = when (cat) {
        "Fruits & Vegetables" -> Green
        "Dairy & Eggs" -> Amber
        "Grains & Pulses" -> Orange
        "Snacks" -> Pink
        "Beverages" -> Blue
        "Personal Care" -> Purple50
        "Household" -> Color(0xFF64748B)
        "Bakery" -> Color(0xFFD97706)
        "Spices & Condiments" -> Red
        "Ready to Eat" -> Cyan
        "Restaurant Food" -> Color(0xFFE11D48)
        "Meat & Seafood" -> Color(0xFFDC2626)
        else -> TextMuted
    }
}
