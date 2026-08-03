from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/app.db"
    secret_key: str = "insecure-dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: str = "*"

    skt_warning_days: int = 90

    invoice_folder: str = "./data/invoices"
    invoice_reminder_days: int = 7

    clinical_docs_folder: str = "./data/clinical_docs"
    vector_db_dir: str = "./data/vectorstore"

    checkin_photos_folder: str = "./data/checkins"

    backup_dir: str = "./data/backups"
    backup_keep_count: int = 8

    qwen_base_url: str = "http://localhost:11434/v1"
    qwen_api_key: str = "ollama"
    qwen_model: str = "qwen2.5:14b-instruct"
    # Cevap süresi büyük ölçüde ÜRETİLEN token sayısıyla doğru orantılı;
    # sınır koymak en uzun cevaplarda beklemeyi kısaltır.
    qwen_max_tokens: int = 900
    # Model yanıt vermezse istemcinin varsayılan zaman aşımı 10 dakika;
    # kullanıcı o kadar bekleyemez.
    qwen_timeout_seconds: int = 60
    # Qwen3 ailesi varsayılan olarak "düşünme" (thinking) modunda çalışır ve
    # cevaptan önce görünmeyen uzun bir muhakeme üretir - süreyi katlar.
    # Model bu parametreyi desteklemiyorsa istek hata verebileceği için
    # kapatma isteğe bağlı.
    qwen_disable_thinking: bool = False

    pubmed_email: str = ""
    pubmed_api_key: str = ""

    evobulut_username: str = ""
    evobulut_password: str = ""
    evobulut_app_name: str = "7ai-saha-uygulamasi"

    # E-posta - günlük vade/SKT özetini göndermek için.
    # Railway'in Hobby planı giden SMTP portlarını (25/465/587/2525) tamamen
    # engellediğinden birincil yöntem HTTPS API'li bir servis (Resend).
    # SMTP ayarları, SMTP'nin açık olduğu ortamlar için yedek olarak durur.
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    digest_hour: int = 8
    app_public_url: str = "https://saha.7medikal.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
