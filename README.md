# budget_app

JSONL 파일 기반 콘솔 용돈 기입장 프로그램입니다. 거래 추가/조회/검색/요약/예산/카테고리/수정/삭제/import/export를 지원합니다.

## 실행 방법

Python 3.10 이상에서 패키지 진입점으로 실행합니다.

```bash
python -m budget_app --help
```

기본 저장 폴더는 `./data`이며, `--data-dir`로 변경할 수 있습니다.

```bash
python -m budget_app --data-dir ./data category list
```

## 저장 파일 위치와 형식

저장 포맷은 JSONL로 고정입니다.

기본 위치:
- `./data/transactions.jsonl`
- `./data/categories.jsonl`
- `./data/budgets.jsonl`

옵션으로 변경:
- `--data-dir <경로>`

형식:
- `transactions.jsonl`: 거래 1건당 JSON 1줄
- `categories.jsonl`: 카테고리 1건당 JSON 1줄
- `budgets.jsonl`: 월 예산 1건당 JSON 1줄

초기 실행 시 저장 파일을 준비하며, 카테고리 파일이 비어 있으면 기본 카테고리를 자동 생성합니다.
- `food`
- `transport`
- `rent`
- `etc`

### 저장 포맷으로 JSONL을 쓰는 이유

저장은 JSONL, 외부와의 교환(import/export)은 CSV로 역할을 나눕니다.

| 기준 | JSONL (저장) | CSV (교환) |
| --- | --- | --- |
| 한 건 추가 | 파일 끝에 한 줄 append — 기존 내용을 다시 쓰지 않습니다 | 같은 append가 가능하지만 컬럼 순서를 매번 맞춰야 합니다 |
| 중첩 구조 | `tags` 배열을 그대로 담습니다 | 배열을 `a,b` 문자열로 눌러 담고 읽을 때 다시 파싱해야 합니다 |
| 스트리밍 | 한 줄이 한 레코드라 줄 단위로 끊어 읽습니다 | 따옴표 안에 줄바꿈이 들어가면 한 줄이 한 레코드가 아닙니다 |
| 한 줄 손상 | 그 줄만 실패로 식별됩니다 | 컬럼 수가 어긋나면 뒤쪽 해석까지 틀어질 수 있습니다 |
| 사람이 열어보기 | 한 줄씩 읽어야 합니다 | 엑셀·스프레드시트로 바로 엽니다 |
| 타입 보존 | 숫자/문자열/배열이 구분됩니다 | 모두 문자열이라 읽을 때 변환해야 합니다 |

저장 포맷을 바꿀 조건은 다음과 같습니다. 거래가 수십만 건을 넘어 조회 지연이 체감되거나, 월별·카테고리별 집계를
자주 요구하게 되면 인덱스가 있는 SQLite로 옮기는 편이 낫습니다. 그때 고치는 범위는 `repository.py`와
조립 지점인 `cli.build_service()`입니다.

## 주요 동작

- 거래 ID는 `TX-000001` 형식으로 6자리 0패딩 시퀀스로 발급됩니다.
- `add`는 대화형 입력 방식입니다.
- `update`는 옵션 기반입니다.
- `list`, `search`는 저장 파일을 스트리밍으로 읽습니다.
- `update/delete`는 임시 파일 작성 후 `os.replace`로 원자적으로 교체합니다.
- 카테고리 삭제 시 해당 카테고리를 사용하는 거래가 있으면 삭제를 막습니다. 대체 카테고리를 묻지 않고 차단만 합니다.
- 금액·예산은 1 이상의 정수만 받습니다. `budget set --amount 0` 과 음수는 거부되며, 예산 미설정과 0원 설정은 다른 상태입니다.
  예산을 설정하지 않은 달은 `summary`에 예산 줄이 나오지 않습니다.
- 예외는 스택트레이스 대신 원인과 힌트를 출력합니다. 잘못된 입력 항목이 여러 개면 모든 항목의 오류를 함께 출력합니다.
- 정상 종료 코드는 `0`, 오류 시 `0`이 아닌 값을 반환합니다.
- 실행 시 로그와 실행 시간이 출력됩니다.
  - `[LOG] main called`
  - `[TIME] main: ...s`

## 주요 명령 예시

### 도움말

```bash
python -m budget_app --help
```

지원 명령:
- `add`
- `list`
- `search`
- `summary`
- `budget`
- `category`
- `update`
- `delete`
- `import`
- `export`

