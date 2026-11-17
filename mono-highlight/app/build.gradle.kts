plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.monohighlight"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.example.monohighlight"
        // takeScreenshotOfWindow() が API 34 (Android 14) から
        minSdk = 34
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // 自分用なのでデバッグ鍵で署名
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
