# 📱 SmartExp Backend & API Integration Guide for Android

This document provides complete documentation and technical specifications for connecting an **Android application** (Kotlin / Jetpack Compose or XML) to the **SmartExp Backend (FastAPI)**.

---

## 📑 Table of Contents
1. [Backend Overview & Architecture](#1-backend-overview--architecture)
2. [Environment Variables & Secret Keys](#2-environment-variables--secret-keys)
3. [Android Network Configuration & Base URLs](#3-android-network-configuration--base-urls)
4. [Authentication & Session Flow](#4-authentication--session-flow)
5. [Complete API Endpoints Specification](#5-complete-api-endpoints-specification)
   - [Authentication Endpoints (`/auth`)](#authentication-endpoints-auth)
   - [User & Profile Endpoints (`/user`)](#user--profile-endpoints-user)
   - [Expenses Endpoints (`/expenses`)](#expenses-endpoints-expenses)
   - [Budget Endpoints (`/budget`)](#budget-endpoints-budget)
   - [Dashboard & Analytics Endpoints (`/dashboard`)](#dashboard--analytics-endpoints-dashboard)
   - [AI Assistant & Chat Endpoints (`/chat`)](#ai-assistant--chat-endpoints-chat)
   - [Health Check (`/test`)](#health-check-test)
6. [Kotlin Data Models (DTOs)](#6-kotlin-data-models-dtos)
7. [Retrofit & OkHttp Android Client Implementation](#7-retrofit--okhttp-android-client-implementation)
8. [UI Screens & Suggested Android Architecture](#8-ui-screens--suggested-android-architecture)

---

## 1. Backend Overview & Architecture

- **Backend Framework:** FastAPI (Python 3.10+)
- **Database:** PostgreSQL (using SQLModel / Async SQLAlchemy)
- **Authentication Scheme:** JWT (JSON Web Tokens) with Argon2 password hashing
  - **Access Token:** Short-lived (15 minutes), passed in `Authorization: Bearer <token>` header.
  - **Refresh Token:** Long-lived (7 days), delivered via secure HTTP-only cookie `refresh_token`.
- **Media / Image Storage:** Cloudinary (for user avatar / profile pictures)
- **AI / NLP Services:** In-house Intent Classification & Entity Extraction for conversational expense logging.

---

## 2. Environment Variables & Secret Keys

These keys are configured in the backend's `.env` file for server runtime:

| Variable | Description | Example / Format |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://user:password@localhost:5432/smartexp` |
| `SECRET_KEY` | Secret key used to sign & verify HS256 JWT tokens | Any strong 256-bit random string |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary Account Cloud Name | `your_cloud_name` |
| `CLOUDINARY_API_KEY` | Cloudinary API Key | `123456789012345` |
| `CLOUDINARY_API_SECRET` | Cloudinary API Secret Key | `abCdEfGhIjKlMnOpQrStUvWxYz` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:5173,https://expense-tracker-frontend-nine-ruddy.vercel.app` |
| `DEBUG_MODE` | Debug flag for stack traces | `false` or `true` |

> ⚠️ **Security Notice for Android:**  
> Never store server secrets like `CLOUDINARY_API_SECRET` or `DATABASE_URL` inside your Android app code. Your Android app will communicate exclusively through the FastAPI backend, which handles media uploading and database transactions securely.

---

## 3. Android Network Configuration & Base URLs

### 🌐 Base URLs by Environment

| Environment | Base URL | Notes |
|---|---|---|
| **Android Studio Emulator** | `http://10.0.2.2:8000` | `10.0.2.2` is the special alias to your host PC's `127.0.0.1`. |
| **Physical Android Device (Debug)** | `http://<YOUR_PC_LAN_IP>:8000` | E.g. `http://192.168.1.15:8000`. Both PC and phone must be on the same Wi-Fi network. |
| **Production / Cloud Deployment** | `https://api.yourdomain.com` | Live deployed HTTPS server. |

### 🔒 Android Cleartext Traffic Setup (For Local Testing)

Android blocks non-HTTPS (`http://`) traffic by default. Configure your debug build to allow cleartext traffic:

#### 1. Create `res/xml/network_security_config.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <!-- Android Emulator host alias -->
        <domain includeSubdomains="true">10.0.2.2</domain>
        <!-- Replace with your local PC LAN IP for physical device testing -->
        <domain includeSubdomains="true">192.168.1.15</domain>
        <domain includeSubdomains="true">localhost</domain>
    </domain-config>
</network-security-config>
```

#### 2. Update `AndroidManifest.xml`:
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="true"
        ...>
    </application>
</manifest>
```

---

## 4. Authentication & Session Flow

### Flow Diagram

```
Android App                       FastAPI Backend
    │                                    │
    │── POST /auth/login ───────────────>│ Validates credentials (Argon2)
    │                                    │ Generates Access Token & Refresh Token
    │<── 200 OK ─────────────────────────│
    │    Body: { access_token }          │
    │    Set-Cookie: refresh_token=...   │
    │                                    │
    │── Store access_token in Memory/EncryptedSharedPreferences
    │── Store refresh_token Cookie in CookieJar
    │                                    │
    │── GET /expenses/get ──────────────>│ Validates Bearer Token
    │    Header: Authorization: Bearer   │
    │<── 200 OK (List of Expenses) ──────│
    │                                    │
    │── (When Access Token Expires 401) ─│
    │── POST /auth/refresh ─────────────>│ Checks Cookie: refresh_token
    │<── 200 OK: { access_token } ───────│
    │── Retry original request ─────────>│
```

1. **Login (`POST /auth/login`)**:
   - Backend returns `{"access_token": "..."}`.
   - Backend sets a `Set-Cookie: refresh_token=<token>; HttpOnly; Secure; SameSite=none; Max-Age=604800` header.
2. **Authenticated Requests**:
   - Every protected request must include:  
     `Authorization: Bearer <access_token>`
3. **Token Refresh (`POST /auth/refresh`)**:
   - Send `POST /auth/refresh`. OkHttp's `CookieJar` sends the stored `refresh_token` cookie.
   - Backend responds with a fresh `{"access_token": "..."}`.

---

## 5. Complete API Endpoints Specification

### Authentication Endpoints (`/auth`)

#### 1. Register User
- **Method:** `POST`
- **URL:** `/auth/register`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "name": "Abhishek Sharma",
  "email": "user@example.com",
  "password": "Password123"
}
```
- **Response (200 OK):**
```json
{
  "message": "User created"
}
```
- **Error (409 Conflict):** `{"detail": "Email already exists"}`
- **Error (422 Validation):** Password < 8 characters or invalid email format.

---

#### 2. Login User
- **Method:** `POST`
- **URL:** `/auth/login`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```
- **Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
*Note: Also receives `Set-Cookie: refresh_token=...`.*
- **Error (401 Unauthorized):** `{"detail": "Invalid credentials"}`

---

#### 3. Refresh Access Token
- **Method:** `POST`
- **URL:** `/auth/refresh`
- **Headers:** Include Cookie `refresh_token=<token>` (handled automatically via `CookieJar`)
- **Request Body:** *None*
- **Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- **Error (401 Unauthorized):** `{"detail": "Refresh token missing"}` or `{"detail": "Refresh token expired"}`

---

### User & Profile Endpoints (`/user`)

All `/user` endpoints require header: `Authorization: Bearer <access_token>`.

#### 1. Get User Profile
- **Method:** `GET`
- **URL:** `/user/me`
- **Response (200 OK):**
```json
{
  "name": "Abhishek Sharma",
  "email": "user@example.com",
  "profile_image": "https://res.cloudinary.com/demo/image/upload/v12345/profile_images/avatar.jpg",
  "has_onboarded": true
}
```

---

#### 2. Update Profile (Name, Email, Avatar)
- **Method:** `PUT`
- **URL:** `/user/profile`
- **Headers:** `Content-Type: multipart/form-data`
- **Form Data Parameters (all optional):**
  - `name`: string (e.g. `"Abhishek S"`)
  - `email`: string (e.g. `"new@example.com"`)
  - `profile_image`: File binary (JPEG, PNG, WebP)
- **Response (200 OK):** Returns the updated user profile object.
```json
{
  "name": "Abhishek S",
  "email": "new@example.com",
  "profile_image": "https://res.cloudinary.com/.../new_pic.jpg",
  "has_onboarded": true
}
```
- **Error (409 Conflict):** `{"detail": "Email already in use"}`

---

#### 3. Change Password
- **Method:** `POST`
- **URL:** `/user/change-password`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "old_password": "Password123",
  "new_password": "NewSecurePassword456"
}
```
- **Response (200 OK):**
```json
{
  "message": "Password changed successfully"
}
```
- **Error (400 Bad Request):** `{"detail": "Current password incorrect"}`

---

#### 4. Complete Onboarding
- **Method:** `PUT`
- **URL:** `/user/onboarded`
- **Response (200 OK):**
```json
{
  "message": "Onboarding status updated",
  "has_onboarded": true
}
```

---

#### 5. Delete Account
- **Method:** `DELETE`
- **URL:** `/user/me`
- **Response (200 OK):**
```json
{
  "message": "Account and all associated data deleted successfully"
}
```

---

### Expenses Endpoints (`/expenses`)

All require: `Authorization: Bearer <access_token>`.

#### 1. Create Expense
- **Method:** `POST`
- **URL:** `/expenses/create`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "title": "Grocery Shopping",
  "amount": 250.50,
  "category": "Food"
}
```
- **Response (200 OK):**
```json
{
  "messege": "Expense created"
}
```

---

#### 2. Get All User Expenses
- **Method:** `GET`
- **URL:** `/expenses/get`
- **Response (200 OK):**
```json
[
  {
    "exp_id": 1,
    "title": "Grocery Shopping",
    "amount": 250.5,
    "category": "Food",
    "created_at": "2026-09-15T12:00:00",
    "user_id": 4
  },
  {
    "exp_id": 2,
    "title": "Fuel",
    "amount": 120.0,
    "category": "Transport",
    "created_at": "2026-09-14T10:30:00",
    "user_id": 4
  }
]
```

---

#### 3. Get Expense by ID
- **Method:** `GET`
- **URL:** `/expenses/get/{expense_id}`
- **Response (200 OK):**
```json
{
  "exp_id": 1,
  "title": "Grocery Shopping",
  "amount": 250.5,
  "category": "Food",
  "created_at": "2026-09-15T12:00:00",
  "user_id": 4
}
```
- **Error (404 Not Found):** `{"detail": "Expense not found or unauthorized"}`

---

#### 4. Edit Expense
- **Method:** `PUT`
- **URL:** `/expenses/edit/{expense_id}`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "title": "Supermarket Shopping",
  "amount": 275.00,
  "category": "Food"
}
```
- **Response (200 OK):**
```json
{
  "message": "Expense updated",
  "expense": {
    "exp_id": 1,
    "title": "Supermarket Shopping",
    "amount": 275.0,
    "category": "Food",
    "created_at": "2026-09-15T12:00:00",
    "user_id": 4
  }
}
```

---

#### 5. Delete Expense
- **Method:** `DELETE`
- **URL:** `/expenses/dlt/{expense_id}`
- **Response (200 OK):**
```json
{
  "message": "Expense deleted"
}
```

---

### Budget Endpoints (`/budget`)

All require: `Authorization: Bearer <access_token>`.

#### Create or Update Budget
- **Method:** `POST`
- **URL:** `/budget/`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "category": "Food",     // null or omitted for overall monthly budget
  "amount": 5000.00,
  "month": 9,
  "year": 2026
}
```
- **Response (200 OK):**
```json
{
  "budget_id": 3,
  "category": "Food",
  "amount": 5000.0,
  "month": 9,
  "year": 2026
}
```

---

### Dashboard & Analytics Endpoints (`/dashboard`)

All require: `Authorization: Bearer <access_token>`.

#### Get Dashboard Analytics
- **Method:** `GET`
- **URL:** `/dashboard?range={week|month|custom}&start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}`
- **Query Parameters:**
  - `range` (*Required*): `"week"`, `"month"`, or `"custom"`
  - `start_date` (*Required if range=custom*): e.g. `"2026-09-01"`
  - `end_date` (*Required if range=custom*): e.g. `"2026-09-30"`

- **Sample Request:**  
  `GET /dashboard?range=month`

- **Response Structure (200 OK):**
```json
{
  "summary": {
    "totalSpent": 3450.50,
    "totalBudget": 10000.00,
    "avgDaily": 230.033,
    "remainingBudget": 6549.50,
    "budgetExceeded": false,
    "changePercent": -12.4,
    "income": 45000.00,
    "incomeMissing": false,
    "savings": 41549.50,
    "healthScore": 88,
    "healthStatus": "Financially Strong",
    "healthBreakdown": {
      "savings": { "score": 100, "details": "Excellent savings (≥30%)" },
      "expense": { "score": 100, "details": "Healthy spending level (≤60%)" },
      "stability": { "score": 70, "details": "Moderately consistent daily spending" },
      "budget": { "score": 100, "details": "Well within budget" },
      "income_consistency": { "score": 80, "details": "Stable income" }
    },
    "message": null
  },
  "categories": [
    { "name": "Food", "amount": 1450.50 },
    { "name": "Transport", "amount": 800.00 },
    { "name": "Entertainment", "amount": 1200.00 }
  ],
  "trends": {
    "labels": ["01 Sep", "02 Sep", "03 Sep", "04 Sep", "..."],
    "values": [0.0, 150.0, 42.5, 0.0, 310.0]
  },
  "insights": [
    "You have used 34.5% of your total budget with 15 days remaining.",
    "Food spending is your highest expense this month."
  ],
  "budgets": [
    {
      "category": "overall",
      "limit": 10000.0,
      "used": 3450.5,
      "percent": 34.505
    },
    {
      "category": "Food",
      "limit": 5000.0,
      "used": 1450.5,
      "percent": 29.01
    }
  ]
}
```

---

### AI Assistant & Chat Endpoints (`/chat`)

All require: `Authorization: Bearer <access_token>`.

SmartExp includes a conversational AI engine that can parse natural sentences, log expenses, update budgets, record income, and answer spending queries!

#### 1. Send Chat Message
- **Method:** `POST`
- **URL:** `/chat/message`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "message": "Spent 150 on coffee and snacks"
}
```
*Sample NLP Commands accepted by the assistant:*
- `"Spent 300 on groceries"` -> Automatically adds 300 to Food category!
- `"Set budget for travel 4000"` -> Automatically sets travel budget!
- `"My salary is 60000"` -> Automatically records monthly income!
- `"How much did I spend on food?"` -> Summarizes category expenses!
- `"Show my expenses"` -> Returns tabular expense list.

- **Response (200 OK):**
```json
{
  "response": "Recorded expense: ₹150.00 for coffee and snacks in Food category.",
  "data_updated": true,
  "data": null
}
```
*(If the user asked "Show my expenses", `data` contains the list of expenses so the Android chat UI can display a native card/table!)*

---

#### 2. Get Chat History
- **Method:** `GET`
- **URL:** `/chat/history`
- **Response (200 OK):**
```json
[
  {
    "sender": "user",
    "text": "Spent 150 on coffee",
    "time": "2026-09-15T14:10:00",
    "data": null
  },
  {
    "sender": "bot",
    "text": "Recorded expense: ₹150.00 for coffee in Food category.",
    "time": "2026-09-15T14:10:01",
    "data": null
  }
]
```

---

#### 3. Autocomplete Search Suggestions
- **Method:** `GET`
- **URL:** `/chat/suggestions?q={query}`
- **Query Parameter:** `q` (e.g. `sp`, `show`, `250`)
- **Response (200 OK):**
```json
{
  "suggestions": [
    "Spent 250 on entertainment",
    "Spent 250 on food",
    "Spent 250 on travel"
  ]
}
```

---

#### 4. Clear Chat History
- **Method:** `DELETE`
- **URL:** `/chat/clear`
- **Response (200 OK):**
```json
{
  "message": "Chat history cleared"
}
```

---

### Health Check (`/test`)

- **Method:** `GET`
- **URL:** `/test`
- **Response (200 OK):** `{"hello": "world"}`

---

## 6. Kotlin Data Models (DTOs)

Ready-to-use Kotlin data classes using `kotlinx.serialization` or `Gson` / `Moshi`:

```kotlin
package com.smartexp.data.model

import com.google.gson.annotations.SerializedName

// --- Auth Models ---
data class RegisterRequest(
    val name: String,
    val email: String,
    val password: String
)

data class LoginRequest(
    val email: String,
    val password: String
)

data class AuthResponse(
    @SerializedName("access_token") val accessToken: String
)

data class MessageResponse(
    val message: String
)

// --- User Models ---
data class UserProfile(
    val name: String,
    val email: String,
    @SerializedName("profile_image") val profileImage: String?,
    @SerializedName("has_onboarded") val hasOnboarded: Boolean
)

data class ChangePasswordRequest(
    @SerializedName("old_password") val oldPassword: String,
    @SerializedName("new_password") val newPassword: String
)

// --- Expense Models ---
data class ExpenseCreateRequest(
    val title: String,
    val amount: Double,
    val category: String
)

data class ExpenseItem(
    @SerializedName("exp_id") val expId: Int,
    val title: String,
    val amount: Double,
    val category: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("user_id") val userId: Int
)

// --- Budget Models ---
data class BudgetRequest(
    val category: String?,
    val amount: Double,
    val month: Int,
    val year: Int
)

data class BudgetItem(
    @SerializedName("budget_id") val budgetId: Int,
    val category: String?,
    val amount: Double,
    val month: Int,
    val year: Int
)

// --- Dashboard Models ---
data class DashboardResponse(
    val summary: DashboardSummary,
    val categories: List<CategorySpend>,
    val trends: TrendData,
    val insights: List<String>,
    val budgets: List<DashboardBudget>
)

data class DashboardSummary(
    val totalSpent: Double,
    val totalBudget: Double,
    val avgDaily: Double,
    val remainingBudget: Double,
    val budgetExceeded: Boolean,
    val changePercent: Double,
    val income: Double,
    val incomeMissing: Boolean,
    val savings: Double,
    val healthScore: Int?,
    val healthStatus: String,
    val healthBreakdown: Map<String, HealthBreakdownItem>?,
    val message: String?
)

data class HealthBreakdownItem(
    val score: Int?,
    val details: String?
)

data class CategorySpend(
    val name: String,
    val amount: Double
)

data class TrendData(
    val labels: List<String>,
    val values: List<Double>
)

data class DashboardBudget(
    val category: String,
    val limit: Double,
    val used: Double,
    val percent: Double
)

// --- Chat Models ---
data class ChatMessageRequest(
    val message: String
)

data class ChatMessageResponse(
    val response: String,
    @SerializedName("data_updated") val dataUpdated: Boolean,
    val data: Any?
)

data class ChatHistoryItem(
    val sender: String, // "user" or "bot"
    val text: String,
    val time: String,
    val data: Any?
)

data class ChatSuggestionsResponse(
    val suggestions: List<String>
)
```

---

## 7. Retrofit & OkHttp Android Client Implementation

### 1. Retrofit API Service Interface (`SmartExpApi.kt`)

```kotlin
package com.smartexp.data.api

import com.smartexp.data.model.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface SmartExpApi {

    // --- Authentication ---
    @POST("auth/register")
    async fun register(@Body request: RegisterRequest): Response<MessageResponse>

    @POST("auth/login")
    async fun login(@Body request: LoginRequest): Response<AuthResponse>

    @POST("auth/refresh")
    async fun refreshToken(): Response<AuthResponse>

    // --- User Profile ---
    @GET("user/me")
    async fun getCurrentUser(): Response<UserProfile>

    @POST("user/change-password")
    async fun changePassword(@Body request: ChangePasswordRequest): Response<MessageResponse>

    @Multipart
    @PUT("user/profile")
    async fun updateProfile(
        @Part("name") name: RequestBody?,
        @Part("email") email: RequestBody?,
        @Part profileImage: MultipartBody.Part?
    ): Response<UserProfile>

    @PUT("user/onboarded")
    async fun completeOnboarding(): Response<MessageResponse>

    @DELETE("user/me")
    async fun deleteAccount(): Response<MessageResponse>

    // --- Expenses ---
    @POST("expenses/create")
    async fun createExpense(@Body request: ExpenseCreateRequest): Response<MessageResponse>

    @GET("expenses/get")
    async fun getAllExpenses(): Response<List<ExpenseItem>>

    @GET("expenses/get/{id}")
    async fun getExpense(@Path("id") id: Int): Response<ExpenseItem>

    @PUT("expenses/edit/{id}")
    async fun editExpense(
        @Path("id") id: Int, 
        @Body request: ExpenseCreateRequest
    ): Response<Map<String, Any>>

    @DELETE("expenses/dlt/{id}")
    async fun deleteExpense(@Path("id") id: Int): Response<MessageResponse>

    // --- Budget ---
    @POST("budget/")
    async fun setBudget(@Body request: BudgetRequest): Response<BudgetItem>

    // --- Dashboard ---
    @GET("dashboard")
    async fun getDashboard(
        @Query("range") range: String,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null
    ): Response<DashboardResponse>

    // --- Chat & Assistant ---
    @POST("chat/message")
    async fun sendChatMessage(@Body request: ChatMessageRequest): Response<ChatMessageResponse>

    @GET("chat/history")
    async fun getChatHistory(): Response<List<ChatHistoryItem>>

    @GET("chat/suggestions")
    async fun getChatSuggestions(@Query("q") query: String): Response<ChatSuggestionsResponse>

    @DELETE("chat/clear")
    async fun clearChat(): Response<MessageResponse>
}
```

---

### 2. OkHttp Client with Auth Interceptor & Cookie Management

To keep the user authenticated and support automatic token refresh:

```kotlin
package com.smartexp.data.network

import android.content.Context
import com.smartexp.data.api.SmartExpApi
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object NetworkClient {

    // Set according to environment (10.0.2.2:8000 for Android Emulator)
    private const val BASE_URL = "http://10.0.2.2:8000/"

    // In-memory or EncryptedSharedPreferences token holder
    var accessToken: String? = null

    // Cookie storage for refresh_token cookie
    private val cookieStore = HashMap<String, MutableList<Cookie>>()

    private val cookieJar = object : CookieJar {
        override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
            cookieStore[url.host] = cookies.toMutableList()
        }

        override fun loadForRequest(url: HttpUrl): List<Cookie> {
            return cookieStore[url.host] ?: emptyList()
        }
    }

    private val authInterceptor = Interceptor { chain ->
        val original = chain.request()
        val requestBuilder = original.newBuilder()

        accessToken?.let { token ->
            requestBuilder.header("Authorization", "Bearer $token")
        }

        chain.proceed(requestBuilder.build())
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    val okHttpClient = OkHttpClient.Builder()
        .cookieJar(cookieJar)
        .addInterceptor(authInterceptor)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    val api: SmartExpApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SmartExpApi::class.java)
    }
}
```

---

## 8. UI Screens & Suggested Android Architecture

For a modern Android experience, build with **Jetpack Compose**, **Kotlin Coroutines / Flow**, and **MVVM / Clean Architecture**:

### Recommended Screens:

1. **Authentication Screens:**
   - `LoginScreen`: Email, Password, "Remember Me", Login button.
   - `RegisterScreen`: Name, Email, Password validation (min 8 chars).
   - `OnboardingScreen`: Guided intro screens when `has_onboarded == false`.

2. **Dashboard / Home Screen (`/dashboard`):**
   - **Health Score Card**: Visual circular gauge displaying `healthScore` (0-100) and `healthStatus` ("Financially Strong", "Stable", etc.).
   - **Summary Cards**: Total Spent, Remaining Budget, Monthly Savings, Daily Avg.
   - **Spending Trends Chart**: Line/Bar chart using `trends.labels` and `trends.values` (using MPAndroidChart or Vico).
   - **Category Distribution**: Donut/Pie chart for `categories`.
   - **Smart Insights Carousel**: Banner cards displaying tips from `insights`.

3. **Expenses Screen (`/expenses`):**
   - Floating Action Button (+) to quickly add an expense.
   - List of expenses with swipe-to-edit and swipe-to-delete.
   - Category badges (Food, Transport, Bills, Shopping, etc.).

4. **AI Assistant Chat Screen (`/chat`):**
   - Messaging UI with speech-to-text / text input.
   - Suggestion chips above the keyboard populated from `/chat/suggestions?q=...`.
   - Native cards embedded into chat bubbles when the bot returns tabular expense data.

5. **Profile & Settings (`/user`):**
   - Avatar image loader (using **Coil**: `AsyncImage(model = user.profileImage)`).
   - Photo picker for profile upload via `PUT /user/profile`.
   - Budget threshold settings (`POST /budget/`).
   - Change Password dialog.
   - Logout & Delete Account button.

---

### 📦 Recommended Android Gradle Dependencies

Add to your Android app's `build.gradle.kts`:

```kotlin
dependencies {
    // Retrofit & Networking
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Image Loading (Cloudinary Avatars)
    implementation("io.coil-kt:coil-compose:2.6.0")

    // Secure Credential Storage
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // Charts for Analytics (Vico or MPAndroidChart)
    implementation("com.patrykandpatrick.vico:compose-m3:2.0.0-alpha.25")

    // Jetpack Navigation & ViewModel
    implementation("androidx.navigation:navigation-compose:2.8.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
}
```

---

*Generated for the SmartExp Backend repository.*

