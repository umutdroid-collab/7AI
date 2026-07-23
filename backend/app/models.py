import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class StockItemStatus(str, enum.Enum):
    IN_STOCK = "in_stock"       # depoda
    AT_HOSPITAL = "at_hospital"  # bir hastanede konsinye
    IN_VEHICLE = "in_vehicle"    # bir çalışanın aracında/üzerinde
    USED = "used"                # hastada kullanıldı / tüketildi
    RETURNED = "returned"        # depoya iade edildi
    EXPIRED = "expired"


class MovementType(str, enum.Enum):
    DISPATCH = "dispatch"    # depodan hastaneye ilk çıkış
    TRANSFER = "transfer"    # hastaneden hastaneye
    RETURN = "return"        # hastaneden depoya iade
    USE = "use"              # hastanede kullanıldı
    ADJUSTMENT = "adjustment"  # manuel düzeltme
    VEHICLE_PICKUP = "vehicle_pickup"  # bir çalışan aracına/üzerine aldı


class InvoiceStatus(str, enum.Enum):
    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"
    PAID = "paid"
    OVERDUE = "overdue"
    UPCOMING = "upcoming"
    OPEN = "open"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    stock_items: Mapped[list["StockItem"]] = relationship(back_populates="hospital")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    reference_no: Mapped[str] = mapped_column(String(100), index=True)   # ref numarası
    ubb_no: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)  # ÜBB numarası
    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock_items: Mapped[list["StockItem"]] = relationship(back_populates="product")


class StockItem(Base):
    """A single traceable consigned unit: one lot/serial/SKT combination."""

    __tablename__ = "stock_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    lot_no: Mapped[str] = mapped_column(String(100), index=True)
    serial_no: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    skt: Mapped[date] = mapped_column(Date)  # son kullanma tarihi
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[StockItemStatus] = mapped_column(Enum(StockItemStatus), default=StockItemStatus.IN_STOCK)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    carried_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="stock_items")
    hospital: Mapped["Hospital | None"] = relationship(back_populates="stock_items")
    carried_by: Mapped["User | None"] = relationship(foreign_keys=[carried_by_user_id])
    movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="stock_item", order_by="StockMovement.moved_at", cascade="all, delete-orphan"
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_items.id"))
    movement_type: Mapped[MovementType] = mapped_column(Enum(MovementType))
    from_hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    to_hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    to_vehicle_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    moved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock_item: Mapped["StockItem"] = relationship(back_populates="movements")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    counterparty: Mapped[str | None] = mapped_column(String(250), nullable=True)

    file_path: Mapped[str] = mapped_column(String(500))
    source_filename: Mapped[str] = mapped_column(String(300))
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.PARSED)
    parse_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    stock_item_id: Mapped[int | None] = mapped_column(ForeignKey("stock_items.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(300), unique=True)
    title: Mapped[str | None] = mapped_column(String(400), nullable=True)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    was_answered: Mapped[bool] = mapped_column(Boolean, default=True)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CheckIn(Base):
    """Bir çalışanın sabah hastaneye vardığında fotoğraf çekerek yaptığı giriş kaydı."""

    __tablename__ = "check_ins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"))
    photo_path: Mapped[str] = mapped_column(String(500))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
