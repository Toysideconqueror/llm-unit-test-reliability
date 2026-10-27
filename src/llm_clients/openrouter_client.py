"""
OpenRouter client (REST API tương thích OpenAI). Cài đặt: pip install requests
Lấy key miễn phí tại https://openrouter.ai — chọn model có nhãn "free".

Dùng streaming (SSE) thay vì chờ 1 response duy nhất: với model chậm (nhiều
phút/request như North Mini Code ở free tier), request non-streaming đứng im
không có byte nào chảy qua trong lúc chờ -> hay bị hạ tầng trung gian (proxy/
load balancer) coi là kết nối chết và chủ động reset (ConnectionResetError).
Streaming giữ dữ liệu chảy liên tục theo từng token -> tránh bị cắt giữa chừng.
"""
import json

import requests

from .base_client import BaseLLMClient


class OpenRouterClient(BaseLLMClient):
    URL = "https://openrouter.ai/api/v1/chat/completions"

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
            "stream": True,
            # Ép model suy luận ít nhất có thể (effort=low) và KHÔNG trả phần
            # suy luận về trong response (exclude=true) - giải quyết đúng vấn đề
            # "sinh quá nhiều text": model reasoning như North Mini Code mặc định
            # dump toàn bộ chain-of-thought dạng text thô trước khi viết code,
            # ăn hết max_tokens trước khi kịp sinh code. Model nào không hỗ trợ
            # tham số này sẽ tự bỏ qua (theo tài liệu OpenRouter), không lỗi.
            "reasoning": {"effort": "low", "exclude": True},
        }

        content_parts = []
        reasoning_parts = []
        finish_reason = None

        # timeout=60 ở đây là timeout GIỮA 2 lần nhận được dữ liệu (read timeout),
        # không phải tổng thời gian cả request -> vẫn đúng nghĩa "treo thật sự"
        # cho streaming, khác với non-streaming trước đây (chờ full response).
        with requests.post(self.URL, headers=headers, json=payload,
                            timeout=60, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or [{}]
                choice = choices[0]
                delta = choice.get("delta", {})
                if delta.get("content"):
                    content_parts.append(delta["content"])
                if delta.get("reasoning"):
                    reasoning_parts.append(delta["reasoning"])
                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

        content = "".join(content_parts)

        # Một số model reasoning (vd North Mini Code) trả nội dung suy luận
        # trong field "reasoning" riêng và để "content" rỗng, đặc biệt khi
        # max_tokens bị dùng hết cho phần reasoning trước khi kịp sinh code.
        # Fallback: nếu content rỗng nhưng có reasoning, dùng tạm reasoning
        # (extract_code_block vẫn sẽ tìm khối ```code``` bên trong nếu có).
        if not content:
            reasoning = "".join(reasoning_parts)
            if reasoning:
                content = reasoning
            else:
                raise RuntimeError(
                    f"OpenRouter trả content rỗng (finish_reason={finish_reason}). "
                    f"Model có thể đã dùng hết max_output_tokens cho phần reasoning "
                    f"trước khi sinh code — thử tăng generation.max_output_tokens "
                    f"trong config.yaml."
                )
        return content
