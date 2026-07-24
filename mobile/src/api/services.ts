import { Platform } from "react-native";
import { api } from "./client";
import {
  ChatResponse,
  CheckIn,
  ClinicalDocument,
  Hospital,
  Invoice,
  Notification,
  Product,
  SalesTarget,
  StockItem,
  StockMovement,
  User,
} from "../types";

// Web'de tarayıcının yerleşik FormData'sı { uri, name, type } şeklini anlamaz,
// gerçek bir Blob/File bekler; bu yüzden web'de seçici sonucundaki `file`
// alanı (expo-document-picker / expo-image-picker web implementasyonunda
// mevcuttur) doğrudan eklenir. Native'de ise React Native'in fetch polyfill'i
// { uri, name, type } şeklini bekler.
function filePart(fileUri: string, fileName: string, mimeType: string, webFile?: File | Blob | null) {
  if (Platform.OS === "web" && webFile) {
    return webFile;
  }
  return { uri: fileUri, name: fileName, type: mimeType } as any;
}

function pdfFormData(fileUri: string, fileName: string, webFile?: File | Blob | null): FormData {
  const form = new FormData();
  form.append("file", filePart(fileUri, fileName, "application/pdf", webFile), fileName);
  return form;
}

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

export async function changePassword(currentPassword: string, newPassword: string) {
  const { data } = await api.post<User>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}

export async function fetchUsers() {
  const { data } = await api.get<User[]>("/auth/users");
  return data;
}

export async function createUser(payload: {
  full_name: string;
  email: string;
  password: string;
  role: "admin" | "employee";
}) {
  const { data } = await api.post<User>("/auth/users", payload);
  return data;
}

export async function setUserActive(userId: number, isActive: boolean) {
  const { data } = await api.patch<User>(`/auth/users/${userId}/active`, { is_active: isActive });
  return data;
}

// --- Hospitals & products ---

export async function fetchHospitals() {
  const { data } = await api.get<Hospital[]>("/hospitals");
  return data;
}

export async function createHospital(payload: {
  name: string;
  city?: string;
  address?: string;
  contact_person?: string;
  contact_phone?: string;
}) {
  const { data } = await api.post<Hospital>("/hospitals", payload);
  return data;
}

export async function updateHospital(
  id: number,
  payload: {
    name: string;
    city?: string;
    address?: string;
    contact_person?: string;
    contact_phone?: string;
  }
) {
  const { data } = await api.put<Hospital>(`/hospitals/${id}`, payload);
  return data;
}

export async function deleteHospital(id: number) {
  await api.delete(`/hospitals/${id}`);
}

export async function fetchProducts(q?: string) {
  const { data } = await api.get<Product[]>("/products", { params: { q } });
  return data;
}

interface ProductPayload {
  name: string;
  reference_no: string;
  ubb_no?: string;
  sut_kodu?: string;
  manufacturer?: string;
  unit?: string;
  notes?: string;
}

export async function createProduct(payload: ProductPayload) {
  const { data } = await api.post<Product>("/products", payload);
  return data;
}

export async function updateProduct(id: number, payload: ProductPayload) {
  const { data } = await api.put<Product>(`/products/${id}`, payload);
  return data;
}

export async function deleteProduct(id: number) {
  await api.delete(`/products/${id}`);
}

export async function bulkDeleteProducts(ids: number[]) {
  const { data } = await api.post<{ deleted: number; errors: { id: number; message: string }[] }>(
    "/products/bulk-delete",
    { ids }
  );
  return data;
}

// --- Stock ---

export async function fetchStock(params: {
  hospital_id?: number;
  carried_by_user_id?: number;
  q?: string;
  expiring_within_days?: number;
  status?: StockItem["status"];
  include_used?: boolean;
}) {
  const { data } = await api.get<StockItem[]>("/stock", { params });
  return data;
}

export async function fetchStockHistory(stockItemId: number) {
  const { data } = await api.get<StockMovement[]>(`/stock/${stockItemId}/history`);
  return data;
}

