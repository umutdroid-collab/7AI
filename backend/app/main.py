import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import assistant, auth, checkins, hospitals, invoices, notifications, products, sales_targets, stock
from app.seed import seed_default_admin
from app.services.migrations import run_startup_migrations
from app.services.invoice_watcher import start_invoice_watcher
from app.services.reminders import start_scheduler
from app.services.vector_store import reindex_all

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")

settings = get_settings()

_observer = None
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _observer, _scheduler

    Base.metadata.create_all(bind=engine)
    run_startup_migrations(engine)
    seed_default_admin()

    _observer = start_invoke_watcher_safe()
    _scheduler = start_scheduler()

    try:
        chunks = reindex_all()
        logger.info("Klinik doküman indeksleme tamamlandı: %d parça", chunks)
    except Exception:
        logger.exception("Başlangıçta klinik doküman indeksleme başarısız oldu")

    yield

    if _observer:
        _observer.stop()
        _observer.join()
    if _scheduler:
        _scheduler.shutdown()


def start_invoke_watcher_safe():
    try:
        return start_invoice_watcher()
    except Exception:
        logger.exception("Fatura klasörü izleyicisi başlatılamadı")
        return None


app = FastAPI(title="7AI Saha Uygulaması API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(hospitals.router)
app.include_router(products.router)
app.include_router(stock.router)
app.include_router(invoices.router)
app.include_router(checkins.router)
app.include_router(sales_targets.router)
app.include_router(notifications.router)
app.include_router(assistant.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "7AI backend"}


@app.get("/health")
def health():
    return {"status": "healthy"}
