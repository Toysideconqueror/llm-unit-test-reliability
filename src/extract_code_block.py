"""
LLM đôi khi vẫn trả code kèm ```python ... ``` dù đã yêu cầu không dùng markdown.
Hàm này lấy phần code bên trong fence nếu có, nếu không thì coi cả response là code.
"""
import re


def extract_code_block(text: str, language: str) -> str:
    pattern = rf"```(?:{language})?\s*(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()
