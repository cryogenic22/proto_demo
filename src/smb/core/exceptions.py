"""SMB exception hierarchy."""


class SMBError(Exception):
    """Base exception for all SMB errors."""


class SchemaError(SMBError):
    """Domain schema is invalid or missing."""


class AdapterError(SMBError):
    """Failed to convert extraction output to SMB input."""


class BuildError(SMBError):
    """Failed to build structured model."""


class InferenceError(SMBError):
    """Inference rule failed."""


class ValidationError(SMBError):
    """Model validation failed."""


class StorageError(SMBError):
    """Storage operation failed."""
