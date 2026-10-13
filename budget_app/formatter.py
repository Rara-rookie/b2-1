from .errors import AppError
from .models import Transaction
from .service import SummaryResult


def format_error(exc: AppError) -> str:
    lines: list[str] = []
    for error in exc.unpack():
        lines.append(f"[오류] {error.message}")
        if error.hint:
            lines.append(f"[힌트] {error.hint}")
    return "\n".join(lines)


def format_transaction(tx: Transaction) -> str:
    memo = tx.memo or ""
    return f"{tx.id} | {tx.date} | {tx.type} | {tx.category} | {tx.amount} | {memo}"


def format_transactions(txs: list[Transaction]) -> str:
    if not txs:
        return "데이터 없음"
    return "\n".join(format_transaction(tx) for tx in txs)


def format_summary(result: SummaryResult) -> str:
    if result.total_income == 0 and result.total_expense == 0:
        return "데이터 없음"

    lines: list[str] = [
        f"총 수입: {result.total_income}원",
        f"총 지출: {result.total_expense}원",
        f"잔액: {result.balance}원",
    ]

    if result.budget is not None and result.usage_rate is not None:
        lines.append(f"예산: {result.budget}원 (사용률 {result.usage_rate:.1f}%)")
        if result.over_budget:
            lines.append("[경고] 예산을 초과했습니다.")

    lines.append("")
    lines.append(f"지출 TOP {len(result.top_expenses)}")

    if not result.top_expenses:
        lines.append("없음")
    else:
        for index, item in enumerate(result.top_expenses, start=1):
            category, amount = item
            lines.append(f"{index}) {category} {amount}원")

    return "\n".join(lines)


def format_categories(names: list[str]) -> str:
    if not names:
        return "데이터 없음"
    return "\n".join(f"- {name}" for name in names)