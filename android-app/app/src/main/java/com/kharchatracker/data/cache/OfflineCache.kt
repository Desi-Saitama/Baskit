package com.kharchatracker.data.cache

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.kharchatracker.data.model.AppStat
import com.kharchatracker.data.model.MonthlyStatsResponse
import com.kharchatracker.data.model.Order
import com.kharchatracker.data.model.OrderItem
import com.kharchatracker.data.model.StatsSummary
import kotlinx.coroutines.flow.first
import java.lang.reflect.Type

private val Context.offlineCacheDataStore by preferencesDataStore(name = "kharcha_offline_cache")

data class CachedDashboard(
    val summary: StatsSummary?,
    val appStats: List<AppStat>,
    val recentOrders: List<Order>,
    val monthlyStats: MonthlyStatsResponse?,
    val lastSyncedAt: Long
)

data class CachedOrders(
    val orders: List<Order>,
    val lastSyncedAt: Long
)

data class CachedOrderItems(
    val items: List<OrderItem>,
    val lastSyncedAt: Long
)

class OfflineCache(context: Context) {
    private val appContext = context.applicationContext
    private val gson = Gson()
    private val orderListType = object : TypeToken<List<Order>>() {}.type
    private val appStatListType = object : TypeToken<List<AppStat>>() {}.type
    private val orderItemListType = object : TypeToken<List<OrderItem>>() {}.type

    suspend fun getDashboard(): CachedDashboard? {
        val prefs = appContext.offlineCacheDataStore.data.first()
        val summaryJson = prefs[DASHBOARD_SUMMARY_KEY]
        val appsJson = prefs[DASHBOARD_APPS_KEY]
        val recentJson = prefs[DASHBOARD_RECENT_KEY]
        val monthlyJson = prefs[DASHBOARD_MONTHLY_KEY]
        val lastSyncedAt = prefs[DASHBOARD_SYNCED_AT_KEY] ?: 0L

        if (summaryJson == null && appsJson == null && recentJson == null && monthlyJson == null && lastSyncedAt == 0L) {
            return null
        }

        return CachedDashboard(
            summary = fromJson(summaryJson, StatsSummary::class.java),
            appStats = fromJson(appsJson, appStatListType) ?: emptyList(),
            recentOrders = fromJson(recentJson, orderListType) ?: emptyList(),
            monthlyStats = fromJson(monthlyJson, MonthlyStatsResponse::class.java),
            lastSyncedAt = lastSyncedAt
        )
    }

    suspend fun saveDashboard(
        summary: StatsSummary?,
        appStats: List<AppStat>,
        recentOrders: List<Order>,
        monthlyStats: MonthlyStatsResponse?
    ) {
        appContext.offlineCacheDataStore.edit { prefs ->
            if (summary != null) {
                prefs[DASHBOARD_SUMMARY_KEY] = gson.toJson(summary)
            }
            prefs[DASHBOARD_APPS_KEY] = gson.toJson(appStats)
            prefs[DASHBOARD_RECENT_KEY] = gson.toJson(recentOrders)
            if (monthlyStats != null) {
                prefs[DASHBOARD_MONTHLY_KEY] = gson.toJson(monthlyStats)
            }
            prefs[DASHBOARD_SYNCED_AT_KEY] = System.currentTimeMillis()
        }
    }

    suspend fun getOrders(): CachedOrders? {
        val prefs = appContext.offlineCacheDataStore.data.first()
        val ordersJson = prefs[ORDERS_KEY]
        val lastSyncedAt = prefs[ORDERS_SYNCED_AT_KEY] ?: 0L

        if (ordersJson == null && lastSyncedAt == 0L) {
            return null
        }

        return CachedOrders(
            orders = fromJson(ordersJson, orderListType) ?: emptyList(),
            lastSyncedAt = lastSyncedAt
        )
    }

    suspend fun saveOrders(orders: List<Order>) {
        appContext.offlineCacheDataStore.edit { prefs ->
            prefs[ORDERS_KEY] = gson.toJson(orders)
            prefs[ORDERS_SYNCED_AT_KEY] = System.currentTimeMillis()
        }
    }

    suspend fun getOrderItems(orderId: Int): CachedOrderItems? {
        val prefs = appContext.offlineCacheDataStore.data.first()
        val itemsJson = prefs[orderItemsKey(orderId)]
        val lastSyncedAt = prefs[orderItemsSyncedAtKey(orderId)] ?: 0L

        if (itemsJson == null && lastSyncedAt == 0L) {
            return null
        }

        return CachedOrderItems(
            items = fromJson(itemsJson, orderItemListType) ?: emptyList(),
            lastSyncedAt = lastSyncedAt
        )
    }

    suspend fun saveOrderItems(orderId: Int, items: List<OrderItem>) {
        appContext.offlineCacheDataStore.edit { prefs ->
            prefs[orderItemsKey(orderId)] = gson.toJson(items)
            prefs[orderItemsSyncedAtKey(orderId)] = System.currentTimeMillis()
        }
    }

    suspend fun removeOrder(orderId: Int) {
        appContext.offlineCacheDataStore.edit { prefs ->
            val cachedOrders = fromJson(prefs[ORDERS_KEY], orderListType) ?: emptyList<Order>()
            prefs[ORDERS_KEY] = gson.toJson(cachedOrders.filterNot { it.id == orderId })
            prefs[ORDERS_SYNCED_AT_KEY] = System.currentTimeMillis()
            prefs.remove(orderItemsKey(orderId))
            prefs.remove(orderItemsSyncedAtKey(orderId))
        }
    }

    suspend fun clearAll() {
        appContext.offlineCacheDataStore.edit { it.clear() }
    }

    private fun <T> fromJson(json: String?, type: Type): T? {
        if (json.isNullOrBlank()) return null
        return runCatching { gson.fromJson<T>(json, type) }.getOrNull()
    }

    private fun <T> fromJson(json: String?, clazz: Class<T>): T? {
        if (json.isNullOrBlank()) return null
        return runCatching { gson.fromJson(json, clazz) }.getOrNull()
    }

    private fun orderItemsKey(orderId: Int) = stringPreferencesKey("order_items_$orderId")

    private fun orderItemsSyncedAtKey(orderId: Int) = longPreferencesKey("order_items_synced_at_$orderId")

    companion object {
        private val DASHBOARD_SUMMARY_KEY = stringPreferencesKey("dashboard_summary")
        private val DASHBOARD_APPS_KEY = stringPreferencesKey("dashboard_apps")
        private val DASHBOARD_RECENT_KEY = stringPreferencesKey("dashboard_recent")
        private val DASHBOARD_MONTHLY_KEY = stringPreferencesKey("dashboard_monthly")
        private val DASHBOARD_SYNCED_AT_KEY = longPreferencesKey("dashboard_synced_at")
        private val ORDERS_KEY = stringPreferencesKey("orders")
        private val ORDERS_SYNCED_AT_KEY = longPreferencesKey("orders_synced_at")
    }
}
