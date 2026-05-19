class OnePageException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", error_code: str | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code


class NotFoundException(OnePageException):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)


class ValidationException(OnePageException):
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message)


class UnauthorizedException(OnePageException):
    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message)


class RateLimitException(OnePageException):
    status_code = 429
    error_code = "RATE_LIMITED"

    def __init__(self, message: str = "Too many requests"):
        super().__init__(message)


class AITaskException(OnePageException):
    status_code = 500
    error_code = "AI_TASK_ERROR"

    def __init__(self, message: str = "AI task failed"):
        super().__init__(message)


class ModelAPIError(OnePageException):
    status_code = 502
    error_code = "MODEL_API_ERROR"

    def __init__(self, message: str = "Model API error"):
        super().__init__(message)


class ModelTimeoutError(OnePageException):
    status_code = 504
    error_code = "MODEL_TIMEOUT"

    def __init__(self, message: str = "Model request timeout"):
        super().__init__(message)


class StorageException(OnePageException):
    status_code = 500
    error_code = "STORAGE_ERROR"

    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message)
