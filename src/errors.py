# src/errors.py

from typing import Optional

class AppError(Exception):
    """
    Base exception for the Ignition Admin Panel.
    All other exceptions should inherit from this.
    """
    def __init__(self, message: str, *, underlying: Optional[Exception] = None):
        super().__init__(message)
        self.underlying = underlying

    def __str__(self):
        if self.underlying:
            return f"{self.args[0]} (caused by {self.underlying})"
        return self.args[0]


class FileSaveError(AppError):
    """
    Raised when saving or copying user-uploaded files fails.
    """


class ProjectValidationError(AppError):
    """
    Raised when the provided project directory is invalid or missing a manifest.
    """


class TagValidationError(AppError):
    """
    Raised when the provided tag file is missing or in an unsupported format.
    """


class ConfigBuildError(AppError):
    """
    Raised when composing the configuration from GUI inputs fails validation.
    """


class TemplateRenderError(AppError):
    """
    Raised when rendering a Jinja2 template (compose or .env) fails.
    """


class DockerManagerError(AppError):
    """
    Raised for errors in starting, stopping, or streaming logs from Docker Compose.
    """


class CleanupError(AppError):
    """
    Raised when generated files or directories cannot be cleaned up.
    """