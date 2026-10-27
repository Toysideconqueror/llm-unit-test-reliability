"""
Gemini client. Cài đặt: pip install google-genai
Lấy key miễn phí tại https://aistudio.google.com
"""
from google import genai
from google.genai import types

from .base_client import BaseLLMClient


class GeminiClient(BaseLLMClient):
    def __init__(self, config: dict, api_key: str):
        super().__init__(config)
        self.client = genai.Client(api_key=api_key)
        self.model_name = config["model_name"]
        gen = config["generation"]
        self.gen_config = types.GenerateContentConfig(
            temperature=gen["temperature"],
            max_output_tokens=gen["max_output_tokens"],
        )

    def _call_api(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self.gen_config,
        )
        return response.text
