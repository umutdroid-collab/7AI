import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database import Base

logger = logging.getLogger("migrations")


def run_startup_migrations(engine: Engine) -> None:
    """Base.metadata.create_all() sadece eksik TABLOLARI oluşturur, var olan bir
    tabloya sonradan eklenen SÜTUNLARI eklemez. Bu proje Alembic gibi bir migrasyon
    aracı kullanmadığından, model değiştikçe (örn. StockItem.carried_by_user_id gibi
    yeni bir alan eklendiğinde) üretimdeki veritabanı geride kalabilir ve
    'no such column' hatasına yol açar. Bu fonksiyon, her başlangıçta model ile
    gerçek şema arasındaki eksik sütunları bulup veri kaybı olmadan ekler."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                try:
                    col_type = column.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'))
                    logger.warning("Migrasyon: '%s' tablosuna '%s' sütunu eklendi", table.name, column.name)
                except Exception:
                    logger.exception(
                        "Migrasyon başarısız: '%s' tablosuna '%s' sütunu eklenemedi", table.name, column.name
                    )
