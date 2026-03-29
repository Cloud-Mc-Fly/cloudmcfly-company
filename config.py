"""CloudMcFly Company - Configuration via pydantic-settings."""

from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"
    api_key: str = "changeme-dev-key"
    data_dir: str = "./data"

    # LLM
    anthropic_api_key: str = ""
    claude_default_model: str = "claude-sonnet-4-6"
    claude_complex_model: str = "claude-opus-4-6"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.7

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/cloudmcfly.db"

    # Airtable
    airtable_pat: str = ""
    airtable_base_id: str = ""

    # Microsoft Teams / Graph API
    teams_tenant_id: str = ""
    teams_client_id: str = ""
    teams_client_secret: str = ""
    teams_webhook_url: str = ""

    # n8n
    n8n_webhook_url: str = ""
    n8n_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION


settings = Settings()

# --- Static Configuration ---

MAX_DEPARTMENT_ITERATIONS = 3
COLOR_AGENT_ORDER = ["yellow", "blue", "green", "red"]

DEPARTMENTS = {
    "marketing": {
        "name": "Marketing",
        "focus": "Content, LinkedIn, Positionierung, Kampagnen",
        "head_persona": (
            "Du bist Head of Marketing bei CloudMcFly. Du steuerst Content-Strategie, "
            "LinkedIn-Praesenz und Markenpositionierung im DACH-Raum fuer AI und Workday."
        ),
    },
    "sales": {
        "name": "Sales",
        "focus": "Lead-Qualifizierung, Outreach, Angebote, Follow-up",
        "head_persona": (
            "Du bist Head of Sales bei CloudMcFly. Du steuerst Lead-Generierung, "
            "Qualifizierung und den gesamten Sales-Funnel fuer AI-Consulting und Workday-Projekte."
        ),
    },
    "consulting": {
        "name": "Consulting",
        "focus": "Konzepte, AI-Strategie, Kundenloesungen, Workshops",
        "head_persona": (
            "Du bist Head of Consulting bei CloudMcFly. Du entwickelst AI-Strategien, "
            "Workday-Architekturkonzepte und Kundenloesungen auf hoechstem Niveau."
        ),
    },
    "delivery": {
        "name": "Delivery",
        "focus": "Projektsteuerung, Umsetzung, QA, Meilensteine",
        "head_persona": (
            "Du bist Head of Delivery bei CloudMcFly. Du steuerst die Umsetzung "
            "von Kundenprojekten mit PMP-Methodik, Qualitaetssicherung und Meilenstein-Tracking."
        ),
    },
    "automation": {
        "name": "Automation",
        "focus": "n8n, Integrationen, interne Tools, Agent-Building",
        "head_persona": (
            "Du bist Head of Automation bei CloudMcFly. Du baust n8n-Workflows, "
            "API-Integrationen und interne AI-Tools fuer maximale Effizienz."
        ),
    },
    "finance": {
        "name": "Finance & Admin",
        "focus": "Rechnungen, Vertraege, Dokumente, Backoffice",
        "head_persona": (
            "Du bist Head of Finance & Administration bei CloudMcFly. Du verwaltest "
            "Rechnungen, Vertraege, Angebote und alle administrativen Prozesse."
        ),
    },
}
