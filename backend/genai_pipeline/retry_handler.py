"""
genai_pipeline/retry_handler.py
Retries a single Groq model call on transient failure (timeout, network
error, empty response, etc.) with exponential backoff. This does NOT switch
models -- model switching is fallback_client.py's job. This only makes one
model more resilient to flaky failures.
"""

import time

from config.settings import settings
from genai_pipeline.groq_client import call_groq, GroqClientError
from genai_pipeline.model_logger import log_call_start, log_call_success, log_call_failure


def call_with_retry(system_prompt: str, user_prompt: str, model: str, employee_code: str) -> str:
    """
    Calls Groq with up to settings.GROQ_MAX_RETRIES attempts for the given
    model. Returns the raw response text on success.
    Raises GroqClientError if every attempt fails.
    """
    last_error = None
    started_at = log_call_start(model, employee_code)

    for attempt in range(1, settings.GROQ_MAX_RETRIES + 1):
        try:
            content = call_groq(system_prompt, user_prompt, model)
            log_call_success(model, employee_code, started_at, tokens_used=len(content.split()))
            return content
        except GroqClientError as e:
            last_error = e
            log_call_failure(
                model, employee_code, started_at,
                f"attempt {attempt}/{settings.GROQ_MAX_RETRIES}: {e}"
            )
            if attempt < settings.GROQ_MAX_RETRIES:
                time.sleep(2 ** (attempt - 1))

    raise GroqClientError(
        f"Model '{model}' failed after {settings.GROQ_MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )