"""
config/settings.py
Centralized app settings, loaded from environment variables (.env).
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- GenAI (Groq) ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL_PRIMARY: str = os.getenv("GROQ_MODEL_PRIMARY", "llama-3.3-70b-versatile")
    GROQ_MODEL_FALLBACK: str = os.getenv("GROQ_MODEL_FALLBACK", "llama-3.1-8b-instant")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.3"))
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
    GROQ_TIMEOUT_SECONDS: int = int(os.getenv("GROQ_TIMEOUT_SECONDS", "60"))
    GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "3"))

    # --- App ---
    PROMPT_VERSION: str = "v1.0"  # legacy default; the real version comes from prompt_templates/prompt_versions.json
    # SRS Step 39 -- max generation attempts when the model returns invalid
    # or incomplete JSON (bounded: never retries forever).
    GENAI_SCHEMA_MAX_ATTEMPTS: int = int(os.getenv("GENAI_SCHEMA_MAX_ATTEMPTS", "3"))
    # Upper bound on source text sent to the model (characters).
    GENAI_MAX_SOURCE_CHARS: int = int(os.getenv("GENAI_MAX_SOURCE_CHARS", "24000"))

    # --- Auth (JWT) ---
    # Reuses the SECRET_KEY already in .env, so there is exactly one secret
    # in the whole app -- no more "SKILLSPRINT_SECRET_KEY" vs "SECRET_KEY"
    # mismatch between the token issuer and the token checker.
    JWT_SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours


settings = Settings()

if not settings.GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set in .env — GenAI generation calls will fail.")

if not settings.JWT_SECRET_KEY:
    print("WARNING: SECRET_KEY is not set in .env — auth tokens will fail to sign/verify.")