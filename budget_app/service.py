from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Iterator, cast

from .errors import AppError, ConflictError, ErrorCollector, StorageError, ValidationError
from .models import Transaction, parse_tags, validate_amount, validate_date, validate_month, validate_type


@dataclass
class SearchQuery:
    date_from: str | None = None
    date_to: str | None = None
    category: str | None = None
    type: str | None = None
    q: str | None = None
    tag: str | None = None


@dataclass
class ImportFailure:
    line: int
    reason: str
    hint: str | None
    row: dict[str, str]


@dataclass
class ImportResult:
    imported: int
    skipped: int
    failures: list[ImportFailure]
    report_path: str | None = None
    rolled_back: bool = False


@dataclass
class SummaryResult:
    month: str
    total_income: int
    total_expense: int
    balance: int
    top_expenses: list[tuple[str, int]]
    budget: int | None
    usage_rate: float | None
    over_budget: bool


class BudgetService:
    def __init__(self, tx_repo, cat_store, budget_store) -> None:
        self.tx_repo = tx_repo
        self.cat_store = cat_store
        self.budget_store = budget_store
        self._default_categories: list[str] = ["food", "transport", "rent", "etc"]
        self.tx_repo.ensure_files()
        self.cat_store.ensure_files(self._default_categories)
        self.budget_store.ensure_files()

    def add_transaction(
        self,
        date: str,
        type_: str,
        category: str,
        amount: object,
        memo: str,
        tags: object,
    ) -> Transaction:
        # 항목마다 독립적으로 검증해 실패를 모은다. 날짜가 틀렸다고 끊으면 카테고리·금액 오류를
        # 사용자가 알 수 없어, 고칠 때마다 다음 오류를 새로 만나게 된다.
        collector = ErrorCollector()
        validated_date = collector.collect(validate_date, date)
        validated_type = collector.collect(validate_type, type_)
        validated_category = collector.collect(self._validate_category, category)
        validated_amount = collector.collect(validate_amount, amount)
        normalized_tags = collector.collect(self._normalize_tags, tags)
        collector.raise_if_any()

        # 여기까지 왔으면 모든 검증이 성공했으므로 None 이 아니다.
        tx = Transaction(
            id=self.tx_repo.next_id(),
            type=cast(str, validated_type),
            date=cast(str, validated_date),
            amount=cast(int, validated_amount),
            category=cast(str, validated_category),
            memo=memo if isinstance(memo, str) else str(memo),
            tags=cast("list[str]", normalized_tags),
        )
        self.tx_repo.add(tx)
        return tx

    def list_transactions(self, limit: int) -> list[Transaction]:
        validated_limit = self._validate_limit(limit)
        recent: list[Transaction] = []
        for tx in self.tx_repo.stream():
            recent.append(tx)
            recent.sort(key=lambda item: (item.date, item.id), reverse=True)
            if len(recent) > validated_limit:
                recent.pop()
        return recent

    def search_transactions(self, query: SearchQuery) -> Iterator[Transaction]:
        normalized = self._normalize_query(query)
        matched: list[Transaction] = []
        for tx in self.tx_repo.stream():
            if self._matches_query(tx, normalized):
                matched.append(tx)
        matched.sort(key=lambda item: (item.date, item.id), reverse=True)
        for tx in matched:
            yield tx

    def summary(self, month: str, top: int) -> SummaryResult:
        validated_month = validate_month(month)
        validated_top = self._validate_top(top)

        total_income = 0
        total_expense = 0
        category_expenses: dict[str, int] = {}

        for tx in self.tx_repo.stream():
            if not tx.date.startswith(validated_month + "-"):
                continue
            if tx.type == "income":
                total_income += tx.amount
            elif tx.type == "expense":
                total_expense += tx.amount
                category_expenses[tx.category] = category_expenses.get(tx.category, 0) + tx.amount

        sorted_expenses = sorted(
            category_expenses.items(),
            key=lambda item: (-item[1], item[0]),
        )[:validated_top]

        budget = self.budget_store.get(validated_month)
        usage_rate: float | None = None
        over_budget = False
        if budget is not None:
            if budget > 0:
                usage_rate = (total_expense / budget) * 100
                over_budget = total_expense > budget
            else:
                usage_rate = None
                over_budget = total_expense > 0

        return SummaryResult(
            month=validated_month,
            total_income=total_income,
            total_expense=total_expense,
            balance=total_income - total_expense,
            top_expenses=sorted_expenses,
            budget=budget,
            usage_rate=usage_rate,
            over_budget=over_budget,
        )

    def set_budget(self, month: str, amount: int) -> None:
        validated_month = validate_month(month)
        validated_amount = validate_amount(amount)
        self.budget_store.set(validated_month, validated_amount)

    def category_add(self, name: str) -> None:
        cleaned = self._clean_category_name(name)
        self.cat_store.add(cleaned)

    def category_list(self) -> list[str]:
        return self.cat_store.list()

    def category_remove(self, name: str) -> None:
        cleaned = self._clean_category_name(name)
        if self.tx_repo.category_in_use(cleaned):
            raise ConflictError(
                "사용 중인 카테고리는 삭제할 수 없습니다.",
                "해당 카테고리를 사용하는 거래를 수정하거나 삭제한 후 다시 시도하세요.",
            )
        self.cat_store.remove(cleaned)

    def update_transaction(self, tx_id: str, changes: dict[str, object]) -> Transaction:
        if not isinstance(tx_id, str) or not tx_id.strip():
            raise ValidationError(
                "id가 올바르지 않습니다.",
                "예: TX-000001",
            )
        if not isinstance(changes, dict) or not changes:
            raise ValidationError(
                "수정할 항목이 없습니다.",
                "--date, --type, --category, --amount, --memo, --tags 중 하나 이상 입력하세요.",
            )

        normalized: dict[str, object] = {}
        collector = ErrorCollector()
        for key, value in changes.items():
            if key == "id":
                continue
            if key == "date":
                normalized["date"] = collector.collect(validate_date, str(value))
            elif key == "type":
                normalized["type"] = collector.collect(validate_type, str(value))
            elif key == "category":
                normalized["category"] = collector.collect(self._validate_category, str(value))
            elif key == "amount":
                normalized["amount"] = collector.collect(validate_amount, value)
            elif key == "memo":
                normalized["memo"] = value if isinstance(value, str) else str(value)
            elif key == "tags":
                normalized["tags"] = collector.collect(self._normalize_tags, value)
            else:
                continue
        collector.raise_if_any()

        if not normalized:
            raise ValidationError(
                "수정할 항목이 없습니다.",
                "--date, --type, --category, --amount, --memo, --tags 중 하나 이상 입력하세요.",
            )

        return self.tx_repo.update(tx_id.strip(), normalized)

    def delete_transaction(self, tx_id: str) -> None:
        if not isinstance(tx_id, str) or not tx_id.strip():
            raise ValidationError(
                "id가 올바르지 않습니다.",
                "예: TX-000001",
            )
        self.tx_repo.delete(tx_id.strip())

    def import_csv(
        self,
        path: str,
        atomic: bool = False,
        report_path: str | None = None,
    ) -> ImportResult:
        """CSV 를 가져온다.

        기본은 부분 성공이다. 검증에 실패한 행만 건너뛰고 나머지를 반영한 뒤, 행 번호와 이유를 돌려준다.
        atomic=True 면 먼저 전체를 검증해 한 행이라도 실패하면 아무것도 쓰지 않는다(전체 롤백).
        report_path 를 주면 실패 행을 같은 스키마 + 이유 컬럼으로 저장해 고쳐서 다시 넣을 수 있게 한다.
        """
        if atomic:
            failures = [f for _, f in self._scan_csv(path) if f is not None]
            if failures:
                written = self._write_failure_report(report_path, failures)
                return ImportResult(0, len(failures), failures, written, True)

        imported = 0
        failures = []
        for row, failure in self._scan_csv(path):
            if failure is not None:
                failures.append(failure)
                continue
            self.add_transaction(
                date=row["date"],
                type_=row["type"],
                category=row["category"],
                amount=row["amount"],
                memo=row["memo"],
                tags=row["tags"],
            )
            imported += 1

        written = self._write_failure_report(report_path, failures)
        return ImportResult(imported, len(failures), failures, written, False)

    # 한 행씩 읽어 (행, 실패) 를 돌려준다. 실패가 None 이면 그 행은 검증을 통과했다.
    # 제너레이터로 두어 파일 전체를 메모리에 올리지 않는다(검증 단계와 적용 단계가 각각 한 번씩 읽는다).
    def _scan_csv(self, path: str) -> Iterator[tuple[dict[str, str], ImportFailure | None]]:
        columns = ["date", "type", "category", "amount", "memo", "tags"]
        with open(path, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValidationError(
                    "CSV 헤더가 없습니다.",
                    "헤더 포함 UTF-8 CSV 파일을 사용하세요.",
                )
            for name in ["date", "type", "category", "amount"]:
                if name not in reader.fieldnames:
                    raise ValidationError(
                        "CSV 스키마가 올바르지 않습니다.",
                        "필수 컬럼: date,type,category,amount",
                    )

            for raw in reader:
                line = reader.line_num
                row = {key: str(raw.get(key) or "") for key in columns}
                errors = self._row_errors(row)
                if errors:
                    yield row, ImportFailure(
                        line=line,
                        reason="; ".join(e.message for e in errors),
                        hint=errors[0].hint,
                        row=row,
                    )
                else:
                    yield row, None

    # 한 행의 모든 항목을 검증해 실패를 모은다(첫 실패에서 멈추지 않는다).
    def _row_errors(self, row: dict[str, str]) -> list[AppError]:
        collector = ErrorCollector()
        collector.collect(validate_date, row["date"])
        collector.collect(validate_type, row["type"])
        collector.collect(self._validate_category, row["category"])
        collector.collect(validate_amount, row["amount"])
        collector.collect(self._normalize_tags, row["tags"])
        return collector.errors

    # 실패 행을 원본 스키마 + line/reason 컬럼으로 저장한다. 고친 뒤 그대로 다시 import 할 수 있다.
    def _write_failure_report(
        self,
        report_path: str | None,
        failures: list[ImportFailure],
    ) -> str | None:
        if not report_path or not failures:
            return None
        columns = ["date", "type", "category", "amount", "memo", "tags"]
        try:
            with open(report_path, "w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["line", "reason"] + columns)
                writer.writeheader()
                for failure in failures:
                    record = {"line": failure.line, "reason": failure.reason}
                    record.update(failure.row)
                    writer.writerow(record)
        except OSError as exc:
            raise StorageError(
                "실패 행 리포트를 저장할 수 없습니다.",
                "--report 경로의 폴더와 권한을 확인하세요.",
            ) from exc
        return report_path

    def export_csv(self, path: str, query: SearchQuery) -> int:
        normalized = self._normalize_query(query)
        if not normalized.date_from and not normalized.date_to:
            raise ValidationError(
                "내보내기 조건이 필요합니다.",
                "--month 또는 --from/--to 조건을 입력하세요.",
            )

        count = 0
        with open(path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["date", "type", "category", "amount", "memo", "tags"],
            )
            writer.writeheader()
            for tx in self.search_transactions(normalized):
                writer.writerow(
                    {
                        "date": tx.date,
                        "type": tx.type,
                        "category": tx.category,
                        "amount": tx.amount,
                        "memo": tx.memo,
                        "tags": ",".join(tx.tags or []),
                    }
                )
                count += 1
        return count

    def _validate_category(self, category: str) -> str:
        cleaned = self._clean_category_name(category)
        if not self.cat_store.exists(cleaned):
            raise ValidationError(
                "존재하지 않는 카테고리입니다.",
                "category list로 목록을 확인하거나 category add로 먼저 등록하세요.",
            )
        return cleaned

    def _clean_category_name(self, name: str) -> str:
        cleaned = name.strip() if isinstance(name, str) else str(name).strip()
        if not cleaned:
            raise ValidationError(
                "카테고리명이 올바르지 않습니다.",
                "비어 있지 않은 카테고리명을 입력하세요.",
            )
        return cleaned

    def _normalize_tags(self, tags: object) -> list[str]:
        if tags is None:
            return []
        if isinstance(tags, list):
            result: list[str] = []
            for tag in tags:
                text = str(tag).strip()
                if text:
                    result.append(text)
            return result
        if isinstance(tags, str):
            return parse_tags(tags)
        raise ValidationError(
            "태그 형식이 올바르지 않습니다.",
            "쉼표(,)로 구분된 문자열을 입력하세요.",
        )

    def _normalize_query(self, query: SearchQuery) -> SearchQuery:
        date_from = validate_date(query.date_from) if query.date_from else None
        date_to = validate_date(query.date_to) if query.date_to else None
        if date_from and date_to and date_from > date_to:
            raise ValidationError(
                "기간 범위가 올바르지 않습니다.",
                "--from 이 --to 보다 늦을 수 없습니다.",
            )

        category = None
        if query.category is not None:
            category = self._clean_category_name(query.category)
            if not self.cat_store.exists(category):
                raise ValidationError(
                    "존재하지 않는 카테고리입니다.",
                    "category list로 목록을 확인하거나 category add로 먼저 등록하세요.",
                )

        type_ = validate_type(query.type) if query.type else None
        q = query.q.strip() if isinstance(query.q, str) else query.q
        tag = query.tag.strip() if isinstance(query.tag, str) else query.tag

        return SearchQuery(
            date_from=date_from,
            date_to=date_to,
            category=category,
            type=type_,
            q=q if q else None,
            tag=tag if tag else None,
        )

    def _matches_query(self, tx: Transaction, query: SearchQuery) -> bool:
        if query.date_from and tx.date < query.date_from:
            return False
        if query.date_to and tx.date > query.date_to:
            return False
        if query.category and tx.category != query.category:
            return False
        if query.type and tx.type != query.type:
            return False
        if query.q and query.q.lower() not in tx.memo.lower():
            return False
        if query.tag and query.tag not in (tx.tags or []):
            return False
        return True

    def _validate_limit(self, limit: int) -> int:
        value = validate_amount(limit)
        return value

    def _validate_top(self, top: int) -> int:
        value = validate_amount(top)
        return value