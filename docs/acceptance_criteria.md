# 매칭 파이프라인 최종 승인 기준

## 1. 기준선 게이트 (Baseline Gate)

대원산업 오프라인 데이터로 `evals/baseline_gate_test.py` 5개 테스트 전부 PASS:

| 테스트 | 기준 |
|--------|------|
| unmatched_articles | == 0 |
| fallback_matches | == 0 |
| topic_matches | == 0 |
| degraded | == false |
| match_count | >= 조문 수 |

## 2. 기존 평가 스위트 유지

| 테스트 | 파일 | 기준 |
|--------|------|------|
| smoke_test | `evals/smoke_test.py` | PASS |
| rubric_smoke | `scripts/run_rubric_smoke.py` | score >= 99.0 |
| resilience | `evals/resilience_test.py` | 3/3 OK |
| diagnostics | `evals/diagnostics_test.py` | 3/3 OK |

## 3. 매핑 변경 규칙

- **추가**: 증거(`basis`) + 신뢰도(`confidence`) 필수. 출처: 법령 조문, 표준취업규칙, SuperLawyer 검증 등.
- **배치 크기**: 3~5건 단위 머지, 머지 전후 baseline gate 통과 확인.
- **global vs override**: 범용 매핑은 `standard_rules_2026_map.json` / `canonical_map.json`. 회사 특화는 `config/overrides/{company}.json`.

## 4. 서비스 확장 기준

MVP → 서비스 전환 시 추가 요건:

- [ ] 대원산업 외 1개 이상 회사 샘플로 baseline gate 통과 (회사별 override 허용)
- [ ] API 모드(온라인 개정 조회) 정상 동작 확인
- [ ] 신구조문 대조표(.xlsx) 생성 정상 확인

## 5. 회귀 방지

모든 PR은 다음을 통과해야 머지 가능:

```
python -m pytest evals/baseline_gate_test.py -v
python evals/smoke_test.py
python evals/resilience_test.py
python evals/diagnostics_test.py
python scripts/run_rubric_smoke.py
```
