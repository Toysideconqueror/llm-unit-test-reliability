"""
Khâu 2 của pipeline (Java): compile class + test JUnit5 đã sinh, chạy với JaCoco
javaagent để instrument, rồi tạo report CSV để lấy BRANCH_COVERED/BRANCH_MISSED.

CÀI ĐẶT 1 LẦN (chạy ở cell đầu notebook, xem README):
  mkdir -p tools && cd tools
  wget -q https://github.com/junit-team/junit5/releases/download/.../junit-platform-console-standalone-<ver>.jar -O junit-platform-console-standalone.jar
  wget -q https://repo1.maven.org/maven2/org/jacoco/org.jacoco.agent/<ver>/org.jacoco.agent-<ver>-runtime.jar -O jacocoagent.jar
  wget -q https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/<ver>/org.jacoco.cli-<ver>-nodeps.jar -O jacococli.jar
(Colab đã có sẵn JDK; kiểm tra bằng `!java -version`.)

LƯU Ý QUAN TRỌNG:
`source_code` trong functions_java.jsonl phải là FULL CLASS (không chỉ method body)
để javac compile độc lập được — xem data/SCHEMA.md và data/prepare_dataset.py.
"""
import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

TOOLS_DIR = Path("tools")
JUNIT_JAR = TOOLS_DIR / "junit-platform-console-standalone.jar"
JACOCO_AGENT = TOOLS_DIR / "jacocoagent.jar"
JACOCO_CLI = TOOLS_DIR / "jacococli.jar"


def measure_branch_coverage_java(class_source: str, test_source: str,
                                  class_name: str, test_class_name: str,
                                  coverage_target_class: str = None,
                                  timeout: int = 60):
    """coverage_target_class: tên class THẬT SỰ chứa target_method cần đo coverage.
    Mặc định = class_name, NHƯNG với file có nhiều class (class phụ trợ + class public
    chính), class chứa method cần test có thể khác class public (vd file KahnsAlgorithm.java
    có class public KahnsAlgorithm nhưng logic thật nằm ở class nội bộ TopologicalSort).
    class_name vẫn dùng để đặt tên file .java (BẮT BUỘC khớp public class để javac compile
    được) - coverage_target_class chỉ dùng để tra đúng dòng trong report JaCoco."""
    coverage_target_class = coverage_target_class or class_name
    workdir = Path(tempfile.mkdtemp())
    try:
        src_dir, test_dir, classes_dir = workdir / "src", workdir / "test", workdir / "classes"
        for d in (src_dir, test_dir, classes_dir):
            d.mkdir(parents=True)

        (src_dir / f"{class_name}.java").write_text(class_source)
        (test_dir / f"{test_class_name}.java").write_text(test_source)

        compile_cmd = [
            "javac", "-cp", str(JUNIT_JAR), "-d", str(classes_dir),
            str(src_dir / f"{class_name}.java"), str(test_dir / f"{test_class_name}.java"),
        ]
        c = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=timeout)
        if c.returncode != 0:
            return 0.0, f"compile_error: {c.stderr[:300]}"

        exec_file = workdir / "jacoco.exec"
        run_cmd = [
            "java", f"-javaagent:{JACOCO_AGENT}=destfile={exec_file}",
            "-jar", str(JUNIT_JAR), "-cp", str(classes_dir),
            "--select-class", test_class_name, "--details=none",
        ]
        r = subprocess.run(run_cmd, capture_output=True, text=True, timeout=timeout)
        status = "ok" if r.returncode == 0 else "test_failed"

        report_csv = workdir / "report.csv"
        report_cmd = [
            "java", "-jar", str(JACOCO_CLI), "report", str(exec_file),
            "--classfiles", str(classes_dir), "--sourcefiles", str(src_dir),
            "--csv", str(report_csv),
        ]
        subprocess.run(report_cmd, capture_output=True, text=True, timeout=timeout)
        if not report_csv.exists():
            return 0.0, "coverage_error"

        with open(report_csv) as f:
            row = next((r for r in csv.DictReader(f) if r["CLASS"] == coverage_target_class), None)
        if not row:
            return 0.0, "no_data"

        branch_missed = int(row["BRANCH_MISSED"])
        branch_covered = int(row["BRANCH_COVERED"])
        total = branch_missed + branch_covered
        pct = (branch_covered / total * 100) if total > 0 else (100.0 if status == "ok" else 0.0)
        return round(pct, 2), status
    except subprocess.TimeoutExpired:
        return 0.0, "timeout"
    except Exception as e:
        return 0.0, f"error:{e}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_batch(functions: list, tests_dir: Path, out_csv: Path):
    rows = []
    for fn in functions:
        test_file = tests_dir / f"{fn['id']}_test.java"
        if not test_file.exists():
            rows.append({"id": fn["id"], "cc": fn["cc"], "branch_coverage": None,
                         "status": "no_test_generated"})
            continue

        pct, status = measure_branch_coverage_java(
            fn["source_code"], test_file.read_text(), fn["class_name"], fn["test_class_name"],
            coverage_target_class=fn.get("coverage_target_class"),
        )
        rows.append({"id": fn["id"], "cc": fn["cc"], "branch_coverage": pct, "status": status})
        print(f"{fn['id']} (cc={fn['cc']}): {pct}% [{status}]")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "cc", "branch_coverage", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out_csv}")
