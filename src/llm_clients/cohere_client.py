"""
Cohere client (Chat V2 API). Cài đặt: pip install cohere
Lấy key miễn phí tại https://dashboard.cohere.com/api-keys

Dùng cho model North Mini Code (agentic coding, open-weight):
  model_name trong config.yaml: "north-mini-code-1-0"
"""
import cohere

from .base_client import BaseLLMClient


class CohereClient(BaseLLMClient):
    def __init__(self, config: dict, api_key: str):
        super().__init__(config)
        self.client = cohere.ClientV2(api_key=api_key)
        self.model_name = config["model_name"]
        self.gen = config["generation"]

    def _call_api(self, prompt: str) -> str:
        resp = self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.gen["temperature"],
            max_tokens=self.gen["max_output_tokens"],
        )
        return resp.message.content[0].text