export async function transferStockItem(
  stockItemId: number,
  toHospitalId: number | null,
  note?: string,
  toVehicle?: boolean
) {
  const { data } = await api.post<StockItem>(`/stock/${stockItemId}/transfer`, {
    to_hospital_id: toHospitalId,
    to_vehicle: !!toVehicle,
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

export async function deleteStockItem(stockItemId: number) {
  await api.delete(`/stock/${stockItemId}`);
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

export async function uploadInvoicePdf(fileUri: string, fileName: string, webFile?: File | Blob | null) {
  const { data } = await api.post<Invoice>("/invoices/upload", pdfFormData(fileUri, fileName, webFile), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchInvoice(invoiceId: number) {
  const { data } = await api.get<Invoice>(`/invoices/${invoiceId}`);
  return data;
}

export function invoicePdfUrl(invoiceId: number) {
  return `/invoices/${invoiceId}/pdf`;
}

export async function updateInvoiceStatus(invoiceId: number, status: Invoice["status"]) {
  const { data } = await api.patch<Invoice>(`/invoices/${invoiceId}`, { status });
  return data;
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

export async function fetchClinicalDocuments() {
  const { data } = await api.get<ClinicalDocument[]>("/assistant/documents");
  return data;
}

export async function uploadClinicalDocument(fileUri: string, fileName: string, webFile?: File | Blob | null) {
  const { data } = await api.post<ClinicalDocument>(
    "/assistant/documents/upload",
    pdfFormData(fileUri, fileName, webFile),
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

// --- Check-ins (employee tracking) ---

export async function createCheckIn(
  hospitalId: number,
  photoUri: string,
  comment?: string,
  webFile?: File | Blob | null
) {
  const form = new FormData();
  form.append("hospital_id", String(hospitalId));
  if (comment) form.append("comment", comment);
  form.append("photo", filePart(photoUri, "checkin.jpg", "image/jpeg", webFile), "checkin.jpg");
  const { data } = await api.post<CheckIn>("/checkins", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchCheckIns(params?: { user_id?: number; hospital_id?: number; day?: string }) {
  const { data } = await api.get<CheckIn[]>("/checkins", { params });
  return data;
}

export function checkinPhotoUrl(id: number) {
  return `/checkins/${id}/photo`;
}

export async function updateCheckInComment(id: number, comment: string | null) {
  const { data } = await api.patch<CheckIn>(`/checkins/${id}`, { comment });
  return data;
}

export async function deleteCheckIn(id: number) {
  await api.delete(`/checkins/${id}`);
}

// --- Bulk uploads (admin) ---

export interface BulkUploadResult {
  created: number;
  skipped?: number;
  errors: any[];
}

function csvFormData(fileUri: string, fileName: string, webFile?: File | Blob | null): FormData {
  const form = new FormData();
  form.append("file", filePart(fileUri, fileName, "text/csv", webFile), fileName);
  return form;
}

export async function bulkUploadHospitals(fileUri: string, fileName: string, webFile?: File | Blob | null) {
  const { data } = await api.post<BulkUploadResult>(
    "/hospitals/bulk-upload",
    csvFormData(fileUri, fileName, webFile),
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

export async function bulkUploadProducts(fileUri: string, fileName: string, webFile?: File | Blob | null) {
  const { data } = await api.post<BulkUploadResult>(
    "/products/bulk-upload",
    csvFormData(fileUri, fileName, webFile),
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return data;
}

export async function bulkUploadStock(fileUri: string, fileName: string, webFile?: File | Blob | null) {
  const { data } = await api.post<BulkUploadResult>("/stock/bulk-upload", csvFormData(fileUri, fileName, webFile), {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function bulkUploadInvoices(files: { uri: string; name: string; webFile?: File | Blob | null }[]) {
  const form = new FormData();
  for (const file of files) {
    form.append("files", filePart(file.uri, file.name, "application/pdf", file.webFile), file.name);
  }
  const { data } = await api.post<{ created: number; errors: any[] }>("/invoices/bulk-upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

// --- Sales targets (Personel Takip) ---

export async function fetchSalesTargets() {
  const { data } = await api.get<SalesTarget[]>("/targets");
  return data;
}

export async function createSalesTarget(payload: {
  product_id: number;
  assigned_user_id?: number | null;
  target_quantity: number;
  period_start: string;
  period_end: string;
  note?: string;
}) {
  const { data } = await api.post<SalesTarget>("/targets", payload);
  return data;
}

export async function deleteSalesTarget(id: number) {
  await api.delete(`/targets/${id}`);
}
