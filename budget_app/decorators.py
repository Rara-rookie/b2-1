from __future__ import annotations

import sys
import time
from functools import wraps
from typing import Callable, TypeVar, cast

from .errors import AppError
from .formatter import format_error

F = TypeVar("F", bound=Callable[..., object])


def log_call(func: F) -> F:
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        print(f"[LOG] {func.__name__} called", file=sys.stderr)
        return func(*args, **kwargs)

    return cast(F, wrapper)


def timed(func: F) -> F:
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        start: float = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed: float = time.perf_counter() - start
            print(f"[TIME] {func.__name__}: {elapsed:.6f}s", file=sys.stderr)

    return cast(F, wrapper)


def handle_errors(func: Callable[..., int]) -> Callable[..., int]:
    @wraps(func)
    def wrapper(*args: object, **kwargs: object) -> int:
        try:
            return func(*args, **kwargs)
        except AppError as exc:
            print(format_error(exc))
            return 1
        except Exception:
            print("[오류] 알 수 없는 오류가 발생했습니다.")
            print("[힌트] 입력값과 저장 파일 상태를 확인한 후 다시 시도하세요.")
            return 1

    return wrapper