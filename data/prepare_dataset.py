"""
Chuyển dataset 300 hàm Python + 300 hàm Java hiện có (folder `final_functions_python`,
`final_functions`) sang 2 file JSONL chuẩn mà pipeline dùng chung
(xem data/SCHEMA.md).

Phần Python (load_python_raw) đã được chỉnh khớp với format thật của
final_functions_python: mỗi hàm 1 file .py, 3 dòng comment header rồi đến định nghĩa hàm:

    # task_id: 15815
    # cyclomatic_complexity: 11
    # mo ta (prompt): <mô tả>

    def compute_h(symbolic_s):
        ...

Phần Java (load_java_raw) vẫn còn TODO vì chưa có mẫu dataset Java thật để đối chiếu.

Chạy: python data/prepare_dataset.py
"""
import json
import re
from pathlib import Path

PYTHON_RAW_DIR = Path("final_functions_python")
JAVA_RAW_DIR = Path("final_functions")             # TODO: sửa khi có dataset Java thật
JAVA_LIZARD_CSV = Path("report.csv")               # TODO: output của lệnh lizard -C 1 --csv

OUT_PYTHON = Path("data/functions_python.jsonl")
OUT_JAVA = Path("data/functions_java.jsonl")

# Nhiều hàm trong UnLeakedTestBench dùng module chuẩn (math.log, datetime.date...) mà
# KHÔNG có dòng import kèm theo trong file — có vẻ benchmark gốc giả định sẵn các module
# này trong namespace khi chấm. Nếu không thêm import, hàm sẽ lỗi NameError khi chạy độc
# lập trong target_function.py. Danh sách dưới đây là các module hay gặp; nếu khi chạy
# thử thấy nhiều status "test_failed" do NameError với module khác, bổ sung vào đây.
COMMON_MODULES = [
    "math", "datetime", "re", "random", "itertools", "collections",
    "string", "json", "os", "sys", "functools", "heapq", "bisect", "copy",
]


def parse_header_and_body(text: str):
    """Tách phần header comment (# key: value) ở đầu file khỏi phần thân hàm."""
    lines = text.split("\n")
    header = {}
    i = 0
    while i < len(lines) and lines[i].strip().startswith("#"):
        line = lines[i].strip().lstrip("#").strip()
        if ":" in line:
            key, _, val = line.partition(":")
            header[key.strip()] = val.strip()
        i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    body = "\n".join(lines[i:]).rstrip("\n")
    return header, body


def guess_missing_imports(source: str) -> str:
    """Tự động thêm `import X` cho các module chuẩn được dùng (vd math.log) nhưng chưa
    có import trong file, để hàm chạy độc lập được khi đưa vào target_function.py."""
    missing = []
    for mod in COMMON_MODULES:
        used = re.search(rf"\b{mod}\.\w+", source)
        already_imported = re.search(rf"^\s*import\s+{mod}\b", source, re.MULTILINE)
        if used and not already_imported:
            missing.append(f"import {mod}")
    if missing:
        return "\n".join(missing) + "\n\n" + source
    return source


def load_python_raw():
    items = []
    n_skipped_no_header, n_skipped_cc_range = 0, 0
    for f in sorted(PYTHON_RAW_DIR.glob("*.py")):
        text = f.read_text(encoding="utf-8")
        header, body = parse_header_and_body(text)

        cc_str = header.get("cyclomatic_complexity")
        if cc_str is None:
            print(f"[SKIP] không đọc được cyclomatic_complexity trong header: {f.name}")
            n_skipped_no_header += 1
            continue
        cc = int(cc_str)
        if not (5 <= cc <= 15):
            n_skipped_cc_range += 1
            continue

        body = guess_missing_imports(body)
        func_match = re.search(r"def\s+(\w+)\s*\(", body)
        function_name = func_match.group(1) if func_match else f.stem.split("_", 1)[-1]
        task_id = header.get("task_id", f.stem.split("_", 1)[0])

        items.append({
            "id": f"py_{task_id}",
            "language": "python",
            "function_name": function_name,
            "source_code": body,
            "cc": cc,
            "dataset_source": "UnLeakedTestBench",
            "file_path": str(f),
            "description": header.get("mo ta (prompt)", ""),
        })

    print(f"Python: {len(items)} hàm giữ lại (CC 5-15), "
          f"{n_skipped_cc_range} bị loại do ngoài khoảng CC, "
          f"{n_skipped_no_header} bị loại do thiếu header.")
    return items


def load_java_raw():
    """
    TODO: chỉnh theo format thật của final_functions (Commons-lang).
    Giả định tạm thời: report.csv (từ `lizard -C 1 --csv`) có cột NLOC, CCN, function
    name, file path... và mỗi hàm tương ứng 1 file .java trong JAVA_RAW_DIR chứa
    FULL CLASS (không chỉ method). Nếu file .java hiện tại chỉ chứa method body, cần
    bọc lại bằng wrap_method_as_class() bên dưới trước khi ghi ra JSONL.
    """
    import csv as csv_module
    items = []
    with open(JAVA_LIZARD_CSV) as f:
        reader = csv_module.DictReader(f)
        for i, row in enumerate(reader, start=1):
            try:
                cc = int(float(row["CCN"]))
            except (KeyError, ValueError):
                continue
            if not (5 <= cc <= 15):
                continue

            class_file = JAVA_RAW_DIR / f"{row.get('long_name', row.get('name', '')).split('.')[0]}.java"
            if not class_file.exists():
                print(f"[SKIP] không tìm thấy file: {class_file}")
                continue

            source = class_file.read_text()
            class_name = class_file.stem
            items.append({
                "id": f"java_{i:04d}",
                "language": "java",
                "class_name": class_name,
                "test_class_name": f"{class_name}Test",
                "source_code": source,
                "cc": cc,
                "dataset_source": "Commons-lang",
                "file_path": str(class_file),
            })
    return items


def wrap_method_as_class(method_source: str, class_name: str) -> str:
    """Nếu source hiện tại chỉ là method body (không phải full class), bọc tối thiểu
    để javac compile được. Method cần là static và tự chứa (không gọi field/method
    khác của class gốc) — nếu không, cần copy thêm phần phụ thuộc thủ công."""
    return f"public class {class_name} {{\n{method_source}\n}}\n"


def write_jsonl(items, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {len(items)} functions -> {out_path}")


if __name__ == "__main__":
    write_jsonl(load_python_raw(), OUT_PYTHON)
    write_jsonl(load_java_raw(), OUT_JAVA)
