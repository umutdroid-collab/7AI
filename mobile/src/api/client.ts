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

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.";
  }
  return "Beklenmeyen bir hata oluştu.";
}