### 거래 추가

`add`는 대화형 입력입니다.

```bash
python -m budget_app add
```

입력 순서:
- 날짜(YYYY-MM-DD)
- 타입(income/expense)
- 카테고리
- 금액(양수)
- 메모(선택)
- 태그(쉼표 구분, 선택)

성공 시:
```text
[저장 완료] id=TX-000001
```

### 거래 목록

```bash
python -m budget_app --data-dir ./data list --limit 3
```

실행 예:
```text
TX-000005 | 2024-03-30 | income | etc | 3000000 | 급여
TX-000001 | 2024-03-15 | expense | food | 15000 | 점심
TX-000002 | 2024-03-10 | expense | food | 30000 | 장보기
```

### 거래 검색

```bash
python -m budget_app --data-dir ./data search --category food --type expense
```

지원 조건:
- `--from YYYY-MM-DD`
- `--to YYYY-MM-DD`
- `--category`
- `--type`
- `--q`
- `--tag`

실행 예:
```text
TX-000001 | 2024-03-15 | expense | food | 15000 | 점심
TX-000002 | 2024-03-10 | expense | food | 30000 | 장보기
```

### 월별 요약

```bash
python -m budget_app --data-dir ./data summary --month 2024-03 --top 3
```

실행 예:
```text
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원

지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원
```

데이터가 없으면:
```text
데이터 없음
```

### 예산 설정

```bash
python -m budget_app --data-dir ./data budget set --month 2024-03 --amount 500000
```

실행 예:
```text
[저장 완료] 2024-03 예산 500000원
```

예산이 설정된 뒤 `summary` 실행 예:
```text
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)

지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원
```

### 카테고리 관리

목록 조회:
```bash
python -m budget_app --data-dir ./data category list
```

실행 예:
```text
- food
- transport
- rent
- etc
```

추가:
```bash
python -m budget_app category add --name salary
```

또는:
```bash
python -m budget_app category add salary
```

삭제:
```bash
python -m budget_app category remove --name food
```

또는:
```bash
python -m budget_app category remove food
```

사용 중인 카테고리 삭제 시:
```text
[오류] 사용 중인 카테고리는 삭제할 수 없습니다.
[힌트] 해당 카테고리를 사용하는 거래를 수정하거나 삭제한 후 다시 시도하세요.
```

### 거래 수정

옵션 기반으로만 동작합니다.

```bash
python -m budget_app update --id TX-000001 --memo 점심값 --amount 16000
```

지원 옵션:
- `--id` 필수
- `--date`
- `--type`
- `--category`
- `--amount`
- `--memo`
- `--tags`

성공 시:
```text
[수정 완료] TX-000001 | 2024-03-15 | expense | food | 16000 | 점심값
```

### 거래 삭제

```bash
python -m budget_app delete --id TX-000001
```

없는 ID 삭제 시:
```text
[오류] 없는 데이터입니다.
[힌트] id를 다시 확인하세요.
```

### CSV 가져오기

```bash
python -m budget_app --data-dir ./data import --from import.csv
```

실행 예:
```text
[완료] imported=5, skipped=0
```

검증에 실패한 행은 건너뛰고 나머지를 반영합니다(부분 성공). 실패 행은 **행 번호와 모든 실패 이유**를 함께 보고합니다.

```text
[완료] imported=2, skipped=2
[실패] 3행: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[실패] 4행: 타입은 income 또는 expense 여야 합니다.; 존재하지 않는 카테고리입니다.; 금액은 양수여야 합니다.
```

| 옵션 | 동작 |
| --- | --- |
| (없음) | 부분 성공. 실패 행만 건너뛰고 `imported`/`skipped`를 보고합니다. 종료 코드 `0` |
| `--atomic` | 전체 검증을 먼저 하고, 한 행이라도 실패하면 **아무것도 쓰지 않습니다**. 종료 코드 `1` |
| `--report <경로.csv>` | 실패 행을 원본 스키마 + `line`,`reason` 컬럼으로 저장합니다 |

```bash
python -m budget_app import --from import.csv --atomic --report failed.csv
```

```text
[중단] 실패 2행이 있어 아무것도 적용하지 않았습니다 (--atomic).
[실패] 3행: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[리포트] failed.csv (2행)
```

