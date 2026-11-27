# RFP 파서 실행 가이드

공유받은 프로젝트에서 HWP와 PDF 제안요청서의 요구사항을 추출해 내 컴퓨터에 JSON으로 저장하는 방법입니다. `src/data/input/`에 여러 파일이 있어도 한 번의 실행으로 처리할 수 있습니다.

## 1. 프로젝트 폴더 열기

공유받은 브랜치를 체크아웃하거나 ZIP 파일을 압축 해제한 뒤, VS Code에서 `enterprise-work-assistant` 폴더를 여세요. **Terminal → New Terminal**을 선택하고, 아래 경로가 보이는 프로젝트 최상위 폴더에서 명령을 실행하세요.

| 경로 | 역할 |
| --- | --- |
| `src/document_parser.py` | 실행할 파이썬 스크립트 |
| `src/data/input/` | 처리할 `.hwp`와 `.pdf` 파일을 넣는 폴더 |
| `src/data/output/` | 결과 JSON이 저장되는 폴더. 실행할 때 자동으로 생성됩니다. |

샘플 HWP와 PDF가 `src/data/input/`에 포함되어 있습니다. 두 파일은 제목만 같고 내용이 다른 문서입니다.

## 2. Python 환경 만들고 파서 실행하기

프로젝트의 `.python-version`은 **Python 3.13**입니다. Python 3.15에서는 현재 잠금 파일의 일부 의존성에 호환 wheel이 없어 설치가 실패하므로, 검증한 3.13 환경을 사용하세요.

### uv 사용 (권장)

`uv`가 설치되어 있다면 다음 명령으로 `uv.lock`에 기록된 PDF·HWP 패키지를 함께 설치하고 실행할 수 있습니다. 필요한 Python 3.13도 자동으로 준비됩니다.

```text
uv sync --locked --python 3.13
uv run --locked python -X utf8 src/document_parser.py
```

### pip 사용

아래 방법은 파서에 필요한 패키지만 설치합니다. 프로젝트 전체의 잠금 버전으로 설치하려면 위의 `uv sync --locked`를 사용하세요.

### Windows PowerShell

```powershell
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "python-hwpx>=7.0.1,<8" "pdfplumber==0.11.9"
.\.venv\Scripts\python.exe -X utf8 src/document_parser.py
```

`py` 명령을 사용할 수 없다면 설치된 Python 3.13 실행 파일의 경로를 지정하거나 위의 uv 방법을 사용하세요.

### macOS, Linux 또는 WSL

```bash
python3.13 --version
python3.13 -m venv .venv
.venv/bin/python -m pip install 'python-hwpx>=7.0.1,<8' 'pdfplumber==0.11.9'
.venv/bin/python -X utf8 src/document_parser.py
```

설치와 실행에는 `.venv` 안의 같은 Python을 사용합니다. 설치를 마친 뒤 다시 실행할 때는 위 블록의 마지막 줄만 실행하면 됩니다.

## 3. JSON 결과 확인하기

처리가 끝나면 터미널에 파일별 처리 상태와 생성·건너뜀·실패 건수가 표시됩니다. `저장`으로 표시된 파일의 결과는 VS Code에서 `src/data/output/`을 열어 확인하세요.

| 샘플 입력 | 결과 파일 이름 | 샘플 추출 건수 |
| --- | --- | ---: |
| `제안요청서.hwp` | `제안요청서.requirements.json` | 33건 |
| `제안요청서.pdf` | `제안요청서.pdf.requirements.json` | 44건 |

PDF 결과 이름에는 `.pdf`가 포함됩니다. 두 원본의 이름이 같아도 각 결과는 별도 파일로 저장됩니다. 추출 건수는 입력 문서에 따라 달라집니다.

JSON 배열의 각 항목은 요구사항 한 건입니다.

| 필드 | 의미 |
| --- | --- |
| `req_id` | 파서가 순서대로 붙인 ID |
| `source_req_id` | 원문에 적힌 요구사항 번호 |
| `doc_name`, `doc_type` | 원본 파일 이름과 형식 |
| `source_location` | PDF 페이지 범위(예: `p.32–33`) 또는 HWP 표 번호 |
| `req_text` | 확인된 기호와 서식을 정리한 본문 |
| `raw_req_text` | 기호 치환 전 추출 본문. 원본 파일과 함께 대조할 때 사용 |
| `warnings` | 미확인 문자나 문서 끝의 종료 항목 누락 등 검토할 사항 |

PDF 페이지는 인쇄된 쪽수가 아닌 파일의 물리 페이지 기준입니다. 결과는 실행한 컴퓨터의 `src/data/output/`에 UTF-8 JSON으로 저장되며 Git에서 제외됩니다.

