# evals

Rubric-based evaluation assets for matching quality and smoke checks.

## Layout

- `fixtures/`: deterministic smoke test inputs
- `results/smoke/`: generated smoke evaluation artifacts

## Run

```bash
python scripts/run_rubric_smoke.py
```

The script writes:

- `evals/results/smoke/latest.json`
