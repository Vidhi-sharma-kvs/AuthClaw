from google import genai
import os
import pytest

@pytest.mark.skipif(
    os.getenv("GOOGLE_API_KEY") in (None, "", "dummy") or os.getenv("GOOGLE_API_KEY", "").startswith("AQ.Ab"),
    reason="Google API Key is not configured with a valid key for live integration testing."
)
def test_gemini_api_call():
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents="What is GDPR?"
    )
    print(response.text)
    assert response.text is not None