"""
genai_pipeline/fallback_client.py
Tries the primary Groq model first (with retries via retry_handler); if that
fully fails, automatically falls back to the secondary model. generator.py
calls this -- it never talks to groq_client.py directly.
"""

from config.settings import settings
from genai_pipeline.groq_client import GroqClientError
from genai_pipeline.retry_handler import call_with_retry
from genai_pipeline.model_logger import log_fallback_triggered


class AllModelsFailedError(Exception):
    """Raised when both the primary and fallback models fail."""
    pass


def generate_with_fallback(system_prompt: str, user_prompt: str, employee_code: str) -> dict:
    """
    Returns {"content": <raw text from Groq>, "model_used": <model name>}.
    Tries GROQ_MODEL_PRIMARY first, then GROQ_MODEL_FALLBACK if the primary
    fails after all its retries.
    """
    primary = settings.GROQ_MODEL_PRIMARY
    fallback = settings.GROQ_MODEL_FALLBACK

    try:
        content = call_with_retry(system_prompt, user_prompt, primary, employee_code)
        return {"content": content, "model_used": primary}
    except GroqClientError as primary_error:
        log_fallback_triggered(primary, fallback, employee_code)
        try:
            content = call_with_retry(system_prompt, user_prompt, fallback, employee_code)
            return {"content": content, "model_used": fallback}
        except GroqClientError as fallback_error:
            raise AllModelsFailedError(
                f"Both models failed for employee={employee_code}. "
                f"Primary ({primary}): {primary_error} | Fallback ({fallback}): {fallback_error}"
            )