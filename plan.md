# budget_app 문서

## 1. 요구사항 분해

이 프로그램은 `budget_app` 패키지로 구현된 파일 기반 콘솔 용돈 기입장이다. 실제 구현 기준으로 충족한 요구사항과 동작 범위를 정리하면 다음과 같다.

### 핵심 기능
- 거래 추가: `add`
  - 대화형 입력으로 날짜, 타입, 카테고리, 금액, 메모, 태그를 받는다.
  - 저장 성공 시 `id`를 출력한다.
- 거래 목록: `list --limit N`
  - 최신순으로 출력한다.
  - 저장소 읽기는 제너레이터 `stream()` 기반이다.
- 거래 검색: `search`
  - 지원 조건: `--from`, `--to`, `--category`, `--type`, `--q`, `--tag`
  - 결과는 최신순으로 정렬해 출력한다.
- 월별 요약: `summary --month YYYY-MM --top N`
  - 총 수입, 총 지출, 잔액을 출력한다.
  - 카테고리별 지출 TOP N을 출력한다.
  - 예산이 있으면 사용률을 함께 출력한다.
  - 데이터가 없으면 `데이터 없음`을 출력한다.
- 예산 설정: `budget set --month YYYY-MM --amount 금액`
  - 월 예산을 저장한다.
- 카테고리 관리: `category add/list/remove`
  - 기본 카테고리 자동 생성: `food`, `transport`, `rent`, `etc`
  - 사용 중인 카테고리는 삭제를 막는다.
- 거래 수정: `update`
  - 옵션 기반으로 고정
  - `--id`와 변경 필드 옵션을 받는다.
- 거래 삭제: `delete --id`
  - 없는 id는 오류 메시지와 힌트를 출력한다.
- 가져오기: `import --from PATH`
  - CSV를 읽어 거래를 일괄 등록한다.
  - 결과로 `imported`, `skipped` 수를 출력한다.
- 내보내기: `export --out PATH`
  - `--month` 또는 `--from`/`--to` 조건이 필요하다.
  - CSV 헤더를 포함해 저장한다.

### 저장 정책
- 저장 포맷은 JSONL로 고정
- 영구 저장 파일 3종
  - `transactions.jsonl`
  - `categories.jsonl`
  - `budgets.jsonl`
- 기본 저장 폴더는 `./data`
- `--data-dir`로 변경 가능

### 구조 및 품질 요구사항
- 패키지 내부 import는 전부 상대 import 사용
- `dataclass` 사용
- 예외 계층 분리
- 데코레이터 적용
  - `handle_errors`
  - `log_call`
  - `timed`
- 오류 시 스택트레이스 대신 원인과 힌트 출력
- 정상 종료 코드 `0`, 오류 종료 코드 `1`
- update/delete는 임시 파일 작성 후 `os.replace`로 원자적 교체

## 2. 모듈 계약과 설계 결정

## 패키지/진입점
- 패키지명: `budget_app`
- 모듈 실행: `python -m budget_app`
- `__main__.py`에서 `cli.main()`을 호출하고 그 반환값으로 종료한다.

## 설계 결정
- 저장 포맷: JSONL 고정
- update 방식: 옵션 기반 고정
- 초기 카테고리 정책: 기본 카테고리 자동 생성
- 카테고리 삭제 정책: 사용 중이면 삭제 불가
- 저장 경로: 기본 `./data`, 옵션 `--data-dir`
- 거래 id: `TX-000001` 형식의 6자리 제로패딩 시퀀스
- 파일 안정성: update/delete는 임시 파일 후 `os.replace`
- 패키지 내부 import: 전부 상대 import

## 모듈별 계약

### `errors.py`
공통 예외 계층을 정의한다.
- `AppError(message, hint=None)`
- `ValidationError`
- `NotFoundError`
- `ConflictError`
- `StorageError`

역할:
- 사용자 메시지와 해결 힌트를 함께 전달한다.
- CLI 공통 오류 처리 데코레이터에서 잡아 출력한다.

### `models.py`
데이터 구조와 검증 로직을 정의한다.
- `Transaction`
- `Budget`
- `Category`
- 검증 함수
  - `validate_date`
  - `validate_type`
  - `validate_amount`
  - `validate_month`
  - `parse_tags`
