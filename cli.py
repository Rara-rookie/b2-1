import argparse

from .decorators import handle_errors, log_call, timed
from .formatter import format_categories, format_summary, format_transaction, format_transactions
from .models import Transaction, parse_tags, validate_amount
from .repository import BudgetStore, CategoryStore, TransactionRepository
from .service import BudgetService, SearchQuery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="budget_app")
    parser.add_argument("--data-dir", default="./data")

    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add")
    _ = add_parser

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=10)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--from", dest="date_from")
    search_parser.add_argument("--to", dest="date_to")
    search_parser.add_argument("--category")
    search_parser.add_argument("--type")
    search_parser.add_argument("--q")
    search_parser.add_argument("--tag")

    summary_parser = subparsers.add_parser("summary")
    summary_parser.add_argument("--month", required=True)
    summary_parser.add_argument("--top", type=int, default=3)

    budget_parser = subparsers.add_parser("budget")
    budget_subparsers = budget_parser.add_subparsers(dest="budget_command")
    budget_set_parser = budget_subparsers.add_parser("set")
    budget_set_parser.add_argument("--month", required=True)
    budget_set_parser.add_argument("--amount", required=True)
    budget_parser.set_defaults(_subparser_ref=budget_parser)

    category_parser = subparsers.add_parser("category")
    category_subparsers = category_parser.add_subparsers(dest="category_command")

    category_add_parser = category_subparsers.add_parser("add")
    category_add_parser.add_argument("--name")
    category_add_parser.add_argument("name_positional", nargs="?")

    category_subparsers.add_parser("list")

    category_remove_parser = category_subparsers.add_parser("remove")
    category_remove_parser.add_argument("--name")
    category_remove_parser.add_argument("name_positional", nargs="?")
    category_parser.set_defaults(_subparser_ref=category_parser)

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--id", required=True)
    update_parser.add_argument("--date")
    update_parser.add_argument("--type")
    update_parser.add_argument("--category")
    update_parser.add_argument("--amount")
    update_parser.add_argument("--memo")
    update_parser.add_argument("--tags")

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("--id", required=True)

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--from", dest="from_path", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--out", required=True)
    export_parser.add_argument("--month")
    export_parser.add_argument("--from", dest="date_from")
    export_parser.add_argument("--to", dest="date_to")
    export_parser.add_argument("--category")
    export_parser.add_argument("--type")
    export_parser.add_argument("--q")
    export_parser.add_argument("--tag")

    return parser


def build_service(data_dir: str) -> BudgetService:
    tx_repo = TransactionRepository(data_dir)
    cat_store = CategoryStore(data_dir)
    budget_store = BudgetStore(data_dir)
    return BudgetService(tx_repo, cat_store, budget_store)


def prompt_add(service: BudgetService) -> Transaction:
    while True:
        try:
            date = input("날짜(YYYY-MM-DD): ")
            type_ = input("타입(income/expense): ")
            category = input("카테고리: ")
            amount_raw = input("금액(양수): ")
            memo = input("메모(선택): ")
            tags_raw = input("태그(쉼표로 구분, 없으면 엔터): ")
            amount = validate_amount(amount_raw)
            tags = parse_tags(tags_raw)
            return service.add_transaction(date, type_, category, amount, memo, tags)
        except Exception as exc:
            from .errors import AppError
            if isinstance(exc, AppError):
                print(f"[오류] {exc.message}")
                if exc.hint:
                    print(f"[힌트] {exc.hint}")
                continue
            raise


@handle_errors
@log_call
@timed
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    service = build_service(args.data_dir)

    if args.command == "add":
        tx = prompt_add(service)
        print(f"[저장 완료] id={tx.id}")
        return 0

    if args.command == "list":
        txs = service.list_transactions(args.limit)
        print(format_transactions(txs))
        return 0

    if args.command == "search":
        query = SearchQuery(
            date_from=args.date_from,
            date_to=args.date_to,
            category=args.category,
            type=args.type,
            q=args.q,
            tag=args.tag,
        )
        txs = list(service.search_transactions(query))
        print(format_transactions(txs))
        return 0

    if args.command == "summary":
        result = service.summary(args.month, args.top)
        print(format_summary(result))
        return 0

    if args.command == "budget":
        if args.budget_command == "set":
            amount = validate_amount(args.amount)
            service.set_budget(args.month, amount)
            print(f"[저장 완료] {args.month} 예산 {amount}원")
            return 0
        args._subparser_ref.print_help()
        return 1

    if args.command == "category":
        if args.category_command == "add":
            name = args.name if args.name is not None else args.name_positional
            name = name if name is not None else input("카테고리명: ")
            service.category_add(name)
            print(f"[저장 완료] category={name.strip()}")
            return 0
        if args.category_command == "list":
            print(format_categories(service.category_list()))
            return 0
        if args.category_command == "remove":
            name = args.name if args.name is not None else args.name_positional
            name = name if name is not None else input("카테고리명: ")
            service.category_remove(name)
            print(f"[삭제 완료] category={name.strip()}")
            return 0
        args._subparser_ref.print_help()
        return 1

    if args.command == "update":
        changes: dict[str, object] = {}
        if args.date is not None:
            changes["date"] = args.date
        if args.type is not None:
            changes["type"] = args.type
        if args.category is not None:
            changes["category"] = args.category
        if args.amount is not None:
            changes["amount"] = validate_amount(args.amount)
        if args.memo is not None:
            changes["memo"] = args.memo
        if args.tags is not None:
            changes["tags"] = parse_tags(args.tags)
        tx = service.update_transaction(args.id, changes)
        print(f"[수정 완료] {format_transaction(tx)}")
        return 0

    if args.command == "delete":
        service.delete_transaction(args.id)
        print(f"[삭제 완료] id={args.id}")
        return 0

    if args.command == "import":
        imported, skipped = service.import_csv(args.from_path)
        print(f"[완료] imported={imported}, skipped={skipped}")
        return 0

    if args.command == "export":
        if not args.month and not (args.date_from and args.date_to):
            parser.error("export는 --month 또는 --from/--to 조건이 필요합니다.")
        date_from = args.date_from
        date_to = args.date_to
        if args.month:
            date_from = f"{args.month}-01"
            date_to = f"{args.month}-31"
        query = SearchQuery(
            date_from=date_from,
            date_to=date_to,
            category=args.category,
            type=args.type,
            q=args.q,
            tag=args.tag,
        )
        count = service.export_csv(args.out, query)
        print(f"[완료] {args.out} ({count} records)")
        return 0

    parser.print_help()
    return 1
