import structlog

logger = structlog.get_logger(__name__)


class BaseAppError(Exception):
    """Базовий клас для всіх кастомних винятків додатку."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SerperAPIError(BaseAppError):
    def __init__(self, url: str, status_code: int | None, message: str):
        super().__init__(f"Serper API Error [{status_code}]: {message}")
        self.url = url
        self.status_code = status_code
        logger.error("serper_api_error", url=url, status_code=status_code, error_message=message)


class ParserError(BaseAppError):
    def __init__(self, url: str | None, message: str, raw_data: dict[str, object] | None = None):
        super().__init__(f"Parser Error: {message}")
        self.url = url
        self.raw_data = raw_data
        logger.error("parser_error", url=url, error_message=message, raw_data=raw_data)


class DatabaseError(BaseAppError):
    def __init__(self, operation: str, details: str):
        super().__init__(f"Database Error during {operation}: {details}")
        self.operation = operation
        self.details = details
        logger.error("database_error", operation=operation, details=details)