- 직렬화 함수
  - `to_dict`
  - `from_dict`

설계 포인트:
- `Transaction`, `Budget`, `Category`는 `dataclass`
- `__post_init__`에서 필드 검증
- 태그는 리스트로 정규화

### `repository.py`
JSONL 파일 입출력을 담당한다.

#### `TransactionRepository`
- `ensure_files()`
- `stream() -> Iterator[Transaction]`
- `next_id() -> str`
- `add(tx)`
- `get(tx_id)`
- `update(tx_id, changes)`
- `delete(tx_id)`
- `category_in_use(name)`

설계 포인트:
- `stream()`으로 파일을 줄 단위로 읽는다.
- `next_id()`는 전체 거래를 훑어 최대 번호 다음 값을 계산한다.
- `update/delete`는 임시 파일을 만든 뒤 `os.replace` 한다.

#### `CategoryStore`
- `ensure_files(defaults)`
- `list()`
- `add(name)`
- `remove(name)`
- `exists(name)`

설계 포인트:
- 파일이 비어 있으면 기본 카테고리를 자동 생성한다.
- 중복 추가 방지
- 삭제는 전체 재작성 방식

#### `BudgetStore`
- `ensure_files()`
- `set(month, amount)`
- `get(month)`

설계 포인트:
- 월별 예산 한 건을 갱신 또는 추가한다.
- `set()`도 임시 파일 후 교체한다.

### `decorators.py`
공통 관심사를 분리한다.
- `log_call`
- `timed`
- `handle_errors`

실제 적용:
- `cli.main`에 적용되어 로그, 실행 시간, 예외 처리를 분리한다.

### `service.py`
비즈니스 로직 계층이다.
- `SearchQuery`
- `SummaryResult`
- `BudgetService`

주요 메서드:
- `add_transaction`
- `list_transactions`
- `search_transactions`
- `summary`
- `set_budget`
- `category_add`
- `category_list`
- `category_remove`
- `update_transaction`
- `delete_transaction`
- `import_csv`
- `export_csv`

설계 포인트:
- 저장소 조합 및 규칙 검증 담당
- 카테고리 존재 여부 검증
- 검색 조건 정규화
- summary에서 예산 사용률 계산
- CSV 스키마 확인 후 import/export 수행

### `formatter.py`
출력 문자열을 담당한다.
- `format_transaction`
- `format_transactions`
- `format_summary`
- `format_categories`

설계 포인트:
- CLI와 출력 형식 책임을 분리한다.

### `cli.py`
명령 파싱과 사용자 입력을 담당한다.
- `build_parser()`
- `build_service(data_dir)`
- `prompt_add(service)`
- `main(argv=None)`

설계 포인트:
- `argparse` 기반
- `add`는 대화형 입력
- `update`는 옵션 기반
- `category add/remove`는 옵션 또는 입력 프롬프트로 이름을 받는다.
- 각 명령의 성공/실패에 맞는 종료 코드를 반환한다.

## 3. 단계별 실행 계획

### 1단계. 데이터 모델과 예외 정의
- `AppError` 계층 구현
- `Transaction`, `Budget`, `Category` 구현
- 날짜/월/금액/타입/태그 검증 함수 구현

확인:
- 잘못된 날짜, 금액, 타입에서 `ValidationError`가 발생하는지 확인

### 2단계. 저장소 구현
- `transactions.jsonl`, `categories.jsonl`, `budgets.jsonl` 경로 구성
- 파일 자동 생성 로직 구현
- 거래 스트리밍 읽기와 추가 구현
- 예산 저장/조회 구현
- 카테고리 기본값 자동 생성 구현

확인:
- 초기 실행 시 `./data`와 3개 파일이 준비되는지 확인
- 카테고리 목록에 기본값이 들어가는지 확인

### 3단계. 거래 변경 안정성 구현
- `TransactionRepository.update/delete`
- `CategoryStore.remove`
- `BudgetStore.set`
- 임시 파일 + `os.replace` 적용

확인:
- 없는 id 삭제/수정 시 `NotFoundError` 처리
- 저장 파일 재작성 후 결과가 일관적인지 확인

