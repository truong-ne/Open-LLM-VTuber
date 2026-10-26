from pydantic import BaseModel, Field
from typing import Literal


class ComputerConfig(BaseModel):
    enabled: bool = False
    allowed_origins: list[str] = Field(default_factory=list)
    actions_per_minute: int = Field(12, ge=1, le=60)
    timeout_seconds: int = Field(15, ge=1, le=60)
    approval_seconds: int = Field(120, ge=10, le=600)
    # CDP attaches only to a dedicated, operator-started debugging browser.
    cdp_url: str = ""
    headless: bool = False


class AutonomyConfig(BaseModel):
    enabled: bool = False
    idle_seconds: int = Field(120, ge=30, le=3600)
    interval_seconds: int = Field(300, ge=60, le=86400)
    daily_cycles: int = Field(24, ge=1, le=96)
    cycle_seconds: int = Field(60, ge=10, le=120)
    model: str = Field("mao-companion", min_length=1, max_length=100)


class HybridConfig(BaseModel):
    enabled: bool = False
    persona_source: Literal["config", "postgres"] = "config"
    database_url_env: str = "MAO_DATABASE_URL"
    database_env_file: str = "private/mao-hybrid.env"
    embedding_url: str = "http://127.0.0.1:11434/api/embed"
    embedding_model: str = "qwen3-embedding:0.6b"
    embedding_digest: str = ""
    embedding_dimensions: int = Field(1024, ge=1024, le=1024)
    embedding_timeout: float = Field(4, ge=0.1, le=30)
    search_mode: Literal["exact", "ann"] = "exact"
    minimum_similarity: float = Field(0.35, ge=0, le=1)
    lexical_min_overlap: int = Field(2, ge=1, le=5)
    scope: str = Field("mao", min_length=1, max_length=100)
    memory_limit: int = Field(2000, ge=10, le=20000)
    retention_days: int = Field(180, ge=1, le=3650)
    tool_rounds: int = Field(6, ge=1, le=12)
    exploration_enabled: bool = False
    exploration_steps: int = Field(3, ge=1, le=6)
    exploration_seconds: int = Field(30, ge=1, le=120)
    learning_enabled: bool = False
    learning_timezone: str = "Asia/Ho_Chi_Minh"
    learning_min_turns: int = Field(20, ge=3, le=10000)
    learning_min_feedback: int = Field(3, ge=3, le=100)
    learning_retention_days: int = Field(90, ge=7, le=365)
    external_read_tools: list[str] = Field(
        default_factory=lambda: [
            "get_current_time",
            "convert_time",
            "search",
            "fetch_content",
        ]
    )
    computer: ComputerConfig = Field(default_factory=ComputerConfig)
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
