# Schema dữ liệu chuẩn (JSONL)

Toàn bộ pipeline (generate_tests, coverage_runner, aggregate) đọc dữ liệu từ 2 file:
`data/functions_python.jsonl` và `data/functions_java.jsonl`. Mỗi dòng là 1 object JSON
tương ứng 1 hàm.

## Python — mỗi dòng trong `functions_python.jsonl`

```json
{
  "id": "py_0001",
  "language": "python",
  "function_name": "quantize_array",
  "source_code": "def quantize_array(x, levels):\n    ...",
  "cc": 7,
  "dataset_source": "UnLeakedTestBench",
  "file_path": "original/path/for/traceability.py"
}
```

- `source_code`: **phải là hàm đứng độc lập, chạy được** khi đặt trong file
  `target_function.py` (không phụ thuộc import nội bộ project gốc). Nếu hàm gốc có
  import/phụ thuộc, cần copy phần import cần thiết vào đầu `source_code`.

## Java — mỗi dòng trong `functions_java.jsonl`

```json
{
  "id": "java_0001",
  "language": "java",
  "class_name": "StringUtilsQuantize",
  "test_class_name": "StringUtilsQuantizeTest",
  "source_code": "public class StringUtilsQuantize {\n    public static int quantize(...) { ... }\n}",
  "cc": 9,
  "dataset_source": "Commons-lang",
  "file_path": "original/path/for/traceability.java"
}
```

- `source_code` ở đây là **FULL CLASS**, không chỉ method body — để `javac` compile được
  độc lập. Nếu dữ liệu `final_functions` hiện tại của nhóm chỉ lưu method, dùng
  `prepare_dataset.py` để bọc lại thành class tối thiểu (xem TODO trong file đó).
- `class_name` phải khớp tên public class trong `source_code` (Java yêu cầu tên file =
  tên class public).
- `test_class_name` là quy ước đặt tên cho class test sẽ được LLM sinh ra /
  `java_coverage_runner.py` dùng để compile + chạy JUnit.

## Vì sao dùng JSONL thay vì 300 file rời

- Duyệt dataset bằng 1 vòng `for` đơn giản, không phải quét thư mục.
- Dễ filter/group theo `cc` bằng pandas khi phân tích RQ1.
- Dễ diff khi 2 người cùng chỉnh dataset (mỗi hàm 1 dòng).
