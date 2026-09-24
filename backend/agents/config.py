import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))

    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"))

    # "gemini" (hosted, no PyTorch) or "local" (sentence-transformers, needs requirements-local.txt)
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "gemini"))
    gemini_embedding_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    )

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))

    adzuna_app_id: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_ID", ""))
    adzuna_app_key: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_KEY", ""))
    adzuna_country: str = field(default_factory=lambda: os.getenv("ADZUNA_COUNTRY", "in"))
    jooble_api_key: str = field(default_factory=lambda: os.getenv("JOOBLE_API_KEY", ""))
    job_location: str = field(default_factory=lambda: os.getenv("JOB_LOCATION", "India"))

    # Postgres connection string (e.g. Supabase) for saving graph progress.
    # When empty, progress is saved to a local SQLite file instead.
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    checkpoint_db: str = field(default_factory=lambda: os.getenv("CHECKPOINT_DB", "checkpoints.sqlite"))

    allowed_origins: tuple = field(default_factory=lambda: tuple(
        o.strip() for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,https://agentic-job-ai.netlify.app"
        ).split(",") if o.strip()
    ))

    def missing(self) -> list[str]:
        """Settings the app cannot work without (job sources are checked separately)."""
        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_KEY": self.supabase_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "GROQ_API_KEY": self.groq_api_key,
        }
        missing = [name for name, value in required.items() if not value]
        if not (self.adzuna_app_id and self.adzuna_app_key) and not self.jooble_api_key:
            missing.append("ADZUNA_APP_ID + ADZUNA_APP_KEY or JOOBLE_API_KEY")
        return missing
