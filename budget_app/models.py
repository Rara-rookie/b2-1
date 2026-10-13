from dataclasses import dataclass, field
from datetime import datetime

from .errors import ValidationError


@dataclass
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ''
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.type = validate_type(self.type)
        self.date = validate_date(self.date)
        self.amount = validate_amount(self.amount)
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValidationError(
                "카테고리가 올바르지 않습니다.",
                "등록된 카테고리 이름을 입력하세요.",
            )
        self.category = self.category.strip()
        if not isinstance(self.memo, str):
            self.memo = str(self.memo)
        if self.tags is None:
            self.tags = []
        elif isinstance(self.tags, list):
            self.tags = [str(tag).strip() for tag in self.tags if str(tag).strip()]
        else:
            raise ValidationError(
                "태그 형식이 올바르지 않습니다.",
                "쉼표(,)로 구분된 문자열 또는 목록이어야 합니다.",
            )


@dataclass
class Budget:
    month: str
    amount: int

    def __post_init__(self) -> None:
        self.month = validate_month(self.month)
        self.amount = validate_amount(self.amount)


@dataclass
class Category:
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError(
                "카테고리명이 올바르지 않습니다.",
                "빈 값이 아닌 카테고리명을 입력하세요.",
            )
        self.name = self.name.strip()



def validate_date(date: str) -> str:
    if not isinstance(date, str):
        raise ValidationError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).",
            "예: 2024-01-15",
        )
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).",
            "예: 2024-01-15",
        )
    return parsed.strftime("%Y-%m-%d")



def validate_type(type_: str) -> str:
    if type_ not in ("income", "expense"):
        raise ValidationError(
            "타입은 income 또는 expense 여야 합니다.",
            "예: income",
        )
    return type_



def validate_amount(amount: object) -> int:
    if isinstance(amount, bool):
        raise ValidationError(
            "금액은 양수여야 합니다.",
            "1 이상의 정수를 입력하세요.",
        )

    value: int
    if isinstance(amount, int):
        value = amount
    elif isinstance(amount, str):
        text = amount.strip()
        if not text:
            raise ValidationError(
                "금액은 양수여야 합니다.",
                "1 이상의 정수를 입력하세요.",
            )
        try:
            value = int(text)
        except ValueError:
            raise ValidationError(
                "금액은 양수여야 합니다.",
                "1 이상의 정수를 입력하세요.",
            )
    else:
        raise ValidationError(
            "금액은 양수여야 합니다.",
            "1 이상의 정수를 입력하세요.",
        )

    if value <= 0:
        raise ValidationError(
            "금액은 양수여야 합니다.",
            "1 이상의 정수를 입력하세요.",
        )
    return value



def validate_month(month: str) -> str:
    if not isinstance(month, str):
        raise ValidationError(
            "월 형식이 올바르지 않습니다 (YYYY-MM).",
            "예: 2024-01",
        )
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise ValidationError(
            "월 형식이 올바르지 않습니다 (YYYY-MM).",
            "예: 2024-01",
        )
    return parsed.strftime("%Y-%m")



def parse_tags(raw: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, str):
        raise ValidationError(
            "태그 형식이 올바르지 않습니다.",
            "쉼표(,)로 구분된 문자열을 입력하세요.",
        )
    parts = raw.split(",")
    result: list[str] = []
    for part in parts:
        tag = part.strip()
        if tag:
            result.append(tag)
    return result



def to_dict(tx: Transaction) -> dict[str, object]:
    return {
        "id": tx.id,
        "type": validate_type(tx.type),
        "date": validate_date(tx.date),
        "amount": validate_amount(tx.amount),
        "category": tx.category,
        "memo": tx.memo if isinstance(tx.memo, str) else "",
        "tags": list(tx.tags),
    }



def from_dict(data: dict[str, object]) -> Transaction:
    tx_id_obj = data.get("id", "")
    category_obj = data.get("category", "")
    memo_obj = data.get("memo", "")
    tags_obj = data.get("tags", [])

    tx_id = tx_id_obj if isinstance(tx_id_obj, str) else str(tx_id_obj)
    category = category_obj if isinstance(category_obj, str) else str(category_obj)
    memo = memo_obj if isinstance(memo_obj, str) else str(memo_obj)

    tags: list[str]
    if tags_obj is None:
        tags = []
    elif isinstance(tags_obj, list):
        tags = [str(tag).strip() for tag in tags_obj if str(tag).strip()]
    elif isinstance(tags_obj, str):
        tags = parse_tags(tags_obj)
    else:
        raise ValidationError(
            "태그 형식이 올바르지 않습니다.",
            "쉼표(,)로 구분된 문자열 또는 목록이어야 합니다.",
        )

    return Transaction(
        id=tx_id,
        type=validate_type(str(data.get("type", ""))),
        date=validate_date(str(data.get("date", ""))),
        amount=validate_amount(data.get("amount")),
        category=category,
        memo=memo,
        tags=tags,
    )
