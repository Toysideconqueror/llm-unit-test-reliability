"""
Factory: đọc config["provider"] và trả về client tương ứng.
generate_tests.py chỉ gọi get_llm_client(config, api_key) — không cần biết provider nào.
Thêm 1 LLM mới cho nhóm = thêm 1 file client_x.py implement _call_api() + 1 nhánh ở đây.
"""


def get_llm_client(config: dict, api_key: str):
    provider = config["provider"]

    if provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient(config, api_key)

    if provider == "groq":
        from .groq_client import GroqClient
        return GroqClient(config, api_key)

    if provider == "openrouter":
        from .openrouter_client import OpenRouterClient
        return OpenRouterClient(config, api_key)

    if provider == "deepseek":
        from .deepseek_client import DeepSeekClient
        return DeepSeekClient(config, api_key)

    if provider == "cohere":
        from .cohere_client import CohereClient
        return CohereClient(config, api_key)

    raise ValueError(
        f"Provider '{provider}' chưa được hỗ trợ. "
        f"Thêm client mới trong src/llm_clients/ rồi đăng ký ở đây."
    )
