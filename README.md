# Reliability of LLM-Generated Unit Tests

Empirical study of how far unit tests written by large language models can be trusted.
Six LLMs generated JUnit / pytest tests for **646 functions** (327 Java + 319 Python, cyclomatic
complexity 5–15); every generated test was compiled, run and measured for **branch coverage**.

Course project for **SWT301 – Software Testing**, FPT University HCMC (2026), done as a team.

## Research questions

1. How reliable are LLM-generated unit tests (share that compile, run and pass) and how much branch coverage do they reach?
2. Which of the 6 models is most reliable, and are the differences statistically significant?
3. Does function complexity (cyclomatic complexity) reduce coverage – is there a "coverage cliff"?
4. Do more test cases mean higher coverage?
5. Is a model equally strong in Java and Python?

## Setup

| | |
|---|---|
| Functions | 646 (327 Java, 319 Python), CC 5–15, self-contained functions |
| Models | Gemini-3.7-Flash, GPT-5.6-Luna, Gemma-4-31B-IT, Gemini-3.5-Flash-Lite, Gemma-4-26B-A4B-IT, GPT-OSS-120B |
| Runs | 1 generation per (model, function) → 3,876 results |
| Prompt | one fixed prompt per language, identical for every model ([`prompts/`](prompts)) |
| Generation | temperature 0.2, max 8,192 output tokens, up to 5 retries with exponential back-off ([`config/config.example.yaml`](config/config.example.yaml)) |
| Coverage | Java: JaCoCo 0.8.12 (`BRANCH_COVERED / (BRANCH_COVERED + BRANCH_MISSED)`); Python: coverage.py with `branch = True` |
| Status per result | `ok`, `test_failed`, `compile_error`, `coverage_error`, `timeout`, `error`, `no_data`, `no_test_generated` |

**Ok Rate** = share of functions whose generated tests compile, run and pass.
Branch coverage is reported on the `ok` results.

## Pipeline

Three independent, resumable stages – each writes to disk and the next one reads it back,
so an interrupted Colab session or an exhausted API quota never loses work.

```
functions.jsonl ──► generate_tests.py ──► python/java_coverage_runner.py ──► aggregate_results.py ──► analysis notebook
   (dataset)         (LLM → test code)      (run tests, measure branches)       (one master table)      (stats + figures)
```

Switching model = editing three lines of `config/config.yaml`; no code changes.
Providers implemented in [`src/llm_clients/`](src/llm_clients): Gemini, Groq, OpenRouter, DeepSeek, Cohere.
Design notes (Vietnamese): [`docs/pipeline-design.vi.md`](docs/pipeline-design.vi.md).

## Results

| Model | Ok Rate | Avg. branch coverage (ok) | Median coverage (ok) | Avg. test cases |
|---|---:|---:|---:|---:|
| Gemini-3.7-Flash | 79.88 % | 90.39 % | 100 % | 11.84 |
| GPT-5.6-Luna | 69.81 % | 86.41 % | 100 % | 12.14 |
| Gemma-4-31B-IT | 54.80 % | 95.76 % | 100 % | 9.92 |
| Gemini-3.5-Flash-Lite | 45.36 % | 94.41 % | 100 % | 7.59 |
| Gemma-4-26B-A4B-IT | 44.89 % | 94.85 % | 100 % | 9.82 |
| GPT-OSS-120B | 31.27 % | 94.45 % | 100 % | 8.58 |

(`results/summary_by_model.csv`, recomputed from `results/master_results.csv`.)

Ok Rate by language: [`results/ok_rate_by_model_language.csv`](results/ok_rate_by_model_language.csv).

**What the data shows**

