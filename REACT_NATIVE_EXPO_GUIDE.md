# 📱 SmartExp Backend Integration Guide for React Native (Expo)

This guide provides everything you need to build and connect a **React Native (Expo)** frontend to the **SmartExp FastAPI Backend**.

---

## 📑 Table of Contents
1. [Backend Setup & Network Configuration](#1-backend-setup--network-configuration)
2. [Expo Project Setup & Recommended Packages](#2-expo-project-setup--recommended-packages)
3. [Environment Configuration & Base URLs](#3-environment-configuration--base-urls)
4. [Authentication Flow & Secure Storage](#4-authentication-flow--secure-storage)
5. [Complete TypeScript Data Models](#5-complete-typescript-data-models)
6. [Axios API Client & Auto-Refresh Interceptor](#6-axios-api-client--auto-refresh-interceptor)
7. [API Service Functions](#7-api-service-functions)
8. [Handling Profile Image Uploads (Cloudinary / Multipart)](#8-handling-profile-image-uploads-cloudinary--multipart)
9. [React Native Screen Blueprints](#9-react-native-screen-blueprints)
10. [Helpful Backend Tweaks for Mobile Apps](#10-helpful-backend-tweaks-for-mobile-apps)

---

## 1. Backend Setup & Network Configuration

When developing with React Native / Expo, your physical phone or simulator needs to communicate with your FastAPI backend.

### ⚠️ Critical: Bind FastAPI to `0.0.0.0`
By default, Uvicorn binds to `127.0.0.1` (localhost), which means a physical mobile device running Expo Go on your Wi-Fi cannot connect.

Start the backend with `--host 0.0.0.0`:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Find Your Computer's LAN IP
In PowerShell on Windows:
```powershell
ipconfig
```
Look for **IPv4 Address** under your Wi-Fi or Ethernet adapter (e.g. `192.168.1.15`).

---

## 2. Expo Project Setup & Recommended Packages

If starting a new Expo app:
```bash
npx create-expo-app@latest smartexp-mobile --template blank-typescript
cd smartexp-mobile
```

### Recommended Packages:
```bash
# Secure Token Storage
npx expo install expo-secure-store

# Networking
npm install axios

# Image Picker (for Profile Avatar)
npx expo install expo-image-picker

# Vector Icons & UI Helpers
npm install lucide-react-native react-native-svg

# Charts (for Dashboard & Trends)
npm install react-native-gifted-charts

# Navigation (if using React Navigation)
npm install @react-navigation/native @react-navigation/native-stack
npx expo install react-native-screens react-native-safe-area-context
```

---

## 3. Environment Configuration & Base URLs

React Native resolves URLs differently depending on whether you run in an iOS simulator, an Android emulator, or on a physical device with Expo Go:

| Environment | Base URL |
|---|---|
| **Physical Phone (Expo Go)** | `http://<YOUR_LAN_IP>:8000` (e.g. `http://192.168.1.15:8000`) |
| **Android Emulator** | `http://10.0.2.2:8000` |
| **iOS Simulator** | `http://localhost:8000` |
| **Production Server** | `https://api.yourdomain.com` |

### Dynamic Base URL Utility (`src/config/api.ts`)

Create `src/config/api.ts` to automatically detect your host computer's IP in development:

```typescript
import Constants from 'expo-constants';
import { Platform } from 'react-native';

const getBaseUrl = (): string => {
  // If in production, return deployed URL
  if (!__DEV__) {
    return 'https://api.yourdomain.com';
  }

  // If using Expo Go on physical device or simulator
  const debuggerHost = Constants.expoConfig?.hostUri;
  const localhost = debuggerHost?.split(':')[0];

  if (localhost) {
    return `http://${localhost}:8000`;
  }

  // Fallbacks for direct emulators
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:8000';
  }
  
  return 'http://localhost:8000';
};

export const API_BASE_URL = getBaseUrl();
```

---

## 4. Authentication Flow & Secure Storage

### Token Management with `expo-secure-store`

FastAPI uses JWT:
- **Access Token:** Lasts 15 minutes. Included in requests as `Authorization: Bearer <token>`.
- **Refresh Token:** Lasts 7 days. Used to renew expired access tokens via `/auth/refresh`.

Create `src/utils/storage.ts`:

```typescript
import * as SecureStore from 'expo-secure-store';

const ACCESS_TOKEN_KEY = 'smartexp_access_token';
const REFRESH_TOKEN_KEY = 'smartexp_refresh_token';

export const saveTokens = async (accessToken: string, refreshToken?: string) => {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken);
  }
};

export const getAccessToken = async (): Promise<string | null> => {
  return await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
};

export const getRefreshToken = async (): Promise<string | null> => {
  return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
};

export const clearTokens = async () => {
  await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
  await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
};
```

---

## 5. Complete TypeScript Data Models

Create `src/types/api.ts`:

```typescript
// --- Auth Types ---
export interface RegisterPayload {
  name: string;
  email: string;
  password: string; // min 8 characters
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token?: string;
}

// --- User Profile ---
export interface UserProfile {
  name: string;
  email: string;
  profile_image: string | null;
  has_onboarded: boolean;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
}

// --- Expense Types ---
export interface ExpenseCreatePayload {
  title: string;
  amount: number;
  category: string;
}

export interface ExpenseItem {
  exp_id: number;
  title: string;
  amount: number;
  category: string;
  created_at: string;
  user_id: number;
}

// --- Budget Types ---
export interface BudgetPayload {
  category?: string | null; // null for overall budget
  amount: number;
  month: number; // 1 - 12
  year: number; // e.g. 2026
}

export interface BudgetItem {
  budget_id: number;
  category: string | null;
  amount: number;
  month: number;
  year: number;
}

// --- Dashboard Types ---
export interface HealthBreakdownItem {
  score: number | null;
  details: string | null;
}

export interface DashboardSummary {
  totalSpent: number;
  totalBudget: number;
  avgDaily: number;
  remainingBudget: number;
  budgetExceeded: boolean;
  changePercent: number;
  income: number;
  incomeMissing: boolean;
  savings: number;
  healthScore: number | null;
  healthStatus: string; // "Financially Strong", "Stable", "Vulnerable", "At Risk", "Critical"
  healthBreakdown: {
    savings?: HealthBreakdownItem;
    expense?: HealthBreakdownItem;
    stability?: HealthBreakdownItem;
    budget?: HealthBreakdownItem;
    income_consistency?: HealthBreakdownItem;
  };
  message: string | null;
}

export interface CategorySpend {
  name: string;
  amount: number;
}

export interface DashboardTrends {
  labels: string[]; // ["01 Sep", "02 Sep", ...]
  values: number[]; // [150.0, 42.5, ...]
}

export interface DashboardBudgetProgress {
  category: string; // "overall" or category name
  limit: number;
  used: number;
  percent: number;
}

export interface DashboardResponse {
  summary: DashboardSummary;
  categories: CategorySpend[];
  trends: DashboardTrends;
  insights: string[];
  budgets: DashboardBudgetProgress[];
}

// --- AI Chat Assistant Types ---
export interface ChatMessagePayload {
  message: string;
}

export interface ChatMessageResponse {
  response: string;
  data_updated: boolean;
  data?: any;
}

export interface ChatHistoryItem {
  sender: 'user' | 'bot';
  text: string;
  time: string;
  data?: any;
}

export interface ChatSuggestionsResponse {
  suggestions: string[];
}
```

---

## 6. Axios API Client & Auto-Refresh Interceptor

Create `src/api/client.ts`:

```typescript
import axios from 'axios';
import { API_BASE_URL } from '../config/api';
import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from '../utils/storage';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Sends cookies if supported by backend
});

// Request Interceptor: Attach Bearer token
apiClient.interceptors.request.use(
  async (config) => {
    const token = await getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Auto refresh on 401 Unauthorized
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Skip if login/register failed or request already retried
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = await getRefreshToken();
        
        // Call refresh endpoint
        const res = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          {},
          {
            withCredentials: true,
            headers: refreshToken ? { Cookie: `refresh_token=${refreshToken}` } : {},
          }
        );

        const newAccessToken = res.data.access_token;
        await saveTokens(newAccessToken);

        apiClient.defaults.headers.common['Authorization'] = `Bearer ${newAccessToken}`;
        processQueue(null, newAccessToken);

        originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        await clearTokens();
        // Redirect to Login screen via navigation ref or event emitter
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## 7. API Service Functions

Create modular service files under `src/api/`:

### `src/api/authService.ts`
```typescript
import apiClient from './client';
import { RegisterPayload, LoginPayload, AuthResponse } from '../types/api';
import { saveTokens, clearTokens } from '../utils/storage';

export const registerUser = async (data: RegisterPayload) => {
  const res = await apiClient.post<{ message: string }>('/auth/register', data);
  return res.data;
};

export const loginUser = async (data: LoginPayload): Promise<AuthResponse> => {
  const res = await apiClient.post<AuthResponse>('/auth/login', data);
  await saveTokens(res.data.access_token);
  return res.data;
};

export const logoutUser = async () => {
  await clearTokens();
};
```

### `src/api/expenseService.ts`
```typescript
import apiClient from './client';
import { ExpenseCreatePayload, ExpenseItem } from '../types/api';

export const getExpenses = async (): Promise<ExpenseItem[]> => {
  const res = await apiClient.get<ExpenseItem[]>('/expenses/get');
  return res.data;
};

export const getExpenseById = async (id: number): Promise<ExpenseItem> => {
  const res = await apiClient.get<ExpenseItem>(`/expenses/get/${id}`);
  return res.data;
};

export const createExpense = async (data: ExpenseCreatePayload) => {
  const res = await apiClient.post<{ messege: string }>('/expenses/create', data);
  return res.data;
};

export const updateExpense = async (id: number, data: ExpenseCreatePayload) => {
  const res = await apiClient.put<{ message: string; expense: ExpenseItem }>(
    `/expenses/edit/${id}`,
    data
  );
  return res.data;
};

export const deleteExpense = async (id: number) => {
  const res = await apiClient.delete<{ message: string }>(`/expenses/dlt/${id}`);
  return res.data;
};
```

### `src/api/dashboardService.ts`
```typescript
import apiClient from './client';
import { DashboardResponse } from '../types/api';

export const getDashboard = async (
  range: 'week' | 'month' | 'custom' = 'month',
  startDate?: string,
  endDate?: string
): Promise<DashboardResponse> => {
  const params: Record<string, string> = { range };
  if (startDate) params.start_date = startDate;
  if (endDate) params.end_date = endDate;

  const res = await apiClient.get<DashboardResponse>('/dashboard', { params });
  return res.data;
};
```

### `src/api/budgetService.ts`
```typescript
import apiClient from './client';
import { BudgetPayload, BudgetItem } from '../types/api';

export const setBudget = async (data: BudgetPayload): Promise<BudgetItem> => {
  const res = await apiClient.post<BudgetItem>('/budget/', data);
  return res.data;
};
```

### `src/api/chatService.ts`
```typescript
import apiClient from './client';
import {
  ChatMessagePayload,
  ChatMessageResponse,
  ChatHistoryItem,
  ChatSuggestionsResponse,
} from '../types/api';

export const sendChatMessage = async (
  message: string
): Promise<ChatMessageResponse> => {
  const res = await apiClient.post<ChatMessageResponse>('/chat/message', { message });
  return res.data;
};

export const getChatHistory = async (): Promise<ChatHistoryItem[]> => {
  const res = await apiClient.get<ChatHistoryItem[]>('/chat/history');
  return res.data;
};

export const getChatSuggestions = async (query: string): Promise<string[]> => {
  const res = await apiClient.get<ChatSuggestionsResponse>('/chat/suggestions', {
    params: { q: query },
  });
  return res.data.suggestions;
};

export const clearChatHistory = async () => {
  const res = await apiClient.delete<{ message: string }>('/chat/clear');
  return res.data;
};
```

---

## 8. Handling Profile Image Uploads (Cloudinary / Multipart)

The backend route `PUT /user/profile` expects `multipart/form-data` with optional `name`, `email`, and `profile_image` (file).

Here is how to pick and upload an image using **Expo Image Picker**:

### `src/api/userService.ts`
```typescript
import apiClient from './client';
import { UserProfile, ChangePasswordPayload } from '../types/api';
import * as ImagePicker from 'expo-image-picker';

export const getCurrentUser = async (): Promise<UserProfile> => {
  const res = await apiClient.get<UserProfile>('/user/me');
  return res.data;
};

export const updateProfile = async (params: {
  name?: string;
  email?: string;
  imageUri?: string;
}): Promise<UserProfile> => {
  const formData = new FormData();

  if (params.name) formData.append('name', params.name);
  if (params.email) formData.append('email', params.email);

  if (params.imageUri) {
    const filename = params.imageUri.split('/').pop() || 'avatar.jpg';
    const match = /\.(\w+)$/.exec(filename);
    const type = match ? `image/${match[1]}` : `image/jpeg`;

    formData.append('profile_image', {
      uri: params.imageUri,
      name: filename,
      type: type,
    } as any);
  }

  const res = await apiClient.put<UserProfile>('/user/profile', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return res.data;
};

export const changePassword = async (data: ChangePasswordPayload) => {
  const res = await apiClient.post<{ message: string }>('/user/change-password', data);
  return res.data;
};

export const completeOnboarding = async () => {
  const res = await apiClient.put<{ message: string; has_onboarded: boolean }>('/user/onboarded');
  return res.data;
};

export const deleteAccount = async () => {
  const res = await apiClient.delete<{ message: string }>('/user/me');
  return res.data;
};
```

---

## 9. React Native Screen Blueprints

### 1. Dashboard Screen
- **Health Score Widget:** Render circular gauge or colored badge based on `summary.healthScore` and `summary.healthStatus`:
  - `85-100`: Green ("Financially Strong")
  - `70-84`: Blue/Teal ("Stable")
  - `55-69`: Yellow/Orange ("Vulnerable")
  - `< 55`: Red ("At Risk" / "Critical")
- **Bar/Line Chart:** Use `react-native-gifted-charts` passing `trends.labels` and `trends.values`.
- **Budgets Progress:** Horizontal progress bars showing `percent` and remaining amounts.
- **Insights Carousel:** Cards mapping over `insights`.

### 2. Smart AI Chat Assistant
- Chat bubble list showing `user` and `bot` messages from `getChatHistory()`.
- Top or bottom autocomplete suggestion bar querying `getChatSuggestions(input)` in real-time as the user types.
- Example prompts to suggest to user:
  - *"Spent ₹150 on coffee"*
  - *"Set food budget to 5000"*
  - *"My salary is 60000"*
  - *"Show my expenses this month"*

### 3. Expenses List Screen
- Pull-to-refresh connected to `getExpenses()`.
- Floating Action Button (+) to open an Add Expense modal.
- Swipe-to-delete connected to `deleteExpense(id)`.

---

## 10. Helpful Backend Tweaks for Mobile Apps

For standard mobile apps, working with `HttpOnly` cookies over non-HTTPS local networks can occasionally drop cookies.

### 💡 Recommendation for `app/auth.py`:
You can make your login endpoint also return `refresh_token` in the JSON response for native apps, while still keeping cookies for web apps:

In `app/auth.py` (`/login` route):
```python
# Before:
return {"access_token": access}

# Recommended (100% backward compatible, mobile friendly):
return {
    "access_token": access,
    "refresh_token": refresh
}
```

And in `/refresh` route, accept `refresh_token` from either cookie **OR** JSON body:
```python
from pydantic import BaseModel
class RefreshBody(BaseModel):
    refresh_token: str | None = None

@router.post("/refresh")
async def refresh_token(
    request: Request,
    body: RefreshBody = None,
    session: Session = Depends(get_session)
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token and body and body.refresh_token:
        refresh_token = body.refresh_token
    ...
```

This allows your React Native app to store both tokens in `expo-secure-store` and effortlessly refresh tokens!

---

*Generated for the SmartExp Backend repository.*

