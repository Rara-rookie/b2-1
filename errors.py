class AppError(Exception):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message: str = message
        self.hint: str | None = hint


class ValidationError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class NotFoundError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class ConflictError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)


class StorageError(AppError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message, hint)
