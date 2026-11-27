# RFP 파서 실행 가이드

공유받은 프로젝트의 샘플 한글 파일에서 요구사항을 추출해, 내 컴퓨터에 JSON으로 저장하는 절차입니다.

## 1. 프로젝트 폴더 열기

공유받은 브랜치를 체크아웃하거나 ZIP을 압축 해제한 뒤, VS Code에서 `enterprise-work-assistant` 폴더를 여세요. VS Code 메뉴에서 **Terminal → New Terminal**을 선택합니다. 터미널의 현재 위치가 아래 두 경로가 보이는 프로젝트 최상위 폴더인지 확인하세요.

| 경로 | 역할 |
| --- | --- |
| `src/document_parser.py` | 실행할 파이썬 스크립트 |
| `src/data/input/제안요청서.hwp` | 함께 받은 원본 제안요청서 |

## 2. Python 환경 만들고 파서 실행하기

프로젝트에서 사용하는 **Python 3.13**을 권장합니다. 아래에서 본인 터미널에 해당하는 블록 하나만 위에서부터 실행하세요. 첫 줄은 Python 버전을 확인하고, 다음 두 줄은 가상 환경을 만들고 `pip`로 HWP 읽기 패키지를 설치합니다. 마지막 줄이 파서를 실행합니다.

### Windows PowerShell

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "python-hwpx>=7.0.1,<8"
.\.venv\Scripts\python.exe src/document_parser.py
```

Windows에서 `python --version`만 동작하는 경우, 첫 두 줄의 `py -3` 대신 `python`을 사용하세요.

### macOS, Linux 또는 WSL

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install 'python-hwpx>=7.0.1,<8'
.venv/bin/python src/document_parser.py
```

설치와 실행 모두 `.venv` 안의 같은 Python을 사용합니다. 다음에 다시 실행할 때는 선택한 블록의 마지막 줄만 실행하면 됩니다.

## 3. JSON 결과 확인하기

샘플 문서 처리에 성공하면 터미널에 **`33건 저장`**과 저장 경로가 표시됩니다. VS Code의 파일 목록에서 아래 파일을 여세요.

```text
src/data/output/제안요청서.requirements.json
```

`output` 폴더는 첫 실행 때 자동으로 생성됩니다. JSON 배열의 각 항목은 요구사항 한 건입니다. `req_id`는 파서가 붙인 ID, `source_location`은 원문에서 찾을 위치, `req_text`는 추출한 본문입니다. 다시 실행하면 같은 이름의 결과 파일을 덮어씁니다. 결과 파일은 실행한 컴퓨터에 저장되며 `.gitignore`에 의해 Git 추적에서 제외됩니다.

## 실행이 멈추면

| 오류 | 확인할 내용 |
| --- | --- |
| `No module named 'hwpx'` | 위 블록의 `-m pip install` 줄을 실행한 뒤, 같은 블록의 마지막 줄로 실행하세요. 설치 이름은 `python-hwpx`이고, 코드에서 불러오는 모듈 이름은 `hwpx`입니다. |
| `can't open file ... document_parser.py` | 터미널이 프로젝트 최상위 폴더에 있는지 확인하세요. |
| `FileNotFoundError` | `src/data/input/제안요청서.hwp`가 있는지 확인하세요. 파일이 보이지 않으면 공유받은 브랜치나 ZIP의 버전을 확인하세요. |

[Python 가상 환경 문서](https://docs.python.org/3/library/venv.html) · [python-hwpx 설치 안내](https://pypi.org/project/python-hwpx/7.0.1/)
