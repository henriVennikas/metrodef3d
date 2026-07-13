class Metrodef3dError(Exception):
    """Base exception for user-facing metrodef3d failures."""


class RecipeError(Metrodef3dError):
    """Raised when a recipe cannot be loaded or validated."""


class RenderError(Metrodef3dError):
    """Raised when a configured render backend cannot produce output."""
