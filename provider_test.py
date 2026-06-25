import os
import sys
import logging

# Configure basic logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("provider_test")

# Add workspace path to system path to import modules
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load environment variables using internal env loader
import startup.env_loader

from providers.gemini_provider import GeminiProvider

def main():
    logger.info("Starting Standalone Provider Test")
    
    try:
        # Initialize provider
        provider = GeminiProvider()
        
        logger.info("Sending prompt to Gemini: 'What is GDPR?'")
        response = provider.generate("What is GDPR?")
        
        logger.info("Response successfully generated!")
        print("\n=== GENERATED RESPONSE ===")
        print(response)
        print("==========================\n")
        
    except Exception as e:
        logger.error(f"Provider test failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
