"""
담당: 팀원2 — 문서 처리·화면
이 파일은 문서 업로드와 분석 결과 조회 화면을 구현하기 위해 만들어졌습니다.
입력: PDF·HWP 파일 및 그룹화·요약 결과 JSON
출력: 그룹별 결과표, 원문 위치 표시, 다운로드 가능한 CSV
구현할 내용: Streamlit 업로드 화면, 처리 상태·오류 안내, 결과 조회 및 다운로드
모델 완성 전에는 합의한 형식의 샘플 JSON으로 화면을 개발합니다.
"""

import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

import streamlit as st

from document_parser import parse_rfp


class GroupResult(TypedDict):
    """그룹 결과 화면과 CSV 다운로드에 필요한 필드와 타입을 정의합니다."""

    group_id: str
    group_name: str
    summary: str
    req_ids: list[str]
    diff_conditions: str
    source_locations: list[str]


# 딕셔너리의 키는 CSV 열 이름으로, 값은 화면에 표시할 한글 제목으로 사용합니다.
# 이 순서를 기준으로 CSV의 열 순서도 정해집니다.
GROUP_COLUMNS = {
    "group_id": "그룹 ID",
    "group_name": "그룹 이름",
    "summary": "요약",
    "req_ids": "포함 요구사항 ID",
    "diff_conditions": "조건 차이",
    "source_locations": "원문 위치",
}

# 그룹화 코드가 연결되기 전까지 결과 화면과 CSV 다운로드를 확인하는 예시입니다.
# G-001은 요구사항 두 건이 묶인 경우, G-002는 한 건만 포함된 경우입니다.
DEMO_GROUPS: list[GroupResult] = [
    {
        "group_id": "G-001",
        "group_name": "관리자 접근 관리",
        "summary": "관리자 접근을 제어하고 접근 기록을 보관합니다.",
        "req_ids": ["REQ-001", "REQ-004"],
        "diff_conditions": "REQ-001은 관리자 로그인 인증을, REQ-004는 접근 기록 1년 보관을 요구합니다.",
        "source_locations": ["p.12", "p.15"],
    },
    {
        "group_id": "G-002",
        "group_name": "데이터 백업",
        "summary": "데이터를 매일 백업합니다.",
        "req_ids": ["REQ-002"],
        "diff_conditions": "",
        "source_locations": ["p.13"],
    },
]


def parse_uploaded_file(filename: str, content: bytes) -> list[dict]:
    """업로드한 파일을 기존 파서에 넘기고 요구사항 목록을 반환합니다."""

    # 확장자를 소문자로 바꿔 .PDF나 .HWP처럼 대문자로 끝나는 파일도 처리합니다.
    # 이 함수가 별도로 호출되는 경우에도 지원 형식과 빈 파일을 검사합니다.
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".hwp"}:
        raise ValueError("PDF 또는 HWP 파일을 선택해 주세요.")
    if not content:
        raise ValueError("파일이 비어 있습니다.")

    # Streamlit에서 읽은 파일 내용은 bytes이고, parse_rfp()는 파일 경로를 받습니다.
    # 따라서 내용을 임시 파일에 저장한 뒤 그 경로를 파서에 전달합니다.
    # 파서가 확장자로 PDF와 HWP를 구분하므로 임시 파일에도 확장자를 붙입니다.
    with TemporaryDirectory(prefix="reqcheck-") as directory:
        path = Path(directory) / f"upload{suffix}"
        path.write_bytes(content)
        requirements = parse_rfp(path)

    # with 블록을 벗어나면 임시 파일은 자동으로 삭제됩니다.
    # 결과의 문서 이름은 사용자가 업로드한 실제 파일명으로 돌려놓습니다.
    for requirement in requirements:
        requirement["doc_name"] = filename
    return requirements


def clear_extraction() -> None:
    """이전 추출 결과와 화면에서 선택했던 요구사항을 지웁니다."""

    # 다른 파일을 선택하거나 추출을 다시 시작할 때 호출합니다.
    # 추출에 실패하더라도 앞서 성공한 결과가 화면에 남아 혼동되는 일을 막습니다.
    st.session_state.pop("requirements", None)
    st.session_state.pop("requirement_id", None)


