"""
담당: 팀원1 — 데이터 검증·평가
이 파일은 학습·평가용 CSV 데이터의 오류를 검사하는 기능을 구현하기 위해 만들어졌습니다.
입력: 요구사항 목록(CSV 또는 JSON)과 관계 분류 정답 CSV
출력: 데이터 오류 목록과 검사 결과
구현할 내용: 필수 항목 누락, 분류값, 요구사항 ID 참조, 중복 요구사항 쌍 검사, 분할 간 데이터 누수 검사
데이터의 의미상 정답 여부는 사람이 별도로 검토합니다.
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

VALID_LABELS = {"중복", "유사·관련", "무관"}
VALID_SPLITS = {"train", "val", "test"}

REQUIRED_REQ_COLUMNS = {"req_id", "doc_name", "doc_type", "source_location", "req_text"}
REQUIRED_PAIR_COLUMNS = {
    "case_id",
    "req_a_id",
    "req_a_text",
    "req_b_id",
    "req_b_text",
    "label",
    "reason",
    "diff_conditions",
    "split",
}


def load_requirements(path: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """requirements.csv 또는 .requirements.json 파일을 읽어 req_id 매핑과 오류 목록을 반환합니다."""
    errors = []
    req_map: dict[str, dict[str, str]] = {}

    if not path.exists():
        raise FileNotFoundError(f"요구사항 파일을 찾을 수 없습니다: {path}")

    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as f:
            rows = json.load(f)
    elif path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError(f"요구사항 CSV 헤더가 비어 있습니다: {path}")
            missing_cols = REQUIRED_REQ_COLUMNS - set(reader.fieldnames)
            if missing_cols:
                errors.append(
                    {
                        "row": 1,
                        "case_id": "-",
                        "error_type": "SCHEMA_ERROR",
                        "detail": f"requirements 파일에 필수 컬럼 누락: {sorted(missing_cols)}",
                    }
                )
            rows = list(reader)
    else:
        raise ValueError(f"지원하지 않는 요구사항 파일 형식입니다(.csv 또는 .json만 가능): {path}")

    for idx, row in enumerate(rows, start=2):
        req_id = (row.get("req_id") or "").strip()
        req_text = (row.get("req_text") or "").strip()

        if not req_id:
            errors.append(
                {
                    "row": idx,
                    "case_id": "-",
                    "error_type": "MISSING_REQ_ID",
                    "detail": "requirements 파일에 req_id가 비어 있습니다.",
                }
            )
            continue

        if req_id in req_map:
            errors.append(
                {
                    "row": idx,
                    "case_id": req_id,
                    "error_type": "DUPLICATE_REQ_ID",
                    "detail": f"요구사항 ID '{req_id}'가 중복 등록되어 있습니다.",
                }
            )
            continue

        if not req_text:
            errors.append(
                {
                    "row": idx,
                    "case_id": req_id,
                    "error_type": "EMPTY_REQ_TEXT",
                    "detail": f"요구사항 '{req_id}'의 본문(req_text)이 비어 있습니다.",
                }
            )

        req_map[req_id] = {k: (v or "").strip() for k, v in row.items()}

    return req_map, errors


def validate_pairs_csv(
    pairs_path: Path,
    req_map: dict[str, dict[str, str]],
    check_text_mismatch: bool = True,
) -> dict:
    """pairs_gt.csv의 형식, 라벨, 참조 무결성, 중복 쌍, 분할 데이터 누수를 검사합니다."""
    if not pairs_path.exists():
        raise FileNotFoundError(f"정답 쌍 CSV 파일을 찾을 수 없습니다: {pairs_path}")

    errors = []
    warnings = []

    with pairs_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"정답 쌍 CSV 헤더가 비어 있습니다: {pairs_path}")

        missing_cols = REQUIRED_PAIR_COLUMNS - set(reader.fieldnames)
        if missing_cols:
            errors.append(
                {
                    "row": 1,
                    "case_id": "-",
                    "error_type": "SCHEMA_ERROR",
                    "detail": f"pairs CSV에 필수 컬럼 누락: {sorted(missing_cols)}",
                }
            )
            return {
                "is_valid": False,
                "total_rows": 0,
                "errors": errors,
                "warnings": warnings,
                "label_counts": {},
                "split_counts": {},
                "split_label_counts": {},
            }

        rows = list(reader)

    seen_case_ids: dict[str, int] = {}
    seen_pairs: dict[tuple[str, str], str] = {}
    req_id_to_splits: dict[str, set[str]] = defaultdict(set)

    label_counts: Counter = Counter()
    split_counts: Counter = Counter()
    split_label_counts: dict[str, Counter] = defaultdict(Counter)

    required_non_empty = [
        "case_id",
        "req_a_id",
        "req_a_text",
        "req_b_id",
        "req_b_text",
        "label",
        "reason",
        "diff_conditions",
        "split",
    ]

    for idx, row in enumerate(rows, start=2):
        case_id = (row.get("case_id") or "").strip() or f"ROW-{idx}"
        req_a_id = (row.get("req_a_id") or "").strip()
        req_b_id = (row.get("req_b_id") or "").strip()
        req_a_text = (row.get("req_a_text") or "").strip()
        req_b_text = (row.get("req_b_text") or "").strip()
        label = (row.get("label") or "").strip()
        split = (row.get("split") or "").strip()

        # 1. 필수 항목 누락 검사
        for col in required_non_empty:
            val = (row.get(col) or "").strip()
            if not val:
                errors.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "MISSING_VALUE",
                        "detail": f"필수 항목 '{col}' 값이 비어 있습니다.",
                    }
                )

        # 2. case_id 중복 검사
        raw_case_id = (row.get("case_id") or "").strip()
        if raw_case_id:
            if raw_case_id in seen_case_ids:
                errors.append(
                    {
                        "row": idx,
                        "case_id": raw_case_id,
                        "error_type": "DUPLICATE_CASE_ID",
                        "detail": f"case_id '{raw_case_id}'가 {seen_case_ids[raw_case_id]}행과 중복됩니다.",
                    }
                )
            else:
                seen_case_ids[raw_case_id] = idx

        # 3. 허용 분류값(label) 검사
        if label:
            if label not in VALID_LABELS:
                errors.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "INVALID_LABEL",
                        "detail": f"허용되지 않은 분류값 '{label}'입니다. (허용: {sorted(VALID_LABELS)})",
                    }
                )
            else:
                label_counts[label] += 1

        # 4. 요구사항 ID 참조 무결성 및 원문 대조 검사
        if req_a_id and req_a_id not in req_map:
            errors.append(
                {
                    "row": idx,
                    "case_id": case_id,
                    "error_type": "UNKNOWN_REQ_ID",
                    "detail": f"req_a_id '{req_a_id}'가 requirements 목록에 존재하지 않습니다.",
                }
            )
        elif req_a_id and check_text_mismatch and req_a_text:
            orig_a = req_map[req_a_id].get("req_text", "")
            if orig_a and req_a_text != orig_a:
                warnings.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "TEXT_MISMATCH_WARNING",
                        "detail": f"req_a_id '{req_a_id}'의 원문이 requirements 파일과 다릅니다.",
                    }
                )

        if req_b_id and req_b_id not in req_map:
            errors.append(
                {
                    "row": idx,
                    "case_id": case_id,
                    "error_type": "UNKNOWN_REQ_ID",
                    "detail": f"req_b_id '{req_b_id}'가 requirements 목록에 존재하지 않습니다.",
                }
            )
        elif req_b_id and check_text_mismatch and req_b_text:
            orig_b = req_map[req_b_id].get("req_text", "")
            if orig_b and req_b_text != orig_b:
                warnings.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "TEXT_MISMATCH_WARNING",
                        "detail": f"req_b_id '{req_b_id}'의 원문이 requirements 파일과 다릅니다.",
                    }
                )

        # 5. 자기 자신 비교 및 순서 무관 중복 요구사항 쌍 검사
        if req_a_id and req_b_id:
            if req_a_id == req_b_id:
                errors.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "SELF_PAIR",
                        "detail": f"동일한 요구사항('{req_a_id}')끼리 쌍으로 구성되었습니다.",
                    }
                )
            else:
                pair_key = tuple(sorted([req_a_id, req_b_id]))
                if pair_key in seen_pairs:
                    errors.append(
                        {
                            "row": idx,
                            "case_id": case_id,
                            "error_type": "DUPLICATE_PAIR",
                            "detail": f"요구사항 쌍 ({req_a_id}, {req_b_id})가 '{seen_pairs[pair_key]}'와 중복됩니다.",
                        }
                    )
                else:
                    seen_pairs[pair_key] = case_id

        # 6. 분할(split) 유효성 및 누수 추적
        if split:
            if split not in VALID_SPLITS:
                errors.append(
                    {
                        "row": idx,
                        "case_id": case_id,
                        "error_type": "INVALID_SPLIT",
                        "detail": f"허용되지 않은 split 값 '{split}'입니다. (허용: {sorted(VALID_SPLITS)})",
                    }
                )
            else:
                split_counts[split] += 1
                if label in VALID_LABELS:
                    split_label_counts[split][label] += 1
                if req_a_id:
                    req_id_to_splits[req_a_id].add(split)
                if req_b_id:
                    req_id_to_splits[req_b_id].add(split)

    # 7. 분할 간 동일 req_id 중복(데이터 누수) 검사
    for req_id, splits in sorted(req_id_to_splits.items()):
        if len(splits) > 1:
            errors.append(
                {
                    "row": "-",
                    "case_id": req_id,
                    "error_type": "DATA_LEAKAGE",
                    "detail": f"요구사항 '{req_id}'가 여러 분할({sorted(splits)})에 동시에 포함되어 데이터 누수가 발생했습니다.",
                }
            )

    return {
        "is_valid": len(errors) == 0,
        "total_rows": len(rows),
        "errors": errors,
        "warnings": warnings,
        "label_counts": dict(label_counts),
        "split_counts": dict(split_counts),
        "split_label_counts": {k: dict(v) for k, v in split_label_counts.items()},
    }


def save_error_report(errors: list[dict], output_path: Path) -> None:
    """검출된 오류 목록을 CSV 파일로 저장합니다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["row", "case_id", "error_type", "detail"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="RFP 요구사항 쌍 정답 데이터 검증기")
    parser.add_argument(
        "--req",
        type=Path,
        default=Path("src/data/output/requirements.csv"),
        help="요구사항 목록 파일 경로 (.csv 또는 .json)",
    )
    parser.add_argument(
        "--pairs",
        type=Path,
        default=Path("src/data/output/pairs_gt.csv"),
        help="검증할 정답 쌍 CSV 파일 경로",
    )
    parser.add_argument(
        "--error_out",
        type=Path,
        default=Path("src/data/output/validation_errors.csv"),
        help="오류 발견 시 저장할 CSV 경로",
    )
    parser.add_argument(
        "--ignore_text_mismatch",
        action="store_true",
        help="원문 텍스트 불일치 경고 무시",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("[데이터 검증 시작]")
    print(f"- 요구사항 목록: {args.req}")
    print(f"- 정답 쌍 파일 : {args.pairs}")
    print("=" * 60)

    req_map, req_errors = load_requirements(args.req)
    result = validate_pairs_csv(
        pairs_path=args.pairs,
        req_map=req_map,
        check_text_mismatch=not args.ignore_text_mismatch,
    )

    all_errors = req_errors + result["errors"]

    print(f"총 요구사항 수 : {len(req_map)}건")
    print(f"총 검사 쌍 수  : {result['total_rows']}건")
    print(f"전체 라벨 분포 : {result['label_counts']}")
    print(f"분할별 쌍 분포 : {result['split_counts']}")
    if result["split_label_counts"]:
        print("분할별 세부 라벨 분포:")
        for sp in ["train", "val", "test"]:
            if sp in result["split_label_counts"]:
                print(f"  - {sp:5s}: {result['split_label_counts'][sp]}")

    if result["warnings"]:
        print(f"\n[경고 {len(result['warnings'])}건]")
        for w in result["warnings"]:
            print(f"  - (행 {w['row']} | {w['case_id']}) [{w['error_type']}] {w['detail']}")

    if all_errors:
        print(f"\n[검증 실패] 총 {len(all_errors)}건의 오류가 발견되었습니다:")
        for err in all_errors:
            print(f"  - (행 {err['row']} | {err['case_id']}) [{err['error_type']}] {err['detail']}")
        save_error_report(all_errors, args.error_out)
        print(f"\n오류 목록 저장 완료 -> {args.error_out}")
        return 1

    print("\n[검증 통과] 형식, 라벨, ID 참조, 중복 쌍, 분할 데이터 누수 오류가 0건입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())