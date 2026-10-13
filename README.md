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

## 주요 동작

- 거래 ID는 `TX-000001` 형식으로 6자리 0패딩 시퀀스로 발급됩니다.
- `add`는 대화형 입력 방식입니다.
- `update`는 옵션 기반입니다.
- `list`, `search`는 저장 파일을 스트리밍으로 읽습니다.
- `update/delete`는 임시 파일 작성 후 `os.replace`로 원자적으로 교체합니다.
- 카테고리 삭제 시 해당 카테고리를 사용하는 거래가 있으면 삭제를 막습니다.
- 예외는 스택트레이스 대신 원인과 힌트를 출력합니다.
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

또는:
```text
[오류] 알 수 없는 오류가 발생했습니다.
[힌트] 입력값과 저장 파일 상태를 확인한 후 다시 시도하세요.
```

## 패키지 구조

패키지명: `budget_app`

주요 모듈:
- `__main__.py` : `python -m budget_app` 진입점
- `cli.py` : argparse 기반 CLI
- `service.py` : 비즈니스 로직
- `repository.py` : JSONL 저장소
- `models.py` : dataclass 모델 및 검증
- `formatter.py` : 콘솔 출력 포맷
- `decorators.py` : 로그/시간/예외 처리 데코레이터
- `errors.py` : 공통 예외 계층

패키지 내부 import는 상대 import를 사용합니다.