## 4. 새 문서를 추가하거나 다시 추출하기

- **새 문서 추가** — `src/data/input/`에 파일을 넣고 실행하세요. 결과 JSON이 없는 입력만 처리합니다.
- **`건너뜀` 확인** — 해당 입력의 결과 JSON이 이미 있다는 뜻입니다. 예를 들어 HWP 결과가 있는 상태에서 PDF를 추가하면 HWP는 `건너뜀`, PDF는 `저장`으로 표시됩니다.
- **기존 문서 다시 추출** — 실행 명령 끝에 `--overwrite`를 붙이세요. 변환에 실패하면 기존 JSON을 보존하고 종료 코드 1을 반환합니다.
- **한 파일만 처리** — `--file "src/data/input/제안요청서.pdf"`처럼 파일 경로를 지정하세요. 출력은 항상 `src/data/output/`에 저장됩니다.

## 5. 글머리표와 깨진 기호 처리

줄 시작의 알려진 글머리표는 `●`로 통일합니다. `≥`, `≤`, `%`, `①`, `-` 등 본문 의미가 있는 기호는 유지합니다. PDF 폰트의 사설 영역 문자는 UTF-8 저장만으로 의미를 복원할 수 없으므로, 원문과 대조한 치환표를 해당 파일에 적용합니다.

저장소의 샘플 PDF를 대조해 확인한 치환표는 `src/data/symbol_maps/sample-rfp-pdf.json`입니다. `U+F09F → ●`, `U+F09E → ·`를 적용합니다.

```text
uv run --locked python -X utf8 src/document_parser.py --file "src/data/input/제안요청서.pdf" --symbol-map src/data/symbol_maps/sample-rfp-pdf.json --overwrite
```

PowerShell에서 pip 방식으로 설치했다면 `uv run --locked python` 대신 `.\.venv\Scripts\python.exe`를 사용하세요.

치환표는 **해당 PDF 전용**입니다. 같은 이름의 HWP나 다른 PDF에 그대로 적용하지 마세요. 폰트마다 같은 사설 문자 코드의 뜻이 다를 수 있어 `--symbol-map`은 `--file`과 함께 사용해야 합니다. 뜻을 확인하지 못한 문자는 삭제하지 않고 `warnings`에 표시합니다. 기본 실행은 PDF 사설 문자도 보존하므로, 샘플 PDF의 `●` 복원에는 위 명령을 사용하세요.

페이지를 넘는 본문은 종료 항목이 없는 경우와 3페이지 이상 이어지는 경우에도 연결합니다. 앞 요구사항의 남은 본문과 다음 요구사항이 한 표로 잡힌 경우에도 나누어 보존합니다. 연속 여부가 불명확하거나 중간 페이지 표를 추출하지 못하면 조용히 생략하지 않고 오류를 알립니다.

## 6. 수정 검증

```text
uv run --locked python -X utf8 -m unittest discover -s tests -v
```

회귀 테스트는 페이지 경계, 반복 헤더, 기호 치환, 원문 보존, 중복 번호, 파일 선택, 기존 결과의 안전한 재생성을 확인합니다. 실제 샘플은 HWP 33건, PDF 44건이며, 샘플 PDF의 치환표 적용 결과에서 `●` 154개를 확인했습니다. HWP의 `MHR-003`에는 미확인 사설 문자 `U+F0A7`가 남아 경고로 표시됩니다.

## 실행이 잘되지 않을 때

| 증상 | 확인할 내용 |
| --- | --- |
| `No module named 'hwpx'` 또는 `No module named 'pdfplumber'` | 2단계에서 본인 터미널에 맞는 `-m pip install` 줄을 실행한 뒤, 같은 블록의 마지막 줄로 다시 실행하세요. HWP 모듈 `hwpx`의 설치 패키지 이름은 `python-hwpx`입니다. |
| `can't open file ... document_parser.py` | 터미널의 현재 위치가 프로젝트 최상위 폴더인지 확인하세요. |
| 처리하려는 문서가 로그에 표시되지 않음 | 원본 파일이 `src/data/input/` 바로 아래에 있고 확장자가 `.hwp` 또는 `.pdf`인지 확인하세요. |
| PDF를 넣었는데 JSON이 보이지 않음 | `src/data/output/`에서 이름에 `.pdf.requirements.json`이 붙은 파일을 찾아보세요. 터미널에 `실패`가 표시되면 같은 줄의 오류 메시지를 확인하세요. |

[Python 가상환경 문서](https://docs.python.org/3/library/venv.html) · [python-hwpx 설치 안내](https://pypi.org/project/python-hwpx/7.0.1/)
