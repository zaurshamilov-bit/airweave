"""Shared exceptions module."""

from typing import Optional

from pydantic import ValidationError


class PermissionException(Exception):
    """Exception raised when a user does not have the necessary permissions to perform an action."""

    def __init__(
        self,
        message: Optional[str] = "User does not have the right to perform this action",
    ):
        """Create a new PermissionException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class NotFoundException(Exception):
    """Exception raised when an object is not found."""

    def __init__(self, message: Optional[str] = "Object not found"):
        """Create a new NotFoundException instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class ImmutableFieldError(Exception):
    """Exception raised for attempts to modify immutable fields in a database model."""

    def __init__(self, field_name: str, message: str = "Cannot modify immutable field"):
        """Create a new ImmutableFieldError instance.

        Args:
        ----
            field_name (str): The name of the immutable field.
            message (str, optional): The error message. Has default message.

        """
        self.field_name = field_name
        self.message = message
        super().__init__(f"{message}: {field_name}")


class TokenRefreshError(Exception):
    """Exception raised when a token refresh fails."""

    def __init__(self, message: Optional[str] = "Token refresh failed"):
        """Create a new TokenRefreshError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


class UsageLimitExceededException(Exception):
    """Exception raised when usage limits are exceeded."""

    def __init__(
        self,
        action_type: Optional[str] = None,
        limit: Optional[int] = None,
        current_usage: Optional[int] = None,
        message: Optional[str] = None,
    ):
        """Create a new UsageLimitExceededException instance.

        Args:
        ----
            action_type (str, optional): The type of action that exceeded the limit.
            limit (int, optional): The limit that was exceeded.
            current_usage (int, optional): The current usage count.
            message (str, optional): Custom error message. If not provided, generates one.

        """
        if message is None:
            if action_type:
                message = f"Usage limit exceeded for {action_type}"
                if limit is not None and current_usage is not None:
                    message += f": {current_usage}/{limit}"
            else:
                message = "Usage limit exceeded"

        self.action_type = action_type
        self.limit = limit
        self.current_usage = current_usage
        self.message = message
        super().__init__(self.message)


class PaymentRequiredException(Exception):
    """Exception raised when an action is blocked due to payment status."""

    def __init__(
        self,
        action_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """Create a new PaymentRequiredException instance.

        Args:
        ----
            action_type (str, optional): The type of action that was blocked.
            payment_status (str, optional): The current payment status.
            message (str, optional): Custom error message. If not provided, generates one.

        """
        if message is None:
            if action_type and payment_status:
                message = (
                    f"Action '{action_type}' is not allowed due to payment status: {payment_status}"
                )
            elif action_type:
                message = f"Action '{action_type}' requires an active subscription"
            else:
                message = "This action requires an active subscription"

        self.action_type = action_type
        self.payment_status = payment_status
        self.message = message
        super().__init__(self.message)


class ExternalServiceError(Exception):
    """Exception raised when an external service fails."""

    def __init__(self, service_name: str, message: Optional[str] = "External service failed"):
        """Create a new ExternalServiceError instance.

        Args:
        ----
            service_name (str): The name of the external service.
            message (str, optional): The error message. Has default message.

        """
        self.service_name = service_name
        self.message = message
        super().__init__(f"{service_name}: {message}")


class InvalidStateError(Exception):
    """Exception raised when an object is in an invalid state.

    Used when multiple services are involved and the state of one service is invalid,
    in relation to the other services.
    """

    def __init__(self, message: Optional[str] = "Object is in an invalid state"):
        """Create a new InvalidStateError instance.

        Args:
        ----
            message (str, optional): The error message. Has default message.

        """
        self.message = message
        super().__init__(self.message)


def unpack_validation_error(exc: ValidationError) -> dict:
    """Unpack a Pydantic validation error into a dictionary.

    Args:
    ----
        exc (ValidationError): The Pydantic validation error.

    Returns:
    -------
        dict: The dictionary representation of the validation error.

    """
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        error_messages.append({field: message})

    return {"errors": error_messages}
