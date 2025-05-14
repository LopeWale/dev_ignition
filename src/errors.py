# src/errors.py

class AppError(Exception):
    """Base exception class for the admin panel."""

class ConfigBuildError(AppError):
    """Raised when building the ComposeConfig fails due to invalid input."""

class DockerManagerError(AppError):
    """Raised when Docker up/down or log streaming fails."""

# You can add more as you go (e.g. FileSaveError, TemplateRenderError, etc.)
