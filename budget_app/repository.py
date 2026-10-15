import io
import json
import os
import tempfile
from typing import Iterator

from .errors import ConflictError, NotFoundError, StorageError, ValidationError
from .models import Budget, Category, Transaction, from_dict, to_dict, validate_amount, validate_month


class TransactionRepository:
    def __init__(self, data_dir: str) -> None:
        self.data_dir: str = data_dir
        self.path: str = os.path.join(data_dir, "transactions.jsonl")

    def ensure_files(self) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            if not os.path.exists(self.path):
                with open(self.path, "w", encoding="utf-8"):
                    pass
        except OSError as exc:
            raise StorageError(
                "거래 저장 파일을 준비할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def stream(self) -> Iterator[Transaction]:
        self.ensure_files()
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                for line in file:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                        if not isinstance(data, dict):
                            raise StorageError(
                                "거래 저장 파일 형식이 올바르지 않습니다.",
                                "transactions.jsonl 파일 내용을 확인하세요.",
                            )
                        yield from_dict(data)
                    except json.JSONDecodeError as exc:
                        raise StorageError(
                            "거래 저장 파일 형식이 올바르지 않습니다.",
                            "transactions.jsonl 파일 내용을 확인하세요.",
                        ) from exc
        except OSError as exc:
            raise StorageError(
                "거래 저장 파일을 읽을 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def reverse_stream(self) -> Iterator[Transaction]:
        self.ensure_files()
        try:
            with open(self.path, "rb") as file:
                file.seek(0, io.SEEK_END)
                position = file.tell()
                buffer = b""
                block_size = 4096

                while position > 0:
                    read_size = min(block_size, position)
                    position -= read_size
                    file.seek(position)
                    chunk = file.read(read_size)
                    buffer = chunk + buffer
                    lines = buffer.split(b"\n")
                    buffer = lines[0]
                    for raw_line in reversed(lines[1:]):
                        text = raw_line.decode("utf-8").strip()
                        if not text:
                            continue
                        try:
                            data = json.loads(text)
                            if not isinstance(data, dict):
                                raise StorageError(
                                    "거래 저장 파일 형식이 올바르지 않습니다.",
                                    "transactions.jsonl 파일 내용을 확인하세요.",
                                )
                            yield from_dict(data)
                        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                            raise StorageError(
                                "거래 저장 파일 형식이 올바르지 않습니다.",
                                "transactions.jsonl 파일 내용을 확인하세요.",
                            ) from exc

                if buffer:
                    text = buffer.decode("utf-8").strip()
                    if text:
                        try:
                            data = json.loads(text)
                            if not isinstance(data, dict):
                                raise StorageError(
                                    "거래 저장 파일 형식이 올바르지 않습니다.",
                                    "transactions.jsonl 파일 내용을 확인하세요.",
                                )
                            yield from_dict(data)
                        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                            raise StorageError(
                                "거래 저장 파일 형식이 올바르지 않습니다.",
                                "transactions.jsonl 파일 내용을 확인하세요.",
                            ) from exc
        except OSError as exc:
            raise StorageError(
                "거래 저장 파일을 읽을 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def next_id(self) -> str:
        max_no = 0
        for tx in self.stream():
            if tx.id.startswith("TX-"):
                number = tx.id[3:]
                if number.isdigit():
                    value = int(number)
                    if value > max_no:
                        max_no = value
        return f"TX-{max_no + 1:06d}"

    def add(self, tx: Transaction) -> None:
        self.ensure_files()
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(json.dumps(to_dict(tx), ensure_ascii=False) + "\n")
        except OSError as exc:
            raise StorageError(
                "거래를 저장할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def get(self, tx_id: str) -> Transaction:
        for tx in self.stream():
            if tx.id == tx_id:
                return tx
        raise NotFoundError(
            "없는 데이터입니다.",
            "id를 다시 확인하세요.",
        )

    def update(self, tx_id: str, changes: dict[str, object]) -> Transaction:
        self.ensure_files()
        updated_tx: Transaction | None = None
        found = False
        directory = self.data_dir
        temp_path = ""

        try:
            with open(self.path, "r", encoding="utf-8") as src:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    delete=False,
                    dir=directory,
                ) as tmp:
                    temp_path = tmp.name
                    for line in src:
                        text = line.strip()
                        if not text:
                            continue
                        data = json.loads(text)
                        if not isinstance(data, dict):
                            raise StorageError(
                                "거래 저장 파일 형식이 올바르지 않습니다.",
                                "transactions.jsonl 파일 내용을 확인하세요.",
                            )
                        tx = from_dict(data)
                        if tx.id == tx_id:
                            found = True
                            merged = {
                                "id": tx.id,
                                "type": tx.type,
                                "date": tx.date,
                                "amount": tx.amount,
                                "category": tx.category,
                                "memo": tx.memo,
                                "tags": list(tx.tags) if tx.tags is not None else [],
                            }
                            for key, value in changes.items():
                                if key in merged and key != "id":
                                    merged[key] = value
                            updated_tx = from_dict(merged)
                            tmp.write(json.dumps(to_dict(updated_tx), ensure_ascii=False) + "\n")
                        else:
                            tmp.write(json.dumps(to_dict(tx), ensure_ascii=False) + "\n")

            if not found:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                raise NotFoundError(
                    "없는 데이터입니다.",
                    "id를 다시 확인하세요.",
                )

            os.replace(temp_path, self.path)
            temp_path = ""

            if updated_tx is None:
                raise StorageError(
                    "거래를 수정할 수 없습니다.",
                    "입력값과 저장 파일 상태를 확인하세요.",
                )
            return updated_tx
        except NotFoundError:
            raise
        except json.JSONDecodeError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "거래 저장 파일 형식이 올바르지 않습니다.",
                "transactions.jsonl 파일 내용을 확인하세요.",
            ) from exc
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "거래를 수정할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def delete(self, tx_id: str) -> None:
        self.ensure_files()
        found = False
        directory = self.data_dir
        temp_path = ""

        try:
            with open(self.path, "r", encoding="utf-8") as src:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    delete=False,
                    dir=directory,
                ) as tmp:
                    temp_path = tmp.name
                    for line in src:
                        text = line.strip()
                        if not text:
                            continue
                        data = json.loads(text)
                        if not isinstance(data, dict):
                            raise StorageError(
                                "거래 저장 파일 형식이 올바르지 않습니다.",
                                "transactions.jsonl 파일 내용을 확인하세요.",
                            )
                        tx = from_dict(data)
                        if tx.id == tx_id:
                            found = True
                            continue
                        tmp.write(json.dumps(to_dict(tx), ensure_ascii=False) + "\n")

            if not found:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                raise NotFoundError(
                    "없는 데이터입니다.",
                    "id를 다시 확인하세요.",
                )

            os.replace(temp_path, self.path)
            temp_path = ""
        except NotFoundError:
            raise
        except json.JSONDecodeError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "거래 저장 파일 형식이 올바르지 않습니다.",
                "transactions.jsonl 파일 내용을 확인하세요.",
            ) from exc
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "거래를 삭제할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def category_in_use(self, name: str) -> bool:
        for tx in self.stream():
            if tx.category == name:
                return True
        return False


