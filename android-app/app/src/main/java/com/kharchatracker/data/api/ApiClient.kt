package com.kharchatracker.data.api

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

private val Context.dataStore by preferencesDataStore(name = "kharcha_prefs")

/**
 * Manages API client creation, auth token storage, and server URL configuration.
 */
class ApiClient(private val context: Context) {

    companion object {
        private val TOKEN_KEY = stringPreferencesKey("auth_token")
        private val SERVER_URL_KEY = stringPreferencesKey("server_url")
        const val DEFAULT_SERVER_URL = "http://10.0.2.2:8000/"  // Android emulator → host

        @Volatile
        private var instance: ApiClient? = null

        fun getInstance(context: Context): ApiClient {
            return instance ?: synchronized(this) {
                instance ?: ApiClient(context.applicationContext).also { instance = it }
            }
        }
    }

    private var cachedToken: String? = null
    private var cachedServerUrl: String? = null
    private var cachedService: ApiService? = null

    // ── Token management ─────────────────────────────────────────────────────

    suspend fun saveToken(token: String) {
        cachedToken = token
        cachedService = null  // Force rebuild
        context.dataStore.edit { prefs ->
            prefs[TOKEN_KEY] = token
        }
    }

    suspend fun getToken(): String? {
        if (cachedToken != null) return cachedToken
        val token = context.dataStore.data.first()[TOKEN_KEY]
        cachedToken = token
        return token
    }

    suspend fun clearToken() {
        cachedToken = null
        cachedService = null
        context.dataStore.edit { prefs ->
            prefs.remove(TOKEN_KEY)
        }
    }

    fun isLoggedIn(): Flow<Boolean> {
        return context.dataStore.data.map { prefs ->
            !prefs[TOKEN_KEY].isNullOrBlank()
        }
    }

    // ── Server URL management ────────────────────────────────────────────────

    suspend fun saveServerUrl(url: String) {
        val normalizedUrl = if (url.endsWith("/")) url else "$url/"
        cachedServerUrl = normalizedUrl
        cachedService = null  // Force rebuild
        context.dataStore.edit { prefs ->
            prefs[SERVER_URL_KEY] = normalizedUrl
        }
    }

    suspend fun getServerUrl(): String {
        if (cachedServerUrl != null) return cachedServerUrl!!
        val url = context.dataStore.data.first()[SERVER_URL_KEY] ?: DEFAULT_SERVER_URL
        cachedServerUrl = url
        return url
    }

    fun serverUrlFlow(): Flow<String> {
        return context.dataStore.data.map { prefs ->
            prefs[SERVER_URL_KEY] ?: DEFAULT_SERVER_URL
        }
    }

    // ── API Service ──────────────────────────────────────────────────────────

    suspend fun getService(): ApiService {
        cachedService?.let { return it }

        val token = getToken()
        val serverUrl = getServerUrl()

        val authInterceptor = Interceptor { chain ->
            val request = if (!token.isNullOrBlank()) {
                chain.request().newBuilder()
                    .addHeader("Authorization", "Bearer $token")
                    .build()
            } else {
                chain.request()
            }
            chain.proceed(request)
        }

        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)    // Gemini parsing can be slow
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(serverUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        val service = retrofit.create(ApiService::class.java)
        cachedService = service
        return service
    }

    /**
     * Get a service without auth token (for login endpoint).
     */
    suspend fun getUnauthService(): ApiService {
        val serverUrl = getServerUrl()

        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(serverUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

        return retrofit.create(ApiService::class.java)
    }
}
