from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# SQLite'ın kendi lower()'ı YALNIZCA ASCII harfleri küçültür; "Ü", "İ", "Ş"
# olduğu gibi kalır. SQLAlchemy `ilike` çağrısını `lower(sutun) LIKE lower(?)`
# olarak derlediğinden bunun sonucu şuydu: "düz" araması yalnızca Title-Case
# yazılmış ürünleri, "DÜZ" araması yalnızca BÜYÜK yazılmışları buluyordu
# (yerel ölçüm). Kullanıcı için bu "arama çalışmıyor" demek.
#
# Ek olarak diyakritikler de sadeleştiriliyor: saha ekibi telefondan
# çoğunlukla "duz vaskuler" diye yazıyor ve "Düz Vasküler"i bulmayı bekliyor.
# Bu, eşleşmeyi yalnızca genişletir - kaçan sonuç üretmez.
_TR_FOLD = str.maketrans(
    {
        "İ": "i", "I": "i", "ı": "i",
        "Ş": "s", "ş": "s",
        "Ğ": "g", "ğ": "g",
        "Ü": "u", "ü": "u",
        "Ö": "o", "ö": "o",
        "Ç": "c", "ç": "c",
    }
)


def turkish_fold(value):
    """Arama karşılaştırmaları için Türkçe duyarlı küçültme."""
    if value is None:
        return None
    return str(value).translate(_TR_FOLD).lower()


@event.listens_for(engine, "connect")
def _register_turkish_lower(dbapi_connection, _record):
    """SQLite'ın lower() fonksiyonunu Türkçe bilen sürümüyle değiştirir.

    Tek noktadan çözüm: `ilike` kullanan tüm aramalar (ürün, fatura, stok)
    bu fonksiyondan geçiyor, her sorguyu tek tek değiştirmeye gerek yok.
    SQL'de lower() yalnızca ilike tarafından üretiliyor, başka bir kullanımı
    yok - davranış değişikliği aramayla sınırlı.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    dbapi_connection.create_function("lower", 1, turkish_fold, deterministic=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
