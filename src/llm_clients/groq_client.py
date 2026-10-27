"""
Groq client. Cài đặt: pip install groq
Lấy key miễn phí tại https://console.groq.com
"""
from groq import Groq

from .base_client import BaseLLMClient


class GroqClient(BaseLLMClient):
    def __init__(self, config: dict, api_key: str):
        super().__init__(config)
        self.client = Groq(api_key=api_key)
        self.model_name = config["model_name"]
        self.gen = config["generation"]

    def _call_api(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.gen["temperature"],
            max_tokens=self.gen["max_output_tokens"],
        )
        return resp.choices[0].message.content
