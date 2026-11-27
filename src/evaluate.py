"""
담당: 팀원1 — 데이터 검증·평가
이 파일은 모델 예측을 정답과 비교해 평가 점수를 계산하는 기능을 구현하기 위해 만들어졌습니다.
입력: 정답 CSV 및 모델 예측 CSV (단일 모델 또는 파인튜닝 전후 2개 모델 비교)
출력: 정확도(Accuracy), 3개 분류의 Macro F1, 클래스별 F1, 혼동행렬, 오분류 및 누락 사례, 추적 가능성 검증
구현할 내용: 사례 ID로 정답과 예측 연결, 누락·중복 ID 검사, 학습 전후 성능 비교
"""

import argparse
import csv
import json
import sys
from pathlib import Path

CLASSES = ["중복", "유사·관련", "무관"]
VALID_LABELS = set(CLASSES)

TARGET_MACRO_F1 = 0.75
TARGET_IMPROVEMENT = 0.05


def load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV 헤더가 비어 있습니다: {path}")
        return list(reader.fieldnames), list(reader)


def load_ground_truth(gt_path: Path, target_split: str = "test") -> dict[str, dict[str, str]]:
    """정답 CSV를 로드하고 target_split('test' 또는 'all')에 해당하는 case_id 맵을 반환합니다."""
    fieldnames, rows = load_csv_rows(gt_path)
    required = {"case_id", "label"}
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"정답 CSV에 필수 컬럼이 없습니다: {sorted(missing)}")

    gt_map: dict[str, dict[str, str]] = {}
    for idx, row in enumerate(rows, start=2):
        case_id = (row.get("case_id") or "").strip()
        label = (row.get("label") or "").strip()
        split = (row.get("split") or "").strip()

        if not case_id:
            raise ValueError(f"정답 CSV {idx}행의 case_id가 비어 있습니다.")
        if target_split != "all" and split != target_split:
            continue
        if label not in VALID_LABELS:
            raise ValueError(
                f"정답 CSV {idx}행({case_id})에 잘못된 라벨 '{label}'이 있습니다. (허용: {CLASSES})"
            )
        if case_id in gt_map:
            raise ValueError(f"정답 CSV에 중복된 case_id '{case_id}'가 있습니다.")

        gt_map[case_id] = {k: (v or "").strip() for k, v in row.items()}

    if not gt_map:
        raise ValueError(
            f"정답 CSV에서 split='{target_split}'에 해당하는 평가 대상 행을 찾지 못했습니다."
        )
    return gt_map