- **Validity, not coverage, is the bottleneck.** Ok Rate ranges from 31 % to 80 %; four of six models produce usable test suites for only 31–55 % of functions. Once a suite runs, the median branch coverage is 100 % for every model.
- **More tests ≠ more coverage.** Across `ok` results the number of test cases is uncorrelated with branch coverage (Spearman ρ ≈ 0.00, p = 0.95).
- **Hard functions are hard for everyone.** 45 of 646 functions (7.0 %, mean CC 11.9 vs 10.1 overall) failed with all six models; 61 (9.4 %) succeeded with all six.
- **Complexity effect is smaller than expected.** For four models the coverage drop only appears at CC ≈ 12–14 and is 2–3 points; for the two strongest models the "cliff" is masked by survivorship bias (complex functions are filtered out before coverage is measured). See the report, §4.5.
- **Language asymmetry** is large for GPT-5.6-Luna (Java 93.0 % vs Python 46.1 % Ok Rate) and small for the others (see the limitation below about GPT-5.6-Luna's Python data).

Full analysis with 10 figures and statistical tests (Kruskal–Wallis, Mann–Whitney U, Spearman, Chi-square):
[`docs/Unit_Test_LLM_Report_EN.docx`](docs/Unit_Test_LLM_Report_EN.docx), [`results/figures/`](results/figures),
[`analysis/Phan_tich_LLM_Unit_Test_Coverage.ipynb`](analysis/Phan_tich_LLM_Unit_Test_Coverage.ipynb).

## Repository layout

```
├── src/               pipeline: generation, coverage runners, aggregation, LLM clients
├── prompts/           fixed prompts (Python, Java)
├── config/            config.example.yaml – copy to config.yaml (never commit keys)
├── data/              manifests of the 646 functions (+ schema and dataset-preparation script)
├── tools/             download_tools.sh – fetches JaCoCo and the JUnit console launcher
├── notebooks/         main_pipeline.ipynb – runs the whole pipeline on Colab
├── analysis/          statistical analysis notebook
├── results/           master table, summaries, figures
└── docs/              full report, pipeline design notes
```

## Reproducing a run

1. Open `notebooks/main_pipeline.ipynb` in Colab and set `PROJECT_ROOT` to your copy of this repo.
2. Store your API key as a **Colab Secret** (the code reads the secret name from `config.yaml`; keys are never written to files).
3. Run `tools/download_tools.sh` to fetch JaCoCo 0.8.12 and JUnit console 1.11.4.
4. Provide the function datasets as `data/functions_python.jsonl` and `data/functions_java.jsonl` (format in [`data/SCHEMA.md`](data/SCHEMA.md)).
   The third-party source code is **not** redistributed here – [`data/manifest_java.csv`](data/manifest_java.csv) and
   [`data/manifest_python.csv`](data/manifest_python.csv) list every function with its original repository and file path so the set can be rebuilt.
5. Choose provider / model in `config/config.yaml`, then run all cells.

Analysis only: upload `results/master_result.xlsx` to the analysis notebook.

## Limitations

- One generation per (model, function) at temperature 0.2 – no repeated runs, so run-to-run variance is not measured.
- Ok Rate counts a test that passes; it does not prove the test asserts the *right* behaviour.
- Survivorship bias: coverage is measured only on tests that run, so complex functions that fail early drop out of the coverage statistics.
- **GPT-5.6-Luna's Python results are provisional:** the source file did not carry a model name and was attributed to GPT-5.6-Luna by elimination (it was the only model without Python data). Treat that model's Python numbers, and the Java-vs-Python gap derived from them, with caution.
- Models were called through free-tier / gateway endpoints; availability, rate limits and model versions may differ from direct provider APIs.
- Functions come from public algorithm and utility repositories and a public benchmark; training-data overlap with the evaluated models is possible.

## How this was built

The pipeline, parsers, merge scripts and analysis notebook were written with the help of an LLM assistant (Claude); the team designed the experiment, ran the models and interpreted the results.

## Credits and licensing of the data

Functions were sampled from public repositories and a benchmark, which keep their own licences: Java – TheAlgorithms/Java, mission-peace/interview, javadev/LeetCode-in-Java, williamfiset/Algorithms, phishman3579/java-algorithms-implementation; Python – UnLeakedTestBench, TheAlgorithms/Python, keon/algorithms, geekcomputers/Python, prabhupant/python-ds, sympy, scipy, numpy.
Only metadata (repository, file path, complexity) is included here.
