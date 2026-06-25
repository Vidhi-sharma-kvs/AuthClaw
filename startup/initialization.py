import json
import logging
from providers import get_provider

logger = logging.getLogger("authclaw.startup.initialization")

def initialize_provider():
    """
    Initializes the configured LLM provider and verifies it is ready.
    Fails application startup if provider initialization fails.
    """
    try:
        provider = get_provider()
        
        # Structured JSON logging for success
        success_log = {
            "event": "provider_initialization",
            "status": "success",
            "message": "LLM provider initialized successfully.",
            "details": {
                "provider_class": provider.__class__.__name__,
                "model_name": provider.model_name
            }
        }
        logger.info(json.dumps(success_log))
        print(json.dumps(success_log), flush=True)
        return provider

    except Exception as e:
        # Structured JSON logging for failure
        failure_log = {
            "event": "provider_initialization",
            "status": "failed",
            "message": f"LLM provider initialization failed: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        }
        logger.error(json.dumps(failure_log))
        print(json.dumps(failure_log), flush=True)
        raise RuntimeError("LLM provider initialization failed. Aborting startup.") from e