### 4단계. 서비스 계층 구현
- 거래 추가
- 목록/검색
- 월별 요약
- 예산 설정
- 카테고리 추가/삭제
- import/export

확인:
- 카테고리 미등록 거래 추가가 차단되는지 확인
- summary에서 예산 사용률 계산이 맞는지 확인

### 5단계. CLI 구현
- 최상위 parser와 하위 명령 구성
- `add` 대화형 입력
- `update` 옵션 기반 처리
- 포맷터 연동

확인:
- `--help` 출력
- 각 명령이 정상 라우팅되는지 확인

### 6단계. 데코레이터와 종료 코드 적용
- `main`에 `handle_errors`, `log_call`, `timed` 적용

확인:
- 성공 시 0, 오류 시 1 반환
- 오류 메시지가 스택트레이스 없이 출력되는지 확인

### 7단계. 픽스처 기반 인수 시험
- `import.csv`로 데이터 적재
- list/search/summary/category/delete 시나리오 확인

## 4. 인수 시험 목록과 각 시험이 확인하는 것

실행 결과 기준으로 정리한다.

### 1) `budget_app --help`
확인 내용:
- 프로그램 진입점이 정상 동작하는지
- 서브커맨드 목록이 노출되는지
- `--data-dir` 옵션이 존재하는지

실행 결과:
- `add,list,search,summary,budget,category,update,delete,import,export` 표시

### 2) `budget_app --data-dir ./data category list`
확인 내용:
- 저장 폴더 초기화
- 기본 카테고리 자동 생성
- 카테고리 목록 출력 형식

실행 결과:
- `food`, `transport`, `rent`, `etc`

### 3) `budget_app --data-dir ./data import --from import.csv`
확인 내용:
- CSV import 동작
- 필수 스키마 처리
- 거래 5건 저장
- 완료 메시지 형식

실행 결과:
- `[완료] imported=5, skipped=0`

### 4) `budget_app --data-dir ./data list --limit 3`
확인 내용:
- 최신순 정렬
- limit 적용
- 거래 포맷 출력

실행 결과:
- 최신 거래 3건 출력
- 첫 행에 `2024-03-30` 확인

### 5) `budget_app --data-dir ./data summary --month 2024-03 --top 3`
확인 내용:
- 월 필터링
- 총 수입/지출/잔액 계산
- 카테고리별 지출 TOP N 계산

실행 결과:
- 총 지출 `215000원`

### 6) `budget_app --data-dir ./data budget set --month 2024-03 --amount 500000`
확인 내용:
- 예산 저장
- 월 형식 및 금액 검증
- 저장 완료 메시지

실행 결과:
- `[저장 완료] 2024-03 예산 500000원`

### 7) `budget_app --data-dir ./data summary --month 2024-03 --top 3`
확인 내용:
- summary와 budget 연계
- 사용률 계산

실행 결과:
- `예산: 500000원 (사용률 43.0%)`

### 8) `budget_app --data-dir ./data search --category food --type expense`
확인 내용:
- 카테고리/타입 조건 검색
- 최신순 출력

실행 결과:
- `food` 지출 2건 출력
- 다만 시험 기대값 `45000`은 출력 형식에 직접 나타나지 않아 이 항목은 실패 처리됨

### 9) `budget_app --data-dir ./data delete --id TX-999999`
확인 내용:
- 없는 id 삭제 오류 처리
- 스택트레이스 없는 메시지 출력
- 힌트 출력

실행 결과:
- `[오류] 없는 데이터입니다.`
- `[힌트] id를 다시 확인하세요.`

### 10) `budget_app --data-dir ./data category remove food`
확인 내용:
- 사용 중 카테고리 삭제 방지
- 충돌 오류 메시지와 힌트 출력

실행 결과:
- `[오류] 사용 중인 카테고리는 삭제할 수 없습니다.`

### 11) `budget_app --data-dir ./data summary --month 2024-08 --top 3`
확인 내용:
- 데이터 없는 월 처리

실행 결과:
- `데이터 없음`

### 공통 확인
모든 통과 실행에서 함께 확인된 내용:
- `main`에 로그 데코레이터 적용: `[LOG] main called`
- 시간 측정 데코레이터 적용: `[TIME] main: ...s`

