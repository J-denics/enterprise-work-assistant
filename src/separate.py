# 요구사항을 70 : 15 : 15로 먼저 분리하고 초안 생성

import itertools
import json
import random
from pathlib import Path
import pandas as pd

# 1. document_parser.py가 생성한 JSON 읽기
json_path = Path("src/data/output/제안요청서.requirements.json")
with json_path.open("r", encoding="utf-8") as f:
    req_list = json.load(f)

df_req = pd.DataFrame(req_list)

# 2. requirements.csv 저장 (표준 5개 컬럼 그대로 유지)
req_csv_path = Path("src/data/output/requirements.csv")
df_req.to_csv(req_csv_path, index=False, encoding="utf-8-sig")
print(f"[1] requirements.csv 저장 완료: {len(df_req)}건 -> {req_csv_path}")

# 3. 원본 req_id를 먼저 70 : 15 : 15로 분리 (데이터 누수 방지)
random.seed(42)
all_ids = df_req["req_id"].tolist()
random.shuffle(all_ids)

n = len(all_ids)
n_train = int(n * 0.7)
n_val = int(n * 0.15)

splits = {
    "train": all_ids[:n_train],
    "val": all_ids[n_train : n_train + n_val],
    "test": all_ids[n_train + n_val :],
}

req_text_map = dict(zip(df_req["req_id"], df_req["req_text"]))

# 4. 각 분할 내부에서만 쌍(Pair) 후보 생성 (라벨링 작업용 초안)
# 전체 조합이 너무 많을 수 있으므로 각 분할별 최대 40쌍(총 ~60~80쌍) 샘플링
max_pairs_per_split = {"train": 50, "val": 15, "test": 15}
pair_rows = []
case_idx = 1

for split_name, id_group in splits.items():
    combos = list(itertools.combinations(sorted(id_group), 2))
    random.shuffle(combos)
    selected = combos[: max_pairs_per_split[split_name]]

    for req_a_id, req_b_id in selected:
        pair_rows.append(
            {
                "case_id": f"CASE-{case_idx:03d}",
                "req_a_id": req_a_id,
                "req_a_text": req_text_map[req_a_id],
                "req_b_id": req_b_id,
                "req_b_text": req_text_map[req_b_id],
                "label": "",           # '중복', '유사·관련', '무관' 중 입력
                "reason": "",          # 판정 근거 입력
                "diff_conditions": "", # 차이점 입력 (없으면 '없음')
                "split": split_name,
            }
        )
        case_idx += 1

df_pairs_draft = pd.DataFrame(pair_rows)
draft_csv_path = Path("src/data/output/pairs_gt_draft.csv")
df_pairs_draft.to_csv(draft_csv_path, index=False, encoding="utf-8-sig")

print(f"[2] pairs_gt_draft.csv 생성 완료: 총 {len(df_pairs_draft)}쌍 -> {draft_csv_path}")
print("    분할별 요구사항 수:", {k: len(v) for k, v in splits.items()})
print("    분할별 쌍 후보 수:", df_pairs_draft["split"].value_counts().to_dict())