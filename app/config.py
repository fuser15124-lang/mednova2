from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "MedNova AI"
    database_url: str = "sqlite:///./mednova.db"
    jwt_secret: str = "dev-only-change-me-change-this-secret-please"
    jwt_expire_minutes: int = 720
    max_upload_mb: int = 10
    # Groq exposes an OpenAI-compatible chat-completions API. Keep the key in server env vars only.
    ai_base_url: str = "https://api.groq.com/openai/v1"
    ai_api_key: str = ""
    ai_model: str = "llama-3.3-70b-versatile"
    cors_origins: str = "https://mednova.pages.dev,http://localhost:8000,http://127.0.0.1:8000"
    ai_timeout_seconds: int = 45
    ncbi_tool: str = "MedNovaAI"
    ncbi_email: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

settings = Settings()
