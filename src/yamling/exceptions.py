from __future__ import annotations


class DumpingError(Exception):
    """Common exception for all dumping errors in yamling."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class ParsingError(Exception):
    """Common exception for all parsing errors in yamling."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error