class CategoryStore:
    def __init__(self, data_dir: str) -> None:
        self.data_dir: str = data_dir
        self.path: str = os.path.join(data_dir, "categories.jsonl")

    def ensure_files(self, defaults: list[str]) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            if not os.path.exists(self.path):
                with open(self.path, "w", encoding="utf-8"):
                    pass
            if not self.list():
                with open(self.path, "a", encoding="utf-8") as file:
                    for name in defaults:
                        category = Category(name=name)
                        file.write(json.dumps({"name": category.name}, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise StorageError(
                "카테고리 저장 파일을 준비할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def list(self) -> list[str]:
        try:
            if not os.path.exists(self.path):
                return []
            names: list[str] = []
            with open(self.path, "r", encoding="utf-8") as file:
                for line in file:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise StorageError(
                            "카테고리 저장 파일 형식이 올바르지 않습니다.",
                            "categories.jsonl 파일 내용을 확인하세요.",
                        ) from exc
                    if not isinstance(data, dict):
                        raise StorageError(
                            "카테고리 저장 파일 형식이 올바르지 않습니다.",
                            "categories.jsonl 파일 내용을 확인하세요.",
                        )
                    raw = data.get("name", "")
                    name = raw if isinstance(raw, str) else str(raw)
                    if name and name not in names:
                        names.append(name)
            return names
        except OSError as exc:
            raise StorageError(
                "카테고리 저장 파일을 읽을 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def add(self, name: str) -> None:
        self.ensure_files([])
        cleaned = name.strip()
        if self.exists(cleaned):
            raise ConflictError(
                "이미 존재하는 카테고리입니다.",
                "다른 이름을 입력하세요.",
            )
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                file.write(json.dumps({"name": cleaned}, ensure_ascii=False) + "\n")
        except OSError as exc:
            raise StorageError(
                "카테고리를 저장할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def remove(self, name: str) -> None:
        if not self.exists(name):
            raise NotFoundError(
                "없는 데이터입니다.",
                "카테고리명을 다시 확인하세요.",
            )

        temp_path = ""
        try:
            with open(self.path, "r", encoding="utf-8") as src:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    delete=False,
                    dir=self.data_dir,
                ) as tmp:
                    temp_path = tmp.name
                    for line in src:
                        text = line.strip()
                        if not text:
                            continue
                        data = json.loads(text)
                        if not isinstance(data, dict):
                            raise StorageError(
                                "카테고리 저장 파일 형식이 올바르지 않습니다.",
                                "categories.jsonl 파일 내용을 확인하세요.",
                            )
                        raw = data.get("name", "")
                        current = raw if isinstance(raw, str) else str(raw)
                        if current == name:
                            continue
                        tmp.write(json.dumps({"name": current}, ensure_ascii=False) + "\n")
            os.replace(temp_path, self.path)
            temp_path = ""
        except NotFoundError:
            raise
        except json.JSONDecodeError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "카테고리 저장 파일 형식이 올바르지 않습니다.",
                "categories.jsonl 파일 내용을 확인하세요.",
            ) from exc
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "카테고리를 삭제할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def exists(self, name: str) -> bool:
        return name in self.list()


class BudgetStore:
    def __init__(self, data_dir: str) -> None:
        self.data_dir: str = data_dir
        self.path: str = os.path.join(data_dir, "budgets.jsonl")

    def ensure_files(self) -> None:
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            if not os.path.exists(self.path):
                with open(self.path, "w", encoding="utf-8"):
                    pass
        except OSError as exc:
            raise StorageError(
                "예산 저장 파일을 준비할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def set(self, month: str, amount: int) -> None:
        validated_month = validate_month(month)
        validated_amount = validate_amount(amount)
        budget = Budget(month=validated_month, amount=validated_amount)

        self.ensure_files()
        found = False
        temp_path = ""

        try:
            with open(self.path, "r", encoding="utf-8") as src:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    delete=False,
                    dir=self.data_dir,
                ) as tmp:
                    temp_path = tmp.name
                    for line in src:
                        text = line.strip()
                        if not text:
                            continue
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError as exc:
                            raise StorageError(
                                "예산 저장 파일 형식이 올바르지 않습니다.",
                                "budgets.jsonl 파일 내용을 확인하세요.",
                            ) from exc
                        if not isinstance(data, dict):
                            raise StorageError(
                                "예산 저장 파일 형식이 올바르지 않습니다.",
                                "budgets.jsonl 파일 내용을 확인하세요.",
                            )
                        try:
                            raw_month = data.get("month", "")
                            raw_amount = data.get("amount", 0)
                            current = Budget(
                                month=validate_month(str(raw_month)),
                                amount=validate_amount(raw_amount),
                            )
                        except ValidationError as exc:
                            raise StorageError(
                                "예산 저장 파일 형식이 올바르지 않습니다.",
                                "budgets.jsonl 파일 내용을 확인하세요.",
                            ) from exc
                        if current.month == budget.month:
                            found = True
                            current = budget
                        tmp.write(
                            json.dumps(
                                {"month": current.month, "amount": current.amount},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                    if not found:
                        tmp.write(
                            json.dumps(
                                {"month": budget.month, "amount": budget.amount},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
            os.replace(temp_path, self.path)
            temp_path = ""
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise StorageError(
                "예산을 저장할 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc

    def get(self, month: str) -> int | None:
        validated_month = validate_month(month)
        self.ensure_files()
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                for line in file:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError as exc:
                        raise StorageError(
                            "예산 저장 파일 형식이 올바르지 않습니다.",
                            "budgets.jsonl 파일 내용을 확인하세요.",
                        ) from exc
                    if not isinstance(data, dict):
                        raise StorageError(
                            "예산 저장 파일 형식이 올바르지 않습니다.",
                            "budgets.jsonl 파일 내용을 확인하세요.",
                        )
                    try:
                        raw_month = data.get("month", "")
                        if validate_month(str(raw_month)) == validated_month:
                            return validate_amount(data.get("amount"))
                    except ValidationError as exc:
                        raise StorageError(
                            "예산 저장 파일 형식이 올바르지 않습니다.",
                            "budgets.jsonl 파일 내용을 확인하세요.",
                        ) from exc
            return None
        except OSError as exc:
            raise StorageError(
                "예산 저장 파일을 읽을 수 없습니다.",
                "저장 폴더 권한과 경로를 확인하세요.",
            ) from exc