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


def parse_rfp(file_path: str | Path) -> list[dict[str, str]]:
    path = Path(file_path)
    doc_type = path.suffix[1:].upper()

    # 두 형식의 표를 (원문 위치, 행 목록, HWP 표 객체) 형태로 모읍니다.
    tables = []
    id_labels = {"요구사항번호", "요구사항고유번호"}

    if doc_type == "HWP":
        from hwpx import HwpxDocument

        doc = HwpxDocument.open(path)
        hwp_tables = doc.tables.with_nested

        # HWP 셀의 행·열 좌표를 사용해 표를 2차원 리스트로 구성합니다.
        # 원본 표 객체는 중첩 표를 읽을 때 사용합니다.
        for entry in doc.tables.map()["tables"]:
            rows = [[None] * entry["cols"] for _ in range(entry["rows"])]
            for cell in entry["cells"]:
                rows[cell["row"]][cell["col"]] = cell["text"]

            index = entry["table_index"]
            tables.append((f"표 {index + 1}", rows, hwp_tables[index]))

    elif doc_type == "PDF":
        import pdfplumber

        footer_labels = {"산출정보", "관련요구사항", "요구사항출처"}
        unfinished = None

        with pdfplumber.open(path) as doc:
            for page_number, page in enumerate(doc.pages, start=1):
                # 표의 셀을 읽고, 사용한 페이지의 좌표 캐시를 비웁니다.
                page_tables = page.extract_tables()
                page.close()

                for rows in page_tables:
                    labels = [
                        next(
                            (
                                "".join(cell.split())
                                for cell in row
                                if cell and cell.strip()
                            ),
                            "",
                        )
                        for row in rows
                    ]
                    headings = [
                        index
                        for index, label in enumerate(labels)
                        if label == "요구사항분류"
                    ]

                    # 다음 쪽의 표가 번호 없이 본문과 산출 정보로 끝나면
                    # 직전 쪽에서 끝나지 않은 요구사항의 연속으로 처리합니다.
                    if unfinished is not None and not headings:
                        previous_page, previous_index, previous_rows = unfinished
                        footer_start = next(
                            (
                                index
                                for index, label in enumerate(labels)
                                if label in footer_labels
                            ),
                            0,
                        )
                        body_rows = rows[:footer_start]

                        if (
                            page_number == previous_page + 1
                            and body_rows
                            and all(
                                len(row) >= 2
                                and not any(cell and cell.strip() for cell in row[:-1])
                                for row in body_rows
                            )
                        ):
                            previous_rows.extend(
                                ["세부내용", row[-1]]
                                for row in body_rows
                                if row[-1] and row[-1].strip()
                            )
                            tables[previous_index] = (
                                f"p.{previous_page}–{page_number}",
                                previous_rows,
                                None,
                            )
                            unfinished = None
                            continue

                    # 붙어 있는 표가 하나로 감지되면 새 분류 행에서 나눕니다.
                    boundaries = [0, *headings[1:], len(rows)]
                    for start, end in zip(boundaries, boundaries[1:]):
                        section = rows[start:end]
                        section_labels = set(labels[start:end])

                        if section_labels & id_labels:
                            unfinished = None
                            if not section_labels & footer_labels:
                                unfinished = (page_number, len(tables), section)

                        tables.append((f"p.{page_number}", section, None))

    else:
        raise ValueError("지원 형식은 .hwp와 .pdf입니다.")

    detail_labels = {"요구사항상세내용", "상세내용", "요구사항세부내용", "세부내용"}
    result = []
    seen_source_ids = set()

    # 표 하나를 요구사항 한 건의 후보로 보고 번호와 상세내용을 찾습니다.
    for location, rows, hwp_table in tables:
        source_ids = set()
        details = []

        for row_number, row in enumerate(rows):
            for col, cell_text in enumerate(row[:-1]):
                # 라벨에 들어간 공백과 줄바꿈을 무시해 같은 항목명으로 인식합니다.
                label = "".join((cell_text or "").split())
                if label not in id_labels and label not in detail_labels:
                    continue

                # 같은 행에서 라벨 오른쪽의 첫 번째 비어 있지 않은 셀을 값으로 사용합니다.
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

                # HWP 본문에 작은 표가 들어 있으면 그 텍스트도 본문에 포함합니다.
                # 각 행은 줄바꿈, 행 안의 셀은 탭으로 구분합니다.
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

        # 두 항목이 모두 없는 일반 표는 건너뜁니다.
        # 요구사항 후보에는 원본 번호 하나와 상세내용이 필요합니다.
        if not source_ids and not details:
            continue
        if len(source_ids) != 1 or not details:
            raise ValueError(
                f"{location}에서 요구사항 번호와 상세내용을 짝지을 수 없습니다."
            )

        # 원본 번호로 문서 안의 중복을 확인하고, 출력용 req_id는 순서대로 붙입니다.
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
    import sys
    from tempfile import TemporaryDirectory

    # 현재 터미널 위치와 상관없이 이 스크립트가 있는 src/에서 data/를 찾습니다.
    data_dir = Path(__file__).resolve().parent / "data"
    input_dir = data_dir / "input"
    output_dir = data_dir / "output"

    if not input_dir.is_dir():
        raise SystemExit(f"입력 폴더를 찾을 수 없습니다. {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    failed = 0

    # input 폴더 바로 아래의 HWP·PDF 파일을 이름순으로 확인합니다.
    for source_path in sorted(input_dir.iterdir()):
        suffix = source_path.suffix.lower()
        if not source_path.is_file() or suffix not in {".hwp", ".pdf"}:
            continue

        # HWP는 기존 JSON 이름을 사용하고, PDF는 .pdf를 남겨 같은 제목의 HWP와 구분합니다.
        output_name = source_path.stem if suffix == ".hwp" else source_path.name
        output_path = output_dir / f"{output_name}.requirements.json"

        # 대응하는 JSON이 있으면 해당 입력의 파싱을 생략합니다.
        if output_path.is_file():
            print(f"건너뜀 {source_path.name} → {output_path.name}")
            skipped += 1
            continue

        try:
            result = parse_rfp(source_path)

            # JSON을 임시 파일에 모두 쓴 뒤 결과 경로로 옮깁니다.
            # 쓰기가 실패하면 최종 경로에 미완성 JSON이 남지 않습니다.
            with TemporaryDirectory(dir=output_dir) as temp_dir:
                temp_path = Path(temp_dir) / output_path.name
                with temp_path.open("w", encoding="utf-8") as output_file:
                    json.dump(result, output_file, ensure_ascii=False, indent=2)
                    output_file.write("\n")

                temp_path.replace(output_path)

        except Exception as error:
            # 개별 파일의 오류를 기록한 뒤 다음 입력을 처리합니다.
            print(f"실패 {source_path.name} → {error}", file=sys.stderr)
            failed += 1
            continue

        print(f"저장 {source_path.name} → {output_path.name} ({len(result)}건)")
        created += 1

    print(f"파일 기준 · 생성 {created}개 · 건너뜀 {skipped}개 · 실패 {failed}개")

    # 전체 처리를 마친 뒤 실패가 있었다면 종료 코드 1로 알립니다.
    if failed:
        raise SystemExit(1)
