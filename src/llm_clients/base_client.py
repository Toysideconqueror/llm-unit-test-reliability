"""
Abstract base class cho mọi LLM client.

Mỗi provider chỉ cần viết 1 class con implement `_call_api(prompt) -> str`.
Phần retry/backoff cho lỗi rate-limit (429) hoặc lỗi mạng tạm thời dùng chung ở đây,
để generate_tests.py không cần biết đang gọi provider nào.
"""
import random
import time


class BaseLLMClient:
    def __init__(self, config: dict):
        self.config = config
        gen = config["generation"]
        self.max_retries = gen["max_retries"]
        self.backoff_base = gen["retry_backoff_base_seconds"]

    def _call_api(self, prompt: str) -> str:
        """Override ở class con: gọi API thật, trả về text response thuần."""
        raise NotImplementedError

    def generate(self, prompt: str) -> str:
        """Gọi API kèm exponential backoff + jitter khi gặp lỗi tạm thời.
        Lỗi hết quota THEO NGÀY (RPD) sẽ không tự khỏi trong vài giây/phút -> fail
        ngay sau lần thử đầu tiên thay vì tốn ~2 phút retry vô ích."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._call_api(prompt)
            except Exception as e:
                last_err = e
                if "RESOURCE_EXHAUSTED" in str(e) and "PerDay" in str(e):
                    raise RuntimeError(f"Hết quota theo NGÀY (RPD), không retry: {e}")
                wait = self.backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
                print(f"[WARN] attempt {attempt}/{self.max_retries} failed: {e}. "
                      f"Retry sau {wait:.1f}s")
                time.sleep(wait)
        raise RuntimeError(f"LLM call thất bại sau {self.max_retries} lần thử: {last_err}")