## 5. 위험 요소와 대응

### 1) 검색 결과와 시험 기대값 불일치
위험:
- `search --category food --type expense`는 개별 거래를 출력한다.
- 시험 기대값은 합계 `45000`을 기대한 것으로 보이지만 현재 구현은 합계를 출력하지 않는다.

대응:
- 문서와 시험 기준을 “검색은 거래 목록 출력”으로 맞춘다.
- 합계가 필요하면 summary 또는 별도 요구사항으로 분리해야 한다.

### 2) 검색은 저장소 스트리밍 후 메모리 정렬
위험:
- `search_transactions()`는 `stream()`으로 읽지만, 매칭 결과를 리스트에 모은 뒤 정렬한다.
- 매우 큰 데이터에서는 메모리 사용량이 늘 수 있다.

대응:
- 현재 코드는 저장소 읽기 자체는 스트리밍이다.
- 완전한 스트리밍 최신순이 필요하면 저장 구조나 인덱싱 방식 변경이 필요하다.

### 3) `export --month`의 종료일 계산
위험:
- `--month 2024-03`이면 내부적으로 `2024-03-01`부터 `2024-03-31`까지 사용한다.
- 31일이 없는 달에서도 문자열 비교 방식이라 동작은 되지만 달 말 계산을 명시적으로 하지 않는다.

대응:
- 현재 구현 범위에서는 문자열 날짜 비교로 필터링된다.
- 더 엄밀하게 하려면 실제 달의 마지막 날짜 계산 로직을 추가한다.

### 4) import 파일 열기 오류 처리
위험:
- `import_csv()`와 `export_csv()`에서 파일 열기 실패는 `AppError`로 변환되지 않는다.
- 이 경우 `handle_errors`가 일반 예외로 처리해 포괄 메시지를 출력한다.

대응:
- 현재도 사용자에게 스택트레이스는 노출되지 않는다.
- 더 명확한 메시지가 필요하면 `StorageError`로 감싸는 보완이 필요하다.

### 5) id 발급 성능
위험:
- `next_id()`는 거래 파일 전체를 순회해 최대 번호를 찾는다.
- 데이터가 많아질수록 추가 시 비용이 커진다.

대응:
- 현재 요구사항 범위에서는 단순하고 안전한 방식이다.
- 확장 시 별도 시퀀스 파일을 두는 방식이 필요하다.

### 6) 카테고리 이름 중복/정규화
위험:
- 공백 제거는 하지만 대소문자 통합은 하지 않는다.
- `food`와 `Food`는 다른 이름으로 저장될 수 있다.

대응:
- 현재 구현 계약은 문자열 strip 기준이다.
- 대소문자 통합 정책이 필요하면 명시적으로 추가해야 한다.

## 6. 실제 동작 기준 사용 방법

### 실행
- `python -m budget_app --help`
- `python -m budget_app --data-dir ./data <command>`

### 주요 명령
- 거래 추가: `python -m budget_app add`
- 목록 조회: `python -m budget_app list --limit 3`
- 검색: `python -m budget_app search --category food --type expense`
- 월 요약: `python -m budget_app summary --month 2024-03 --top 3`
- 예산 설정: `python -m budget_app budget set --month 2024-03 --amount 500000`
- 카테고리 목록: `python -m budget_app category list`
- 카테고리 추가: `python -m budget_app category add --name leisure`
- 카테고리 삭제: `python -m budget_app category remove food`
- 거래 수정:
  - `python -m budget_app update --id TX-000001 --memo 점심값 --amount 16000`
- 거래 삭제:
  - `python -m budget_app delete --id TX-000001`
- 가져오기:
  - `python -m budget_app import --from import.csv`
- 내보내기:
  - `python -m budget_app export --out export.csv --month 2024-03`

## 7. 저장 파일 위치와 형식

기본 폴더:
- `./data`

파일:
- `transactions.jsonl`
- `categories.jsonl`
- `budgets.jsonl`

형식:
- UTF-8
- JSONL 한 줄당 한 레코드

예시 개념:
- 거래: `id`, `type`, `date`, `amount`,
