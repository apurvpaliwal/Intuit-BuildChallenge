class OrderProcessingError(Exception):
    """Base exception for order processing."""


class InputFileError(OrderProcessingError):
    """Input file cannot be read or is invalid."""


class RecordParseError(OrderProcessingError):
    """Record line is malformed or fails validation."""


class OutputFileError(OrderProcessingError):
    """Output/Error files cannot be written."""
