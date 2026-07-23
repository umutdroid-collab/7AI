export type UserRole = "admin" | "employee";

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface Hospital {
  id: number;
  name: string;
  city: string | null;
  address: string | null;
  contact_person: string | null;
  contact_phone: string | null;
}

export interface Product {
  id: number;
  name: string;
  reference_no: string;
  ubb_no: string | null;
  manufacturer: string | null;
  unit: string | null;
  notes: string | null;
}

export type StockItemStatus = "in_stock" | "at_hospital" | "in_vehicle" | "used" | "returned" | "expired";

export interface StockItem {
  id: number;
  product: Product;
  lot_no: string;
  serial_no: string | null;
  skt: string;
  quantity: number;
  status: StockItemStatus;
  hospital: Hospital | null;
  carried_by: User | null;
  created_at: string;
  updated_at: string;
  days_to_expiry: number | null;
}

export type MovementType = "dispatch" | "transfer" | "return" | "use" | "adjustment" | "vehicle_pickup";

export interface StockMovement {
  id: number;
  movement_type: MovementType;
  from_hospital_id: number | null;
  to_hospital_id: number | null;
  to_vehicle_user_id: number | null;
  moved_by_user_id: number | null;
  moved_at: string;
  note: string | null;
}

export type InvoiceStatus = "parsed" | "needs_review" | "paid" | "overdue" | "upcoming" | "open";

export interface Invoice {
  id: number;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  amount: number | null;
  currency: string;
  counterparty: string | null;
  source_filename: string;
  status: InvoiceStatus;
  parse_confidence: number;
  days_to_due: number | null;
}

export interface Notification {
  id: number;
  invoice_id: number | null;
  stock_item_id: number | null;
  title: string;
  message: string;
  created_at: string;
  is_read: boolean;
}

export interface ChatSource {
  type: "document" | "pubmed";
  title: string;
  detail: string | null;
  url: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  was_answered: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
}

export interface ClinicalDocument {
  id: number;
  filename: string;
  title: string | null;
  num_chunks: number;
  indexed_at: string;
}

export interface CheckIn {
  id: number;
  user: User;
  hospital: Hospital;
  comment: string | null;
  checked_in_at: string;
}
