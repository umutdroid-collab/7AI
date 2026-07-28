import axios from "axios";
import Constants from "expo-constants";
import secureStorage from "../utils/secureStorage";

export const API_BASE_URL: string =
  (Constants.expoConfig?.extra?.apiBaseUrl as string) || "http://localhost:8000";

export const TOKEN_KEY = "7ai_access_token";

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use(async (config) => {
  const token = await secureStorage.getItemAsync(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Token süresi dolduğunda (8 saat) her istek 401 dönmeye başlar; kullanıcıya
// anlamsız "beklenmeyen hata"lar göstermek yerine oturumu kapatıp giriş
// ekranına yönlendiriyoruz. AuthContext açılışta buraya logout'unu kaydeder.
let onUnauthorized: (() => void) | null = null;

export function setOnUnauthorized(callback: () => void) {
  onUnauthorized = callback;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const isLoginRequest = axios.isAxiosError(error) && String(error.config?.url).includes("/auth/login");
    if (axios.isAxiosError(error) && error.response?.status === 401 && !isLoginRequest) {
      await secureStorage.deleteItemAsync(TOKEN_KEY);
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.";
  }
  return "Beklenmeyen bir hata oluştu.";
}
