# RBL – LLM Test Generation & Branch Coverage Pipeline

Pipeline dùng chung cho cả nhóm để trả lời RQ1:
> LLM có sinh test đạt branch coverage ≥80% trên các hàm CC 5–15 không, và
> ngưỡng CC nào bắt đầu làm hiệu suất giảm?

## 1. Nguyên tắc thiết kế

- **1 config = 1 lần chạy đầy đủ.** Muốn đổi từ Gemini sang Groq/OpenRouter/DeepSeek/Cohere/model khác,
  chỉ sửa `config/config.yaml`, không đụng vào code còn lại.
- **Tách rời 3 khâu độc lập:** (1) sinh test bằng LLM, (2) đo branch coverage, (3) tổng hợp
  kết quả. Mỗi khâu ghi output ra đĩa (Google Drive), khâu sau đọc lại — nên nếu Colab bị
  ngắt session hoặc hết quota API giữa chừng, chạy lại là tiếp tục chứ không mất dữ liệu
  (resumable).
- **Namespace output theo `{provider}_{model}`.** Mỗi thành viên chạy 1 model sẽ ghi ra
  thư mục/file riêng (`outputs/raw/gemini_gemini-2.0-flash/...`,
  `results_gemini_gemini-2.0-flash.csv`...). Cuối cùng `aggregate_results.py` gộp toàn bộ
  file `results_*.csv` trong Drive dùng chung lại thành 1 bảng để phân tích RQ1.
- **Prompt cố định, không đổi theo model.** Để so sánh công bằng giữa các LLM, mọi người
  dùng chung 2 file `prompts/test_gen_python.txt` và `prompts/test_gen_java.txt`.

## 2. Cây thư mục

```
rbl_llm_testgen/
├── config/
│   └── config.example.yaml      # copy thành config.yaml, mỗi người sửa 3 dòng đầu
├── data/
│   ├── SCHEMA.md                 # định dạng JSONL chuẩn cho functions_python/java.jsonl
│   └── prepare_dataset.py        # convert folder 300 func hiện có -> JSONL chuẩn
├── prompts/
│   ├── test_gen_python.txt
│   └── test_gen_java.txt
├── src/
│   ├── llm_clients/               # 1 class/provider, cùng interface .generate(prompt)
│   │   ├── base_client.py
│   │   ├── gemini_client.py
│   │   ├── groq_client.py
│   │   ├── openrouter_client.py
│   │   ├── deepseek_client.py
│   │   └── cohere_client.py
│   ├── extract_code_block.py
│   ├── generate_tests.py          # khâu 1
│   ├── python_coverage_runner.py  # khâu 2 (Python)
│   ├── java_coverage_runner.py    # khâu 2 (Java)
│   └── aggregate_results.py       # khâu 3
├── notebooks/
│   └── main_pipeline.ipynb        # notebook Colab lắp ráp toàn bộ pipeline
└── outputs/                        # kết quả — nên trỏ vào Google Drive dùng chung
```

## 3. Luồng chạy cho 1 thành viên (trên Colab)

1. Mount Google Drive dùng chung của nhóm, `cd` vào project.
2. `pip install` các thư viện cần thiết (xem notebook).
3. Copy `config/config.example.yaml` → `config/config.yaml`, sửa:
   - `provider`: `gemini` / `groq` / `openrouter` / `deepseek` / `cohere`
   - `model_name`: tên model cụ thể
   - `api_key_secret_name`: tên secret Colab chứa API key của **cá nhân** (Settings → Secrets),
     không hardcode key vào code/notebook.
4. Chạy `generate_tests.py` cho `python` và `java` — sinh test, lưu raw response + code đã
   extract. Có thể dừng giữa chừng (hết quota) và chạy lại, hàm đã xử lý sẽ tự bỏ qua.
5. Chạy `python_coverage_runner.py` / `java_coverage_runner.py` — đo branch coverage thực tế
   bằng cách chạy test đã sinh, ghi `results_{provider}_{model}.csv` (cột: `id, cc,
   branch_coverage, status`).
6. Sau khi đủ các thành viên chạy xong model của mình, 1 người chạy `aggregate_results.py`
   để gộp toàn bộ `results_*.csv` trong Drive → bảng tổng + summary theo CC bucket (5–7,
   8–10, 11–13, 14–15) trả lời trực tiếp RQ1.

## 4. Lưu ý quan trọng khi triển khai

- **Rate limit free tier**: `config.generation.requests_per_minute_limit` dùng để giãn cách
  request; mỗi provider free tier có giới hạn khác nhau, mỗi người tự chỉnh theo tài liệu
  provider của mình.
- **Đo branch coverage đúng nghĩa (không phải statement coverage)**:
  - Python: bật `branch = True` trong `coverage.py`, tính
    `covered_branches / num_branches`, không dùng `percent_covered` mặc định (đó là coverage
    kết hợp statement+branch).
  - Java: dùng JaCoco, cột `BRANCH_COVERED` / (`BRANCH_COVERED` + `BRANCH_MISSED`) trong
    report CSV.
- **Dữ liệu Java cần đủ ngữ cảnh để compile**: nếu file hàm hiện tại của nhóm chỉ lưu phần
  thân method (không phải cả class Commons-lang gốc), cần bọc lại thành 1 class tối thiểu
  trước khi đưa vào `java_coverage_runner.py` — xem TODO trong `data/prepare_dataset.py`.
  Việc này nhóm cần tự kiểm tra dataset `final_functions` hiện có trước khi chạy hàng loạt.
- **Test sinh ra lỗi biên dịch/chạy vẫn phải được ghi nhận** (status: `compile_error`,
  `test_failed`, `timeout`...) chứ không bỏ qua — vì bản thân tỉ lệ lỗi theo CC cũng là dữ
  liệu trả lời RQ1 (LLM "sinh được test hợp lệ" giảm khi CC tăng).
