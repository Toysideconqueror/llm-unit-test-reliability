"""
Khâu 3 của pipeline: gộp toàn bộ file results_{provider}_{model}.csv (do từng thành viên
tạo ra ở khâu 2, nằm chung 1 Google Drive) thành 1 bảng, rồi tổng hợp theo CC bucket
để trả lời trực tiếp RQ1.
"""
from pathlib import Path

import pandas as pd


def aggregate(results_dir: Path, out_path: Path) -> pd.DataFrame:
    frames = []
    for csv_file in sorted(results_dir.glob("results_*.csv")):
        df = pd.read_csv(csv_file)
        df["model"] = csv_file.stem.replace("results_", "")
        frames.append(df)

    if not frames:
        raise FileNotFoundError(f"Không tìm thấy file results_*.csv nào trong {results_dir}")

    all_df = pd.concat(frames, ignore_index=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(out_path, index=False)
    print(f"Gộp {len(frames)} model, {len(all_df)} dòng -> {out_path}")
    return all_df


def summarize_by_cc(all_df: pd.DataFrame) -> pd.DataFrame:
    df = all_df.copy()
    df["cc_bucket"] = pd.cut(df["cc"], bins=[4, 7, 10, 13, 15],
                              labels=["5-7", "8-10", "11-13", "14-15"])

    # Chỉ "ok" và "test_failed" là coverage ĐO ĐƯỢC THẬT (branch_coverage có ý nghĩa).
    # Các status còn lại (timeout/compile_error/coverage_error/no_data/no_test_generated/
    # error:...) là LỖI HẠ TẦNG, không phản ánh khả năng LLM viết test -> phải loại khỏi
    # mẫu tính RQ1, nếu không sẽ làm sai lệch mean/pct_ge_80 (bị kéo về phía 0% oan uổng).
    measured = df["status"].isin(["ok", "test_failed"])
    df_measured = df[measured].copy()

    summary = df_measured.groupby(["model", "cc_bucket"], observed=True).agg(
        n_measured=("branch_coverage", "count"),
        mean_branch_coverage=("branch_coverage", "mean"),
        pct_functions_ge_80=("branch_coverage", lambda s: (s >= 80).mean() * 100),
        pct_valid_test=("status", lambda s: (s == "ok").mean() * 100),
    ).reset_index()

    # Báo cáo riêng tỷ lệ lỗi hạ tầng theo bucket, để biết % mẫu bị loại và vì lý do gì
    # (không gộp lẫn vào summary chính, nhưng vẫn cần biết để đánh giá độ tin cậy kết quả).
    infra_fail = (
        df[~measured]
        .groupby(["model", "cc_bucket", "status"], observed=True)
        .size()
        .rename("count")
        .reset_index()
    )

    return summary.sort_values(["model", "cc_bucket"]), infra_fail.sort_values(["model", "cc_bucket"])