def render_requirements(requirements: list[dict]) -> None:
    """전체 요구사항을 표로 표시하고, 선택한 한 건의 상세 본문을 보여줍니다."""

    # req_id는 파서가 REQ-001 형태로 붙인 내부 ID입니다.
    # source_req_id는 SFR-001처럼 실제 문서에 인쇄된 번호라 원문 검색에 쓸 수 있습니다.
    st.subheader(f"추출한 요구사항 {len(requirements)}건")
    st.dataframe(
        [
            {
                "추출 ID": requirement["req_id"],
                "원문 번호": requirement["source_req_id"],
                "원문 위치": requirement["source_location"],
            }
            for requirement in requirements
        ],
        hide_index=True,
    )
    st.caption("PDF 위치는 파일의 페이지 번호, HWP 위치는 추출된 표의 순번입니다.")

    # 선택 상자는 내부 ID를 값으로 사용합니다.
    # 화면에는 원문 번호와 위치를 표시해 사용자가 항목을 쉽게 구분할 수 있게 합니다.
    by_id = {requirement["req_id"]: requirement for requirement in requirements}
    selected_id = st.selectbox(
        "본문을 볼 요구사항",
        options=list(by_id),
        format_func=lambda req_id: (
            f"{by_id[req_id]['source_req_id']} · {by_id[req_id]['source_location']}"
        ),
        key="requirement_id",
    )
    requirement = by_id[selected_id]

    # 기본으로 정리된 본문을 보여주고, 선택한 항목에 대한 파서 경고를 함께 표시합니다.
    # 정리 과정에서 본문이 달라졌다면 펼침 영역에서 정리 전 추출문을 대조할 수 있습니다.
    st.text(requirement["req_text"])
    for warning in requirement["warnings"]:
        st.warning(warning)
    if requirement["raw_req_text"] != requirement["req_text"]:
        with st.expander("정리 전 추출 본문"):
            st.text(requirement["raw_req_text"])


def group_rows(groups: list[GroupResult]) -> list[dict[str, str]]:
    """그룹 데이터를 화면과 CSV에서 함께 사용할 수 있는 행으로 변환합니다."""

    # 그룹 하나가 표의 한 행이 됩니다. 여러 요구사항 ID는 한 셀에 저장합니다.
    # 평가 코드가 |로 구분된 req_ids를 읽으므로 REQ-001|REQ-004 형식으로 만듭니다.
    return [
        {
            "group_id": group["group_id"],
            "group_name": group["group_name"],
            "summary": group["summary"],
            "req_ids": "|".join(group["req_ids"]),
            "diff_conditions": group["diff_conditions"],
            "source_locations": " | ".join(group["source_locations"]),
        }
        for group in groups
    ]


def group_csv(rows: list[dict[str, str]]) -> bytes:
    """그룹별 결과를 다운로드 버튼에 전달할 CSV 바이트로 변환합니다."""

    # StringIO를 사용해 메모리에서 CSV를 만듭니다.
    # DictWriter는 요약문에 쉼표나 줄바꿈이 들어가도 셀 하나로 읽히도록 처리합니다.
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(GROUP_COLUMNS))
    writer.writeheader()
    writer.writerows(rows)

    # UTF-8 BOM을 붙여 Excel에서 한글 인코딩을 인식하기 쉽게 합니다.
    return buffer.getvalue().encode("utf-8-sig")


def main() -> None:
    """업로드·추출 탭과 그룹 결과 예시 탭을 구성합니다."""

    st.set_page_config(page_title="ReqCheck", layout="wide")
    st.title("ReqCheck")
    extraction_tab, demo_tab = st.tabs(["요구사항 추출", "그룹 결과 예시"])

    with extraction_tab:
        # 파일을 고르면 Streamlit이 파일 객체를 반환합니다.
        # 선택한 파일이 바뀌거나 제거되면 on_change가 이전 결과를 지웁니다.
        uploaded_file = st.file_uploader(
            "제안요청서 업로드",
            type=["pdf", "hwp"],
            on_change=clear_extraction,
        )

        # 파일을 선택한 뒤 버튼을 눌렀을 때만 파서를 호출합니다.
        # name은 파일명이고, getvalue()는 업로드한 파일의 실제 바이트입니다.
        if st.button("요구사항 추출", disabled=uploaded_file is None, type="primary"):
            clear_extraction()
            try:
                with st.spinner("요구사항을 추출하고 있어요."):
                    st.session_state["requirements"] = parse_uploaded_file(
                        uploaded_file.name, uploaded_file.getvalue()
                    )
            except Exception as error:
                st.error(f"요구사항을 추출하지 못했습니다. {error}")

        # Streamlit은 사용자가 다른 요구사항을 선택할 때도 스크립트를 다시 실행합니다.
        # 추출 결과를 session_state에 저장해 두면 파일을 다시 파싱하지 않고 본문을 바꿔 볼 수 있습니다.
        requirements = st.session_state.get("requirements")
        if requirements:
            render_requirements(requirements)

    with demo_tab:
        # 이 탭은 업로드한 파일과 별도로 동작합니다.
        # 같은 예시 행을 화면에 표시하고 CSV로도 내려받을 수 있게 합니다.
        st.caption("화면과 CSV 형식을 확인하기 위한 예시입니다.")
        rows = group_rows(DEMO_GROUPS)
        st.dataframe(rows, column_config=GROUP_COLUMNS, hide_index=True)
        st.download_button(
            "예시 CSV 다운로드",
            data=group_csv(rows),
            file_name="reqcheck-demo-groups.csv",
            mime="text/csv",
            on_click="ignore",
        )


if __name__ == "__main__":
    main()
