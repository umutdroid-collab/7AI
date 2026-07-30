import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.database import Base

logger = logging.getLogger("migrations")


def _add_missing_columns(engine: Engine, inspector) -> None:
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
                    # server_default varsa DEFAULT'u da yaz: aksi halde mevcut
                    # satırlar NULL kalır ve örn. bir bool bayrak "kapalı" gibi
                    # davranır (yeni sütun eklenen tabloda sessiz veri hatası).
                    default_clause = ""
                    if column.server_default is not None:
                        default_sql = getattr(column.server_default, "arg", None)
                        if default_sql is not None:
                            default_clause = f" DEFAULT {default_sql}"
                    conn.execute(
                        text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_clause}')
                    )
                    logger.warning("Migrasyon: '%s' tablosuna '%s' sütunu eklendi", table.name, column.name)
                except Exception:
                    logger.exception(
                        "Migrasyon başarısız: '%s' tablosuna '%s' sütunu eklenemedi", table.name, column.name
                    )


def _columns_needing_relaxed_null(inspector, table) -> list[str]:
    """Veritabanında NOT NULL ama modelde artık isteğe bağlı olan sütunlar."""
    live = {col["name"]: col for col in inspector.get_columns(table.name)}
    relaxed = []
    for column in table.columns:
        existing = live.get(column.name)
        if not existing:
            continue
        if column.nullable and not existing["nullable"] and not column.primary_key:
            relaxed.append(column.name)
    return relaxed


def _rebuild_table(engine: Engine, table, reason: str) -> None:
    """Tabloyu modeldeki şemaya göre yeniden oluşturup veriyi taşır.

    SQLite ALTER COLUMN desteklemediği için, bir sütunun NOT NULL kısıtını
    kaldırmanın tek yolu tabloyu yeniden kurmak. Veri kaybını önlemek için
    eski tablo önce yeniden adlandırılır, veri kopyalandıktan sonra silinir;
    işlemin tamamı tek bir transaction içinde yapılır, ortasında bir hata
    olursa hiçbir değişiklik kalıcı olmaz.
    """
    old_name = f"{table.name}__migrasyon_yedegi"
    live_columns = {col["name"] for col in inspect(engine).get_columns(table.name)}
    shared = [c.name for c in table.columns if c.name in live_columns]
    column_list = ", ".join(f'"{c}"' for c in shared)

    logger.warning("Migrasyon: '%s' tablosu yeniden oluşturuluyor (%s)", table.name, reason)

    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(text(f'ALTER TABLE "{table.name}" RENAME TO "{old_name}"'))
        table.create(bind=conn)
        conn.execute(text(f'INSERT INTO "{table.name}" ({column_list}) SELECT {column_list} FROM "{old_name}"'))
        conn.execute(text(f'DROP TABLE "{old_name}"'))
        conn.execute(text("PRAGMA foreign_keys=ON"))

    logger.warning("Migrasyon: '%s' tablosu yeniden oluşturuldu", table.name)


def _relax_not_null_constraints(engine: Engine, inspector) -> None:
    if engine.dialect.name != "sqlite":
        return  # diğer veritabanlarında ALTER COLUMN doğrudan yapılabilir
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        relaxed = _columns_needing_relaxed_null(inspector, table)
        if not relaxed:
            continue
        try:
            _rebuild_table(engine, table, f"{', '.join(relaxed)} artık zorunlu değil")
        except Exception:
            logger.exception(
                "Migrasyon başarısız: '%s' tablosundaki NOT NULL kısıtı kaldırılamadı", table.name
            )


def run_startup_migrations(engine: Engine) -> None:
    """Base.metadata.create_all() sadece eksik TABLOLARI oluşturur; var olan bir
    tabloya sonradan eklenen SÜTUNLARI eklemez, kısıt değişikliklerini de
    uygulamaz. Bu proje Alembic gibi bir migrasyon aracı kullanmadığından,
    model değiştikçe üretimdeki veritabanı geride kalabilir ve 'no such column'
    ya da 'NOT NULL constraint failed' hatalarına yol açar. Bu fonksiyon her
    başlangıçta iki farkı kapatır: eksik sütunlar ve artık zorunlu olmaması
    gereken sütunlar."""
    inspector = inspect(engine)
    _add_missing_columns(engine, inspector)
    # Sütun eklendikten sonra şema değiştiği için inspector tazelenmeli.
    _relax_not_null_constraints(engine, inspect(engine))
