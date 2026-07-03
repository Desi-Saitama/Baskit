package com.kharchatracker

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import androidx.lifecycle.lifecycleScope
import com.kharchatracker.data.api.ApiClient
import com.kharchatracker.ui.navigation.MainNavigation
import com.kharchatracker.ui.screens.LoginScreen
import com.kharchatracker.ui.theme.KharchaTrackerTheme
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val apiClient = ApiClient.getInstance(this)

        setContent {
            KharchaTrackerTheme {
                var isLoggedIn by remember { mutableStateOf<Boolean?>(null) }
                var sharedUri by remember { mutableStateOf<Uri?>(null) }

                // Check login state
                LaunchedEffect(Unit) {
                    isLoggedIn = apiClient.isLoggedIn().first()
                }

                // Handle share intent
                LaunchedEffect(Unit) {
                    sharedUri = handleIncomingIntent(intent)
                }

                when (isLoggedIn) {
                    null -> {
                        // Loading — show nothing or splash
                    }
                    false -> {
                        LoginScreen(
                            onLoginSuccess = {
                                isLoggedIn = true
                            }
                        )
                    }
                    true -> {
                        MainNavigation(
                            sharedUri = sharedUri,
                            onLogout = {
                                isLoggedIn = false
                                sharedUri = null
                            }
                        )
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // Handle share when app is already running
        setIntent(intent)
        // The LaunchedEffect in setContent will pick it up on recomposition
        recreate()
    }

    private fun handleIncomingIntent(intent: Intent?): Uri? {
        if (intent == null) return null

        return when (intent.action) {
            Intent.ACTION_SEND -> {
                // Single file share (image or PDF)
                if (intent.type?.startsWith("image/") == true ||
                    intent.type == "application/pdf"
                ) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                        ?: intent.clipData?.getItemAt(0)?.uri
                } else {
                    null
                }
            }
            Intent.ACTION_SEND_MULTIPLE -> {
                // Multiple images — take the first one for now
                val uris = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM, Uri::class.java)
                uris?.firstOrNull()
            }
            else -> null
        }
    }
}