`failed.csv`는 `line`,`reason` 두 컬럼을 지우면 그대로 다시 `import` 할 수 있는 형식입니다.
부분 성공과 전체 롤백 중 무엇을 쓸지는 데이터 성격으로 정합니다. 가계부 거래는 서로 독립적이라 기본값을
부분 성공으로 두고, 한 파일이 하나의 정산 단위처럼 전부 들어가야 의미가 있을 때 `--atomic`을 씁니다.

### CSV 내보내기

월 조건:
```bash
python -m budget_app export --out export.csv --month 2024-03
```

기간 조건:
```bash
python -m budget_app export --out export.csv --from 2024-03-01 --to 2024-03-31
```

실행 예:
```text
[완료] export.csv (12 records)
```

`export`는 다음 중 하나의 조건이 반드시 필요합니다.
- `--month YYYY-MM`
- `--from YYYY-MM-DD --to YYYY-MM-DD`

## import/export CSV 스키마

인코딩 및 형식:
- UTF-8
- 헤더 포함

컬럼:

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 |

예시:

```csv
date,type,category,amount,memo,tags
2024-03-15,expense,food,15000,점심,meal
2024-03-30,income,etc,3000000,급여,
```

## 오류 처리

예시:
```text
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
```

`add`와 `update`는 입력 항목을 하나씩 끊어 검증하지 않고 전체를 검증한 뒤, 잘못된 항목을 모두
출력합니다. 입력받은 순서(날짜 → 타입 → 카테고리 → 금액 → 태그)대로 `[오류]`와 `[힌트]` 한 쌍씩
나오므로, 한 번 고치면 다음 오류를 새로 만나지 않습니다.

```text
$ python -m budget_app add
날짜(YYYY-MM-DD): 2026-10-32
타입(income/expense): income
카테고리: 1
금액(양수): 1
메모(선택):
태그(쉼표로 구분, 없으면 엔터):
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
[오류] 존재하지 않는 카테고리입니다.
[힌트] category list로 목록을 확인하거나 category add로 먼저 등록하세요.
날짜(YYYY-MM-DD):
```

```bash
python -m budget_app update --id TX-000001 --date 2026-02-30 --type buy
```

```text
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
[오류] 타입은 income 또는 expense 여야 합니다.
[힌트] 예: income
```

또는:
```text
[오류] 알 수 없는 오류가 발생했습니다.
[힌트] 입력값과 저장 파일 상태를 확인한 후 다시 시도하세요.
```

### 저장 파일이 손상됐을 때

저장 파일의 한 줄이 깨지면 그 파일을 읽는 명령이 다음과 같이 멈춥니다.

```text
[오류] 거래 저장 파일 형식이 올바르지 않습니다.
[힌트] transactions.jsonl 파일 내용을 확인하세요.
```

복구 절차는 이렇습니다.

1. `python -c "import json,io,sys; [json.loads(l) for i,l in enumerate(io.open(sys.argv[1],encoding='utf-8'),1) if l.strip()]" ./data/transactions.jsonl`
   로 어느 줄에서 멈추는지 확인합니다.
2. 해당 줄을 고치거나 삭제합니다. 한 줄이 한 레코드이므로 그 줄만 지우면 나머지 거래는 그대로 살아 있습니다.
3. 지운 내용이 필요하면 `export`로 떠 둔 CSV에서 다시 `import` 합니다.

`update`·`delete`는 임시 파일에 전체를 다시 쓴 뒤 `os.replace`로 교체하므로, 쓰는 도중에 중단되어도
원본은 옛 내용 그대로 남습니다. 별도의 백업 파일은 만들지 않습니다. 중요한 데이터는 작업 전에
`export --month`로 CSV를 떠 두거나 `./data` 폴더를 복사해 두는 방식을 권합니다.

## 동작 검증

성공 경로와 실패 경로를 한 번에 실행하고 종료 코드·출력을 단정하는 스크립트가 있습니다.
실습 데이터(`./data`)는 건드리지 않고 임시 폴더에서 돌립니다.

```bash
bash scripts/smoke.sh
```

```text
  통과 34 / 실패 0
  모든 단정 통과
```

검증 범위는 정상 경로 12건, 실패 경로(원인+힌트와 종료 코드 `1`) 10건, CSV 가져오기·내보내기 6건,
저장 파일 손상 처리 2건, 데코레이터 출력 2건, 인자 사용법 오류(종료 코드 `2`) 2건입니다.
최근 실행 기록은 `logs/smoke.log`에 있습니다.

