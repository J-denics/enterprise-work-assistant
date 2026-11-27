# RFP 파서 실행 가이드

공유받은 프로젝트에서 HWP와 PDF 제안요청서의 요구사항을 추출해 내 컴퓨터에 JSON으로 저장하는 방법입니다. `src/data/input/`에 여러 파일이 있어도 한 번의 실행으로 처리할 수 있습니다.

## 1. 프로젝트 폴더 열기

공유받은 브랜치를 체크아웃하거나 ZIP 파일을 압축 해제한 뒤, VS Code에서 `enterprise-work-assistant` 폴더를 여세요. **Terminal → New Terminal**을 선택하고, 아래 경로가 보이는 프로젝트 최상위 폴더에서 명령을 실행하세요.

| 경로 | 역할 |
| --- | --- |
| `src/document_parser.py` | 실행할 파이썬 스크립트 |
| `src/data/input/` | 처리할 `.hwp`와 `.pdf` 파일을 넣는 폴더 |
| `src/data/output/` | 결과 JSON이 저장되는 폴더. 실행할 때 자동으로 생성됩니다. |

샘플 HWP가 이미 `src/data/input/`에 있다면 바로 실행할 수 있습니다. PDF도 테스트하려면 받은 `제안요청서.pdf`를 같은 폴더에 넣으세요.

## 2. Python 환경 만들고 파서 실행하기

**Python 3.13**을 권장합니다. 사용하는 터미널에 맞는 블록 하나를 위에서부터 실행하세요. Python 버전을 확인하고, `.venv` 가상환경을 만든 뒤 `pip`로 HWP와 PDF 처리 패키지를 설치합니다. 마지막 명령이 파서를 실행합니다.

### Windows PowerShell

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "python-hwpx>=7.0.1,<8" "pdfplumber==0.11.9"
.\.venv\Scripts\python.exe src/document_parser.py
```

`py` 명령을 사용할 수 있고 Python 3.13이 설치되어 있다면, 첫 두 줄에서 `py -3`을 `py -3.13`으로 바꿔 해당 버전을 지정할 수 있습니다. `python` 명령만 동작한다면 첫 두 줄의 `py -3` 대신 `python`을 사용하세요.

### macOS, Linux 또는 WSL

```bash
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install 'python-hwpx>=7.0.1,<8' 'pdfplumber==0.11.9'
.venv/bin/python src/document_parser.py
```

설치와 실행에는 `.venv` 안의 같은 Python을 사용합니다. 설치를 마친 뒤 다시 실행할 때는 위 블록의 마지막 줄만 실행하면 됩니다.

## 3. JSON 결과 확인하기

처리가 끝나면 터미널에 파일별 처리 상태와 생성·건너뜀·실패 건수가 표시됩니다. `저장`으로 표시된 파일의 결과는 VS Code에서 `src/data/output/`을 열어 확인하세요.

| 샘플 입력 | 결과 파일 이름 | 샘플 추출 건수 |
| --- | --- | ---: |
| `제안요청서.hwp` | `제안요청서.requirements.json` | 33건 |
| `제안요청서.pdf` | `제안요청서.pdf.requirements.json` | 44건 |

PDF 결과 이름에는 `.pdf`가 포함됩니다. 두 원본의 이름이 같아도 각 결과는 별도 파일로 저장됩니다. 추출 건수는 입력 문서에 따라 달라집니다.

JSON 배열의 각 항목은 요구사항 한 건입니다. `req_id`는 파서가 붙인 ID, `source_location`은 원문에서 찾을 위치, `req_text`는 추출한 요구사항 본문입니다. 결과는 실행한 컴퓨터의 `output` 폴더에 저장됩니다. 코드를 공유할 때는 생성된 JSON을 커밋에서 제외하세요.

## 4. 새 문서를 추가하거나 다시 추출하기

- **새 문서 추가** — `src/data/input/`에 파일을 넣고 실행하세요. 결과 JSON이 없는 입력만 처리합니다.
- **`건너뜀` 확인** — 해당 입력의 결과 JSON이 이미 있다는 뜻입니다. 예를 들어 HWP 결과가 있는 상태에서 PDF를 추가하면 HWP는 `건너뜀`, PDF는 `저장`으로 표시됩니다.
- **기존 문서 다시 추출** — 원본을 수정했거나 결과를 새로 만들려면 해당 JSON만 `output` 폴더 밖으로 옮긴 뒤 다시 실행하세요.

## 실행이 잘되지 않을 때

| 증상 | 확인할 내용 |
| --- | --- |
| `No module named 'hwpx'` 또는 `No module named 'pdfplumber'` | 2단계에서 본인 터미널에 맞는 `-m pip install` 줄을 실행한 뒤, 같은 블록의 마지막 줄로 다시 실행하세요. HWP 모듈 `hwpx`의 설치 패키지 이름은 `python-hwpx`입니다. |
| `can't open file ... document_parser.py` | 터미널의 현재 위치가 프로젝트 최상위 폴더인지 확인하세요. |
| 처리하려는 문서가 로그에 표시되지 않음 | 원본 파일이 `src/data/input/` 바로 아래에 있고 확장자가 `.hwp` 또는 `.pdf`인지 확인하세요. |
| PDF를 넣었는데 JSON이 보이지 않음 | `src/data/output/`에서 이름에 `.pdf.requirements.json`이 붙은 파일을 찾아보세요. 터미널에 `실패`가 표시되면 같은 줄의 오류 메시지를 확인하세요. |

[Python 가상환경 문서](https://docs.python.org/3/library/venv.html) · [python-hwpx 설치 안내](https://pypi.org/project/python-hwpx/7.0.1/)