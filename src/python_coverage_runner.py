"""
Khâu 2 của pipeline (Python): chạy test đã sinh cho từng hàm, đo BRANCH coverage
(không phải statement coverage) bằng coverage.py, ghi 1 dòng CSV / hàm.

Lưu ý: `summary.percent_covered` mặc định của coverage.py là coverage KẾT HỢP
statement + branch. Để lấy đúng branch coverage phải tự tính
covered_branches / num_branches.
"""
import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def measure_branch_coverage(function_source: str, test_source: str, timeout: int = 30):
    """Chạy 1 cặp (function, test) trong sandbox tạm, trả về (branch_pct, status)."""
    workdir = Path(tempfile.mkdtemp())
    try:
        (workdir / "target_function.py").write_text(function_source)
        (workdir / "test_target_function.py").write_text(test_source)
        (workdir / ".coveragerc").write_text("[run]\nbranch = True\n")

        run = subprocess.run(
            ["coverage", "run", "--branch", "-m", "pytest", "test_target_function.py", "-q"],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
        )
        status = "ok" if run.returncode == 0 else "test_failed"

        subprocess.run(["coverage", "json", "-o", "cov.json"],
                        cwd=workdir, capture_output=True, text=True)
        cov_file = workdir / "cov.json"
        if not cov_file.exists():
            return 0.0, "coverage_error"

        data = json.loads(cov_file.read_text())
        file_data = data.get("files", {}).get("target_function.py")
        if not file_data:
            return 0.0, "no_data"

        summary = file_data["summary"]
        num_branches = summary.get("num_branches", 0)
        covered_branches = summary.get("covered_branches", 0)
        if num_branches > 0:
            branch_pct = covered_branches / num_branches * 100
        else:
            # hàm không có nhánh rẽ (CC=1) -> coi như 100% nếu chạy được
            branch_pct = 100.0 if status == "ok" else 0.0

        return round(branch_pct, 2), status
    except subprocess.TimeoutExpired:
        return 0.0, "timeout"
    except Exception as e:
        return 0.0, f"error:{e}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_batch(functions: list, tests_dir: Path, out_csv: Path):
    rows = []
    for fn in functions:
        test_file = tests_dir / f"{fn['id']}_test.py"
        if not test_file.exists():
            rows.append({"id": fn["id"], "cc": fn["cc"], "branch_coverage": None,
                         "status": "no_test_generated"})
            continue

        pct, status = measure_branch_coverage(fn["source_code"], test_file.read_text())
        rows.append({"id": fn["id"], "cc": fn["cc"], "branch_coverage": pct, "status": status})
        print(f"{fn['id']} (cc={fn['cc']}): {pct}% [{status}]")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "cc", "branch_coverage", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out_csv}")
