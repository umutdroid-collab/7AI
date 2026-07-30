from datetime import date, datetime

from pydantic import BaseModel, EmailStr, model_validator

from app.models import InvoiceStatus, MovementType, StockItemStatus, UserRole


# --- Auth ---

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.EMPLOYEE


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    email_notifications_enabled: bool = True

    class Config:
        from_attributes = True


class EmailPreferenceUpdate(BaseModel):
    email_notifications_enabled: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserActiveUpdate(BaseModel):
    is_active: bool


# --- Hospitals ---

class HospitalCreate(BaseModel):
    name: str
    city: str | None = None
    address: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None


class HospitalOut(HospitalCreate):
    id: int

    class Config:
        from_attributes = True


# --- Products ---

class ProductCreate(BaseModel):
    name: str
    reference_no: str
    ubb_no: str | None = None
    sut_kodu: str | None = None
    manufacturer: str | None = None
    unit: str | None = None
    notes: str | None = None


class ProductOut(ProductCreate):
    id: int

    class Config:
        from_attributes = True


class ProductBulkDelete(BaseModel):
    ids: list[int]


# --- Stock items ---

class StockItemCreate(BaseModel):
    product_id: int
    lot_no: str
    serial_no: str | None = None
    skt: date | None = None  # bilinmiyorsa boş bırakılabilir
    quantity: int = 1
    hospital_id: int | None = None  # None = depoda


class StockItemOut(BaseModel):
    id: int
    product: ProductOut
    lot_no: str
    serial_no: str | None
    skt: date | None
    quantity: int
    status: StockItemStatus
    hospital: HospitalOut | None
    carried_by: UserOut | None
    created_at: datetime
    updated_at: datetime
    days_to_expiry: int | None = None

    class Config:
        from_attributes = True


class StockTransferRequest(BaseModel):
    to_hospital_id: int | None = None  # None = depoya iade (to_vehicle false ise)
    to_vehicle: bool = False  # true ise ürünü işlemi yapan çalışanın aracına alır
    note: str | None = None


class StockMovementOut(BaseModel):
    id: int
    movement_type: MovementType
    from_hospital_id: int | None
    to_hospital_id: int | None
    to_vehicle_user_id: int | None
    moved_by_user_id: int | None
    moved_at: datetime
    note: str | None

    class Config:
        from_attributes = True


# --- Invoices ---

class InvoiceOut(BaseModel):
    id: int
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    amount: float | None
    currency: str
    counterparty: str | None
    source_filename: str
    status: InvoiceStatus
    parse_confidence: float
    days_to_due: int | None = None

    class Config:
        from_attributes = True


class InvoiceUpdate(BaseModel):
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    amount: float | None = None
    currency: str | None = None
    counterparty: str | None = None
    status: InvoiceStatus | None = None


# --- Notifications ---

class NotificationOut(BaseModel):
    id: int
    invoice_id: int | None
    stock_item_id: int | None
    title: str
    message: str
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True


# --- Check-ins ---

class CheckInOut(BaseModel):
    id: int
    user: UserOut
    hospital: HospitalOut
    comment: str | None
    latitude: float | None
    longitude: float | None
    checked_in_at: datetime

    class Config:
        from_attributes = True


class CheckInUpdate(BaseModel):
    comment: str | None = None


# --- Assistant ---

class ChatRequest(BaseModel):
    question: str


class SourceOut(BaseModel):
    type: str  # "document" | "pubmed"
    title: str
    detail: str | None = None
    url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    was_answered: bool


class ClinicalDocumentOut(BaseModel):
    id: int
    filename: str
    title: str | None
    num_chunks: int
    file_size: int = 0
    indexed_at: datetime

    class Config:
        from_attributes = True


# --- Sales targets (Personel Takip) ---

class SalesTargetCreate(BaseModel):
    # Ürüne bağlı hedeflerde product_id, serbest ("manuel") hedeflerde title
    # verilir; ilerleme manuel hedeflerde elle girilir.
    product_id: int | None = None
    title: str | None = None
    assigned_user_id: int | None = None  # None = tüm ekip için ortak hedef
    target_quantity: int
    period_start: date
    period_end: date
    note: str | None = None

    @model_validator(mode="after")
    def require_product_or_title(self):
        if self.product_id is None and not (self.title or "").strip():
            raise ValueError("Ürün seçin ya da hedef için bir başlık yazın")
        return self


class SalesTargetUpdate(BaseModel):
    title: str | None = None
    assigned_user_id: int | None = None
    target_quantity: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    note: str | None = None


class SalesTargetProgressAdjust(BaseModel):
    delta: int  # +1 / -1 gibi; toplam ilerleme negatife düşürülmez


class SalesTargetContributor(BaseModel):
    user_id: int
    full_name: str
    quantity: int


class SalesTargetOut(BaseModel):
    id: int
    product: ProductOut | None
    title: str | None
    manual_progress: int = 0
    assigned_user: UserOut | None
    target_quantity: int
    period_start: date
    period_end: date
    note: str | None
    created_at: datetime
    progress: int = 0
    contributors: list[SalesTargetContributor] = []

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    user_name: str
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    created_at: datetime

    class Config:
        from_attributes = True
