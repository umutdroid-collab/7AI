import { api } from "./client";
import {
  ChatResponse,
  Hospital,
  Invoice,
  Notification,
  Product,
  StockItem,
  StockMovement,
  User,
} from "../types";

// --- Auth ---

export async function login(email: string, password: string) {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const { data } = await api.post<{ access_token: string; user: User }>("/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function fetchMe() {
  const { data } = await api.get<User>("/auth/me");
  return data;
}

// --- Hospitals & products ---

export async function fetchHospitals() {
  const { data } = await api.get<Hospital[]>("/hospitals");
  return data;
}

export async function fetchProducts(q?: string) {
  const { data } = await api.get<Product[]>("/products", { params: { q } });
  return data;
}

// --- Stock ---

export async function fetchStock(params: {
  hospital_id?: number;
  q?: string;
  expiring_within_days?: number;
}) {
  const { data } = await api.get<StockItem[]>("/stock", { params });
  return data;
}

export async function fetchStockHistory(stockItemId: number) {
  const { data } = await api.get<StockMovement[]>(`/stock/${stockItemId}/history`);
  return data;
}

export async function transferStockItem(stockItemId: number, toHospitalId: number | null, note?: string) {
  const { data } = await api.post<StockItem>(`/stock/${stockItemId}/transfer`, {
    to_hospital_id: toHospitalId,
    note,
  });
  return data;
}

export async function markStockItemUsed(stockItemId: number, note?: string) {
  const { data } = await api.post<StockItem>(`/stock/${stockItemId}/mark-used`, null, {
    params: { note },
  });
  return data;
}

export async function createStockItem(payload: {
  product_id: number;
  lot_no: string;
  serial_no?: string;
  skt: string;
  quantity?: number;
  hospital_id?: number | null;
}) {
  const { data } = await api.post<StockItem>("/stock", payload);
  return data;
}

// --- Invoices ---

export async function fetchInvoices(params?: { upcoming_only?: boolean; overdue_only?: boolean; q?: string }) {
  const { data } = await api.get<Invoice[]>("/invoices", { params });
  return data;
}

export async function fetchInvoice(invoiceId: number) {
  const { data } = await api.get<Invoice>(`/invoices/${invoiceId}`);
  return data;
}

export function invoicePdfUrl(invoiceId: number) {
  return `/invoices/${invoiceId}/pdf`;
}

// --- Notifications ---

export async function fetchNotifications(unreadOnly = false) {
  const { data } = await api.get<Notification[]>("/notifications", {
    params: { unread_only: unreadOnly },
  });
  return data;
}

export async function markNotificationRead(id: number) {
  const { data } = await api.post<Notification>(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead() {
  await api.post("/notifications/read-all");
}

// --- Assistant ---

export async function askAssistant(question: string) {
  const { data } = await api.post<ChatResponse>("/assistant/chat", { question });
  return data;
}
