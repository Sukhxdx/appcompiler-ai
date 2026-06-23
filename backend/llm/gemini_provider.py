"""Google Gemini LLM provider."""

from __future__ import annotations

import os

from llm.provider import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_prompt,
            generation_config={"temperature": 0.2, "response_mime_type": "application/json"},
        )
        response = await model.generate_content_async(user_prompt)
        return response.text or "{}"
