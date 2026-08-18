from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_EXPIRES_MINUTES: int = 1440

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "ChangeThisAdminPassword123!"

    GOOGLE_CLIENT_ID: str

    GEMINI_API_KEY: str | None = None

    OPENAI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    @property
    def cors_list(self):
        return [
            x.strip()
            for x in self.CORS_ORIGINS.split(",")
            if x.strip()
        ]


settings = Settings()