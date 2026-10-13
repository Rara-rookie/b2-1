from typing import Callable, TypeVar

T = TypeVar("T")


class AppError(Exception):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.hint: str | None = hint

    # 사용자에게 보여줄 오류 목록. 한 건이면 자기 자신이고, 여러 건을 담는
    # ValidationErrors 는 담고 있는 오류를 모두 펼쳐서 돌려준다.
    def unpack(self) -> list["AppError"]:
        return [self]


class ValidationError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class ValidationErrors(ValidationError):
    """입력 항목 여러 개가 동시에 잘못된 경우를 한 예외로 전달한다.

    ValidationError 를 상속하므로, 검증 실패를 걸러내는 기존 처리(import 의 행 건너뛰기 등)는
    오류가 한 건이든 여러 건이든 그대로 동작한다.
    """

    def __init__(self, errors: list[AppError]) -> None:
        self.errors: list[AppError] = list(errors)
        super().__init__(
            f"입력값 {len(self.errors)}개가 올바르지 않습니다.",
            "아래 항목을 모두 수정한 후 다시 입력하세요.",
        )

    def unpack(self) -> list[AppError]:
        unpacked: list[AppError] = []
        for error in self.errors:
            unpacked.extend(error.unpack())
        return unpacked


class NotFoundError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class ConflictError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class StorageError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class ErrorCollector:
    """검증을 차례로 실행하되 첫 실패에서 멈추지 않고 모은다.

    add 처럼 한 번에 여러 항목을 입력받는 명령에서 첫 항목의 오류로 중단하면, 나머지 항목이
    올바른지 사용자가 알 수 없어 재입력을 여러 번 반복하게 된다. 그래서 항목별 검증을
    collect() 로 감싸 실행하고, 모든 항목을 본 뒤 raise_if_any() 에서 한 번만 예외를 던진다.
    """

    def __init__(self) -> None:
        self.errors: list[AppError] = []

    def collect(self, validator: Callable[..., T], *args: object) -> T | None:
        """validator 를 실행해 결과를 돌려준다. 실패하면 오류를 모아 두고 None 을 돌려준다."""
        try:
            return validator(*args)
        except AppError as exc:
            self.errors.append(exc)
            return None

    def raise_if_any(self) -> None:
        """모인 오류가 있으면 던진다. 한 건이면 원래 예외를 그대로 쓴다."""
        if len(self.errors) == 1:
            raise self.errors[0]
        if self.errors:
            raise ValidationErrors(self.errors)