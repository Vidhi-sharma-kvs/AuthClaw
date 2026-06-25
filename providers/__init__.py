from .base import BaseProvider
from .gemini_provider import GeminiProvider
from .config import MODEL_PROVIDER

def get_provider() -> BaseProvider:
    provider_name = MODEL_PROVIDER.lower()
    if provider_name == "gemini":
        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported model provider configured: {MODEL_PROVIDER}")
