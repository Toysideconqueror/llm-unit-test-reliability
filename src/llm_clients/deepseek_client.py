"""
DeepSeek client (REST API tương thích OpenAI). Cài đặt: pip install requests
Lấy key + credit miễn phí ban đầu tại https://platform.deepseek.com
"""
import requests

from .base_client import BaseLLMClient


class DeepSeekClient(BaseLLMClient):
    URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, config: dict, api_key: str):
        super().__init__(config)
        self.api_key = api_key
        self.model_name = config["model_name"]
        self.gen = config["generation"]

    def _call_api(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.gen["temperature"],
            "max_tokens": self.gen["max_output_tokens"],
        }
        r = requests.post(self.URL, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