## 성능과 한계

거래 10만 건(13.2MB)을 넣고 측정한 결과입니다(Python 3.13, Windows, SSD. 명령마다 인터프리터 시작 약 0.1초 포함).

| 명령 | 소요 시간 | 최대 메모리 |
| --- | --- | --- |
| `list --limit 10` | 1.97초 | 0.8MB |
| `summary --month` | 1.91초 | 0.1MB |
| `search --category food` (결과 2.5만 건) | 1.85초 | 14.7MB |
| `update --id` / `delete --id` | 3.1초 | 0.8MB |
| `add` 1건 | 1.81초 (빈 파일에서는 0.13초) | 0.8MB |
| (비교) 전체를 리스트로 읽을 때 | — | 51.5MB |

- `list`와 `summary`는 데이터가 10만 건이어도 메모리가 1MB 미만입니다. 한 줄씩 읽어 필요한 만큼만 들고 있습니다.
- `search`는 읽기는 스트리밍이지만 최신순 정렬 때문에 **매칭 결과를 모읍니다**. 결과 수에 비례해 메모리가 늘어납니다.
- `add` 1건이 1.8초인 이유는 `next_id()`가 매번 전체를 훑어 최대 번호를 찾기 때문입니다. 가장 먼저 개선할 지점입니다.
- `update`·`delete`는 전체를 다시 쓰므로 읽기의 약 1.6배가 걸립니다. 안전한 교체의 대가입니다.

개선 우선순위는 ① `next_id`를 시퀀스 파일로 분리 ② 날짜 역순 저장으로 정렬 제거 ③ 월별 파일 분할
또는 SQLite 전환입니다.

## 패키지 구조

패키지명: `budget_app`. 패키지 내부 import는 상대 import를 사용합니다.

| 모듈 | 책임 | 공개 API | 상태 |
| --- | --- | --- | --- |
| `__main__.py` | `python -m budget_app` 진입점, 종료 코드 전달 | `run()` | 없음 |
| `cli.py` | 인자 파싱, 대화형 입력, 조립, 출력 | `build_parser()`, `build_service()`, `prompt_add()`, `main()` | 없음 |
| `service.py` | 업무 규칙, 집계, 가져오기/내보내기 정책 | `BudgetService`, `SearchQuery`, `SummaryResult`, `ImportResult`, `ImportFailure` | 저장소 3개를 주입받아 보관 |
| `repository.py` | 파일 읽기·쓰기, 원자적 교체 | `TransactionRepository`, `CategoryStore`, `BudgetStore` | 경로만 보관(메모리 캐시 없음) |
| `models.py` | 데이터 구조와 형식 검증 | `Transaction`, `Budget`, `Category`, `validate_*()`, `parse_tags()`, `to_dict()`, `from_dict()` | 없음(생성 시 검증·정규화) |
| `formatter.py` | 출력 문자열 생성 | `format_transaction(s)()`, `format_summary()`, `format_categories()`, `format_error()`, `format_import_result()` | 없음(순수 함수) |
| `decorators.py` | 호출 로그·실행 시간·예외 처리 | `log_call`, `timed`, `handle_errors` | 없음 |
| `errors.py` | 예외 계층과 검증 실패 수집 | `AppError`, `ValidationError`, `ValidationErrors`, `NotFoundError`, `ConflictError`, `StorageError`, `ErrorCollector` | `ErrorCollector`만 수집 중 상태 보유 |

저장소 클래스는 파일 경로 외에 상태를 갖지 않습니다. 호출마다 파일을 읽으므로 여러 프로세스가 번갈아 써도
마지막 쓰기가 반영되며, 그 대신 반복 조회에 캐시 이득이 없습니다.

예외는 모두 `AppError` 하위입니다. 파일 I/O(`OSError`)와 JSON 파싱 오류는 저장소 경계에서 `StorageError`로
감싸 원인과 힌트를 붙입니다.

## 문서

| 파일 | 내용 |
|---|---|
| `plan.md` | 요구사항 분해와 단계별 실행 계획 |
| `note.md` | 개념 원리와 구현 근거를 정리한 리포트 |
| `walkthrough.md` | 코드를 한 줄씩 설명할 때 쓰는 학습 가이드 (모듈별 라인 안내, 예상 질문) |
| `REPORT.md` | 실행 결과 기록 |
| `selfcheck.md` | 요구사항 자기 점검 결과 |