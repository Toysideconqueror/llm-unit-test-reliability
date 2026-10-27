"""
Khâu 1 của pipeline: với mỗi hàm trong dataset, gọi LLM (theo config) sinh test,
lưu raw response + code đã extract ra đĩa.

Resumable: nếu file raw output đã tồn tại, hàm đó được bỏ qua -> chạy lại nhiều lần
an toàn khi hết quota / session Colab bị ngắt giữa chừng.

Dùng:
    from src.generate_tests import run
    run("python", config, api_key)
    run("java", config, api_key)
"""
import json
import time
from pathlib import Path

from src.extract_code_block import extract_code_block
from src.llm_clients import get_llm_client


def _tag(config: dict) -> str:
    return f"{config['provider']}_{config['model_name']}".replace("/", "-")


def load_jsonl(path: str):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def build_prompt(language: str, fn: dict) -> str:
    template = Path(f"prompts/test_gen_{language}.txt").read_text()
    if language == "python":
        return template.format(function_code=fn["source_code"], function_name=fn["function_name"])
    else:  # java
        return template.format(
            class_code=fn["source_code"],
            class_name=fn["class_name"],
            test_class_name=fn["test_class_name"],
        )


def _is_daily_quota_exhausted(e: Exception) -> bool:
    """True nếu lỗi là do hết quota THEO NGÀY (RPD) - retry trong vài giây/phút sẽ
    luôn thất bại lại, chỉ hết khi sang ngày mới (hoặc đổi key/project khác)."""
    msg = str(e)
    return "RESOURCE_EXHAUSTED" in msg and "PerDay" in msg


def run(language: str, config: dict, api_key: str):
    client = get_llm_client(config, api_key)
    tag = _tag(config)

    functions = load_jsonl(config["dataset"][f"{language}_path"])
    raw_dir = Path(config["paths"]["raw_output_dir"].format(tag=tag))
    test_dir = Path(config["paths"]["extracted_tests_dir"].format(tag=tag))
    raw_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    rpm_limit = config["generation"]["requests_per_minute_limit"]
    delay = 60.0 / rpm_limit
    ext = "py" if language == "python" else "java"

    n_done, n_skip, n_err = 0, 0, 0
    total = len(functions)
    for idx, fn in enumerate(functions, 1):
        raw_path = raw_dir / f"{fn['id']}.txt"
        if raw_path.exists():
            n_skip += 1
            continue

        if idx % 10 == 0 or idx == total:
            print(f"[{tag}/{language}] {idx}/{total} "
                  f"(done={n_done} skip={n_skip} err={n_err})")

        # Heartbeat MỖI hàm (không phải mỗi 10 hàm) — để không nhìn giống bị treo
        # khi model chậm (vd North Mini Code có thể mất vài phút/hàm ở free tier).
        call_start = time.time()
        print(f"[{tag}/{language}] {idx}/{total} đang gọi API cho {fn['id']}...")

        prompt = build_prompt(language, fn)
        try:
            raw_response = client.generate(prompt)
            if not raw_response:
                raise RuntimeError(
                    "Client trả về response rỗng/None (có thể do model bị chặn bởi "
                    "safety filter, hoặc hết token budget cho phần reasoning)."
                )
        except Exception as e:
            print(f"[ERROR] {fn['id']}: {e}")
            # QUAN TRỌNG: ghi lỗi ra file KHÁC raw_path (không phải "{id}.txt"), để
            # raw_path.exists() vẫn = False -> lần chạy sau tự động retry hàm này,
            # thay vì bị coi là "đã xong" và bị skip vĩnh viễn.
            error_path = raw_dir / f"{fn['id']}.error.txt"
            error_path.write_text(str(e))
            n_err += 1
            if _is_daily_quota_exhausted(e):
                print(f"[STOP] Đã hết quota NGÀY (RPD) của model này. "
                      f"Dừng sớm ở {idx}/{total} thay vì tiếp tục lãng phí thời gian "
                      f"retry cho các hàm còn lại (chắc chắn cũng sẽ lỗi tương tự). "
                      f"Chạy lại cell này sau khi quota reset (theo giờ Pacific Time) "
                      f"hoặc đổi API key/project khác.")
                break
            time.sleep(delay)
            continue

        raw_path.write_text(raw_response)
        code = extract_code_block(raw_response, language)
        (test_dir / f"{fn['id']}_test.{ext}").write_text(code)
        elapsed = time.time() - call_start
        print(f"[{tag}/{language}] {idx}/{total} xong {fn['id']} ({elapsed:.1f}s)")
        n_done += 1
        time.sleep(delay)  # tôn trọng rate limit free tier

    print(f"[{tag}/{language}] done={n_done} skipped(existing)={n_skip} errors={n_err}")
