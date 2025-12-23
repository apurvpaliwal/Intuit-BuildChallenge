class LibraryError(Exception):
    """Base exception for library system errors."""


class BookNotFoundError(LibraryError):
    """Requested ISBN does not exist in the library."""


class MemberNotFoundError(LibraryError):
    """Requested memberId does not exist in the library."""


class CheckoutRuleViolationError(LibraryError):
    """checkout/return violates business rules."""


class DuplicateBookError(LibraryError):
    """Trying to add a book that already exists."""


class DuplicateMemberError(LibraryError):
    """Trying to register a member that already exists."""
