"""Validation utilities for runtime checks that work with Python's -O flag."""

from typing import Any, Optional, Type, TypeVar

T = TypeVar('T')


def require_not_none(value: Optional[T], name: str) -> T:
    """
    Validate that a value is not None.

    Args:
        value: The value to check
        name: Descriptive name for error messages

    Returns:
        The value if not None

    Raises:
        RuntimeError: If value is None
    """
    if value is None:
        raise RuntimeError(f"{name} must not be None")
    return value


def require_type(value: Any, expected_type: Type[T], name: str) -> T:
    """
    Validate that a value is of the expected type.

    Args:
        value: The value to check
        expected_type: The expected type
        name: Descriptive name for error messages

    Returns:
        The value if type matches

    Raises:
        TypeError: If value is not of expected type
    """
    if not isinstance(value, expected_type):
        raise TypeError(
            f"{name} must be {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )
    return value


def require_truthy(value: Any, message: str) -> None:
    """
    Validate that a value is truthy.

    Args:
        value: The value to check
        message: Error message if check fails

    Raises:
        RuntimeError: If value is falsy
    """
    if not value:
        raise RuntimeError(message)


def require_condition(condition: bool, message: str) -> None:
    """
    Validate that a condition is true.

    Args:
        condition: The condition to check
        message: Error message if check fails

    Raises:
        RuntimeError: If condition is False
    """
    if not condition:
        raise RuntimeError(message)