def evaluate_single_predictions(
    gt_map: dict[str, dict[str, str]],
    pred_path: Path,
    model_name: str = "Model",
) -> dict:
    """단일 예측 CSV를 정답 맵과 비교하여 Accuracy, Macro F1, 오분류 목록 등을 계산합니다."""
    fieldnames, rows = load_csv_rows(pred_path)
    required = {"case_id", "pred_label"}
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"[{model_name}] 예측 CSV에 필수 컬럼이 없습니다: {sorted(missing)}")

    pred_map: dict[str, dict[str, str]] = {}
    duplicate_pred_ids: list[str] = []
    invalid_pred_labels: list[tuple[str, str]] = []
    extra_pred_ids: list[str] = []

    for idx, row in enumerate(rows, start=2):
        case_id = (row.get("case_id") or "").strip()
        pred_label = (row.get("pred_label") or "").strip()

        if not case_id:
            continue
        if case_id in pred_map:
            duplicate_pred_ids.append(case_id)
            continue
        if case_id not in gt_map:
            extra_pred_ids.append(case_id)
            continue
        if pred_label not in VALID_LABELS:
            invalid_pred_labels.append((case_id, pred_label))

        pred_map[case_id] = {k: (v or "").strip() for k, v in row.items()}

    missing_pred_ids = sorted(set(gt_map.keys()) - set(pred_map.keys()))

    # 혼동 행렬 초기화: confusion[gt][pred]
    confusion: dict[str, dict[str, int]] = {
        gt_cls: {pred_cls: 0 for pred_cls in CLASSES} for gt_cls in CLASSES
    }

    correct = 0
    evaluated_count = 0
    error_cases: list[dict[str, str]] = []

    for case_id, gt_row in gt_map.items():
        if case_id not in pred_map:
            continue

        pred_row = pred_map[case_id]
        y_true = gt_row["label"]
        y_pred = pred_row["pred_label"]

        if y_pred not in VALID_LABELS:
            continue

        evaluated_count += 1
        confusion[y_true][y_pred] += 1

        if y_true == y_pred:
            correct += 1
        else:
            error_cases.append(
                {
                    "model": model_name,
                    "case_id": case_id,
                    "req_a_id": gt_row.get("req_a_id", ""),
                    "req_b_id": gt_row.get("req_b_id", ""),
                    "gt_label": y_true,
                    "pred_label": y_pred,
                    "gt_reason": gt_row.get("reason", ""),
                    "pred_reason": pred_row.get("pred_reason", ""),
                    "gt_diff_conditions": gt_row.get("diff_conditions", ""),
                    "pred_diff_conditions": pred_row.get("pred_diff_conditions", ""),
                    "req_a_text": gt_row.get("req_a_text", ""),
                    "req_b_text": gt_row.get("req_b_text", ""),
                }
            )

    accuracy = (correct / evaluated_count) if evaluated_count > 0 else 0.0

    per_class: dict[str, dict[str, float | int]] = {}
    f1_list: list[float] = []

    for cls in CLASSES:
        tp = confusion[cls][cls]
        fp = sum(confusion[other][cls] for other in CLASSES if other != cls)
        fn = sum(confusion[cls][other] for other in CLASSES if other != cls)
        support = sum(confusion[cls].values())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        per_class[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(CLASSES)

    return {
        "model_name": model_name,
        "pred_path": str(pred_path),
        "gt_total": len(gt_map),
        "evaluated_count": evaluated_count,
        "correct": correct,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion": confusion,
        "missing_pred_ids": missing_pred_ids,
        "duplicate_pred_ids": sorted(set(duplicate_pred_ids)),
        "extra_pred_ids": sorted(set(extra_pred_ids)),
        "invalid_pred_labels": invalid_pred_labels,
        "error_cases": error_cases,
    }


def print_single_report(res: dict) -> None:
    print("\n" + "-" * 60)
    print(f"[{res['model_name']} 평가 결과] ({res['pred_path']})")
    print("-" * 60)
    print(f"- 평가 대상 수 : {res['evaluated_count']} / {res['gt_total']}건 (정답 일치: {res['correct']}건)")
    print(f"- Accuracy     : {res['accuracy']:.4f} ({res['accuracy'] * 100:.2f}%)")
    print(f"- Macro F1     : {res['macro_f1']:.4f} (목표 기준 >= {TARGET_MACRO_F1:.2f})")

    if res["missing_pred_ids"]:
        print(f"- [경고] 예측 누락 case_id ({len(res['missing_pred_ids'])}건): {res['missing_pred_ids']}")
    if res["duplicate_pred_ids"]:
        print(f"- [경고] 예측 중복 case_id ({len(res['duplicate_pred_ids'])}건): {res['duplicate_pred_ids']}")
    if res["invalid_pred_labels"]:
        print(f"- [경고] 잘못된 pred_label ({len(res['invalid_pred_labels'])}건): {res['invalid_pred_labels']}")

    print("\n[클래스별 상세 성능]")
    print(f"{'클래스':<12} {'Precision':>10} {'Recall':>10} {'F1-Score':>10} {'Support':>9}")
    for cls in CLASSES:
        m = res["per_class"][cls]
        print(
            f"{cls:<12} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>9d}"
        )

    print("\n[혼동 행렬 (행: 정답 / 열: 예측)]")
    corner = "정답 / 예측"
    header = f"{corner:<12}" + "".join(f"{c:>12}" for c in CLASSES)
    print(header)
    for gt_cls in CLASSES:
        row_str = f"{gt_cls:<12}" + "".join(
            f"{res['confusion'][gt_cls][p_cls]:>12d}" for p_cls in CLASSES
        )
        print(row_str)


def check_traceability(req_path: Path, final_results_path: Path) -> dict:
    """최종 결과 CSV에 원본 요구사항 ID가 100% 누락 없이 포함되었는지 검증합니다."""
    if req_path.suffix.lower() == ".json":
        with req_path.open("r", encoding="utf-8") as f:
            req_rows = json.load(f)
    else:
        _, req_rows = load_csv_rows(req_path)

    expected_ids = {(r.get("req_id") or "").strip() for r in req_rows if (r.get("req_id") or "").strip()}

    fieldnames, res_rows = load_csv_rows(final_results_path)
    if "req_ids" not in fieldnames:
        raise ValueError(f"최종 결과 CSV에 'req_ids' 컬럼이 없습니다: {final_results_path}")

    covered_ids: set[str] = set()
    for row in res_rows:
        raw_ids = (row.get("req_ids") or "").strip()
        if not raw_ids:
            continue
        for token in raw_ids.split("|"):
            rid = token.strip()
            if rid:
                covered_ids.add(rid)

    missing_ids = sorted(expected_ids - covered_ids)
    unknown_ids = sorted(covered_ids - expected_ids)
    coverage_rate = (len(expected_ids & covered_ids) / len(expected_ids)) if expected_ids else 0.0

    print("\n" + "=" * 60)
    print("[최종 결과 CSV 추적 가능성(Traceability) 검증]")
    print("=" * 60)
    print(f"- 원본 요구사항 수 : {len(expected_ids)}건")
    print(f"- 결과 반영 ID 수  : {len(expected_ids & covered_ids)}건 (반영률: {coverage_rate * 100:.1f}%)")
    if missing_ids:
        print(f"- [누락된 req_id]  : {missing_ids}")
    if unknown_ids:
        print(f"- [미등록 req_id]  : {unknown_ids}")
    if not missing_ids and not unknown_ids:
        print("- [통과] 모든 원본 요구사항이 그룹 또는 단독 항목으로 100% 연결되었습니다.")

    return {
        "expected_count": len(expected_ids),
        "covered_count": len(expected_ids & covered_ids),
        "coverage_rate": coverage_rate,
        "missing_ids": missing_ids,
        "unknown_ids": unknown_ids,
    }


def save_error_cases(error_cases: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model",
        "case_id",
        "req_a_id",
        "req_b_id",
        "gt_label",
        "pred_label",
        "gt_reason",
        "pred_reason",
        "gt_diff_conditions",
        "pred_diff_conditions",
        "req_a_text",
        "req_b_text",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(error_cases)


def main() -> int:
    parser = argparse.ArgumentParser(description="RFP 요구사항 관계 분류 모델 성능 평가기")
    parser.add_argument(
        "--gt",
        type=Path,
        default=Path("src/data/output/pairs_gt.csv"),
        help="정답 쌍 CSV 경로",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["test", "val", "train", "all"],
        help="평가에 사용할 split 구분 (기본값: test)",
    )
    parser.add_argument(
        "--pred",
        type=Path,
        default=None,
        help="단일 예측 CSV 경로 (단독 평가 시 사용)",
    )
    parser.add_argument(
        "--base_pred",
        type=Path,
        default=Path("src/data/output/base_pred.csv"),
        help="파인튜닝 전 Base 모델 예측 CSV 경로",
    )
    parser.add_argument(
        "--ft_pred",
        type=Path,
        default=Path("src/data/output/ft_pred.csv"),
        help="파인튜닝 후 QLoRA 모델 예측 CSV 경로",
    )
    parser.add_argument(
        "--error_out",
        type=Path,
        default=Path("src/data/output/error_cases.csv"),
        help="오분류 사례 저장 CSV 경로",
    )
    parser.add_argument(
        "--report_out",
        type=Path,
        default=Path("src/data/output/eval_report.json"),
        help="평가 요약 JSON 저장 경로",
    )
    parser.add_argument(
        "--req",
        type=Path,
        default=None,
        help="(선택) 추적 가능성 검증용 원본 requirements.csv/.json 경로",
    )
    parser.add_argument(
        "--final_results",
        type=Path,
        default=None,
        help="(선택) 추적 가능성 검증용 최종 결과 final_results.csv 경로",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("[모델 예측 성능 평가 시작]")
    print(f"- 정답 파일 : {args.gt} (대상 split: {args.split})")
    print("=" * 60)

    gt_map = load_ground_truth(args.gt, target_split=args.split)

    all_errors: list[dict[str, str]] = []
    report_summary: dict = {"gt_path": str(args.gt), "split": args.split, "gt_count": len(gt_map)}

    if args.pred is not None:
        res = evaluate_single_predictions(gt_map, args.pred, model_name="Model")
        print_single_report(res)
        all_errors.extend(res["error_cases"])
        report_summary["model"] = {k: v for k, v in res.items() if k != "error_cases"}
    else:
        has_base = args.base_pred.exists()
        has_ft = args.ft_pred.exists()

        if not has_base and not has_ft:
            raise FileNotFoundError(
                f"예측 파일을 찾을 수 없습니다. --pred 또는 --base_pred / --ft_pred 경로를 확인하세요.\n"
                f"  확인한 경로: {args.base_pred}, {args.ft_pred}"
            )

        base_res = None
        ft_res = None

        if has_base:
            base_res = evaluate_single_predictions(gt_map, args.base_pred, model_name="Base_Model")
            print_single_report(base_res)
            all_errors.extend(base_res["error_cases"])
            report_summary["base_model"] = {k: v for k, v in base_res.items() if k != "error_cases"}

        if has_ft:
            ft_res = evaluate_single_predictions(gt_map, args.ft_pred, model_name="FineTuned_QLoRA")
            print_single_report(ft_res)
            all_errors.extend(ft_res["error_cases"])
            report_summary["ft_model"] = {k: v for k, v in ft_res.items() if k != "error_cases"}

        if base_res and ft_res:
            acc_diff = ft_res["accuracy"] - base_res["accuracy"]
            f1_diff = ft_res["macro_f1"] - base_res["macro_f1"]
            goal_f1_ok = ft_res["macro_f1"] >= TARGET_MACRO_F1
            goal_imp_ok = f1_diff >= TARGET_IMPROVEMENT

            print("\n" + "=" * 60)
            print("[파인튜닝 전후 성능 비교 요약]")
            print("=" * 60)
            print(
                f"- Accuracy : Base {base_res['accuracy']:.4f} -> FT {ft_res['accuracy']:.4f} "
                f"(변화: {acc_diff:+.4f})"
            )
            print(
                f"- Macro F1 : Base {base_res['macro_f1']:.4f} -> FT {ft_res['macro_f1']:.4f} "
                f"(변화: {f1_diff:+.4f})"
            )
            print(
                f"- 목표1 (FT Macro F1 >= {TARGET_MACRO_F1:.2f})   : "
                f"{'달성 (PASS)' if goal_f1_ok else '미달 (FAIL)'}"
            )
            print(
                f"- 목표2 (향상 폭 >= +{TARGET_IMPROVEMENT:.2f})     : "
                f"{'달성 (PASS)' if goal_imp_ok else '미달 (FAIL)'}"
            )

            report_summary["comparison"] = {
                "accuracy_diff": acc_diff,
                "macro_f1_diff": f1_diff,
                "target_macro_f1_passed": goal_f1_ok,
                "target_improvement_passed": goal_imp_ok,
            }

    if all_errors:
        save_error_cases(all_errors, args.error_out)
        print(f"\n[오분류 리포트] 총 {len(all_errors)}건 저장 완료 -> {args.error_out}")
    else:
        print("\n[오분류 리포트] 오분류 사례가 0건입니다.")

    if args.req and args.final_results:
        trace_res = check_traceability(args.req, args.final_results)
        report_summary["traceability"] = trace_res

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    with args.report_out.open("w", encoding="utf-8") as f:
        json.dump(report_summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[평가 요약 JSON] 저장 완료 -> {args.report_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())