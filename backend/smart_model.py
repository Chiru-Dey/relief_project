import time
import re
import random
from google.adk.models.google_llm import Gemini
from google.genai.errors import ClientError
from google.api_core.exceptions import ResourceExhausted

class SmartGemini(Gemini):
    """
    A wrapper around the ADK Gemini model that implements 
    logic-based retries. It blocks execution until the API succeeds 
    or max retries are hit.
    """
    def __init__(self, model: str, **kwargs):
        super().__init__(model=model, **kwargs)

    def _extract_wait_time(self, error_str):
        """Regex to find 'retry in 12.34s'."""
        match = re.search(r"retry (?:in|after) (\d+(\.\d+)?)s", str(error_str))
        if match:
            return float(match.group(1))
        return None

    def _calculate_backoff(self, attempt):
        """Fallback exponential backoff."""
        delay = min(60, 2 * (2 ** attempt))
        return delay * (0.5 + random.random() / 2)

    def generate_content(self, *args, **kwargs):
        """
        Overrides the base generation method to inject the custom retry loop.
        """
        max_retries = 10
        current_attempt = 0

        while True:
            try:
                # Attempt the actual API call
                return super().generate_content(*args, **kwargs)

            except Exception as e:
                error_str = str(e)
                
                # Check for Rate Limits (429)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota" in error_str:
                    current_attempt += 1
                    if current_attempt > max_retries:
                        raise e # Give up after 10 tries

                    # 1. Try to get exact time from Google
                    wait_time = self._extract_wait_time(error_str)
                    
                    if wait_time:
                        wait_time += 1.0 # Add 1s buffer
                        print(f"⏳ Backend Rate Limit: Sleeping {wait_time:.2f}s...")
                    else:
                        wait_time = self._calculate_backoff(current_attempt)
                        print(f"⏳ Backend Rate Limit: Backing off {wait_time:.2f}s...")
                    
                    time.sleep(wait_time)
                    continue # Retry the loop
                
                # Re-raise other errors immediately
                raise e