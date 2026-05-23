from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    llm_provider: str = "anthropic"
    main_agent_model: str = "claude-haiku-4-5-20251001"
    classifier_model: str = "claude-haiku-4-5-20251001"
    summarizer_model: str = "claude-haiku-4-5-20251001"
    memory_dir: Path = Path("memory")
    skills_dir: Path = Path("skills")
    sessions_dir: Path = Path("sessions")
    max_response_tokens: int = 2048
    enable_cache: bool = True
    cors_origins: list[str] = ["http://localhost:5173"]
    project_root: Path = Path(__file__).resolve().parent.parent

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def resolve(self, p: Path) -> Path:
        return self.project_root / p


settings = Settings()
