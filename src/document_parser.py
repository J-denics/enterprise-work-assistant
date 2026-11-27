"""
담당: 팀원2 — 문서 처리·화면
이 파일은 PDF·HWP에서 텍스트와 원문 위치를 추출하는 기능을 구현하기 위해 만들어졌습니다.
입력: 텍스트 추출이 가능한 PDF 또는 HWP 파일
출력: 문서명, 문서 형식, 원문 위치, 추출 텍스트를 담은 공통 데이터
구현할 내용: 형식별 추출, 표 내용 확인, 추출 실패 안내
PDF는 페이지를, HWP는 확보 가능한 절·문단·표 위치를 보존합니다.
HWP를 PDF로 변환하는 경우 페이지 번호가 변환본 기준임을 표시합니다.
"""

import re
from pathlib import Path

# import json
# from typing import Literal, TypedDict


# class ExtractedBlock(TypedDict):
#     document_name: str
#     document_format: Literal["pdf", "hwp"]
#     source_location: dict[str, int | str]
#     text: str


def parse_rfp(file_path: str | Path) -> list[dict[str, str]]:
    path = Path(file_path)
    doc_type = path.suffix[1:].upper()
    tables = []

    if doc_type == "HWP":
        from hwpx import HwpxDocument

        doc = HwpxDocument.open(path)
        hwp_tables = doc.tables.with_nested

        for entry in doc.tables.map()["tables"]:
            rows = [[None] * entry["cols"] for _ in range(entry["rows"])]
            for cell in entry["cells"]:
                rows[cell["row"]][cell["col"]] = cell["text"]

            index = entry["table_index"]
            tables.append((f"표 {index + 1}", rows, hwp_tables[index]))

    elif doc_type == "PDF":
        import pymupdf

        with pymupdf.open(path) as doc:
            for page_number, page in enumerate(doc, start=1):
                for table in page.find_tables().tables:
                    tables.append((f"p.{page_number}", table.extract(), None))

    else:
        raise ValueError("지원 형식은 .hwp와 .pdf입니다.")

    id_labels = {"요구사항번호", "요구사항고유번호"}
    detail_labels = {"요구사항상세내용", "상세내용", "요구사항세부내용", "세부내용"}
    result = []
    seen_source_ids = set()

    for location, rows, hwp_table in tables:
        source_ids = set()
        details = []

        for row_number, row in enumerate(rows):
            for col, cell_text in enumerate(row[:-1]):
                label = "".join((cell_text or "").split())
                if label not in id_labels and label not in detail_labels:
                    continue

                for value_col in range(col + 1, len(row)):
                    value = row[value_col]
                    if value and value.strip():
                        break
                else:
                    continue

                if label in id_labels:
                    source_id = "".join(value.split())
                    if re.fullmatch(r"[A-Z]+-[0-9]+", source_id):
                        source_ids.add(source_id)
                    continue

                if hwp_table is not None:
                    cell = hwp_table.cell(row_number, value_col)
                    if cell.tables:
                        parts = []
                        for paragraph in cell.paragraphs:
                            parts.append(paragraph.text or "")
                            for nested in paragraph.tables:
                                parts.extend(
                                    "\t".join(c.text for c in nested_row.cells)
                                    for nested_row in nested.rows
                                )
                        value = "\n".join(parts)

                details.append(value)

        if not source_ids and not details:
            continue
        if len(source_ids) != 1 or not details:
            raise ValueError(
                f"{location}에서 요구사항 번호와 상세내용을 짝지을 수 없습니다."
            )

        source_id = next(iter(source_ids))
        if source_id in seen_source_ids:
            raise ValueError(f"{location}에서 요구사항 {source_id}가 반복됩니다.")
        seen_source_ids.add(source_id)

        result.append(
            {
                "req_id": f"REQ-{len(result) + 1:03d}",
                "doc_name": path.name,
                "doc_type": doc_type,
                "source_location": location,
                "req_text": "\n".join(details),
            }
        )

    if not result:
        raise ValueError(
            "문서에서 요구사항 번호와 상세내용이 있는 표를 찾지 못했습니다."
        )

    return result


if __name__ == "__main__":
    import json

    data_dir = Path(__file__).resolve().parent / "data"
    source_path = data_dir / "input" / "제안요청서.hwp"
    result = parse_rfp(source_path)

    output_dir = data_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.requirements.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    print(f"{len(result)}건 저장 → {output_path}")
