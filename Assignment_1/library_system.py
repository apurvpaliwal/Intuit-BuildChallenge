from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from exceptions import (
    LibraryError,
    BookNotFoundError,
    MemberNotFoundError,
    CheckoutRuleViolationError,
    DuplicateBookError,
    DuplicateMemberError,
)


# Logging configuration
logger = logging.getLogger("library")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# Domain Models
@dataclass
class Book:
    """
    Represents a book in the library.

    Attributes:
        isbn (str): Unique identifier for the book.
        title (str): Book title.
        author (str): Author name.
        isAvailable (bool): Whether the book is currently available for checkout.
    """
    isbn: str
    title: str
    author: str
    isAvailable: bool = True


@dataclass
class BorrowRecord:
    """
    Internal helper record that tracks a single borrow lifecycle.

    This record is used for:
    - due date calculation
    - overdue fine calculation
    - borrowing history reporting

    Attributes:
        isbn (str): ISBN of the borrowed book.
        checkoutDate (date): Date when the book was checked out.
        dueDate (date): Due date (checkout + 14 days).
        returnDate (Optional[date]): Date when the book was returned, if any.
    """
    isbn: str
    checkoutDate: date
    dueDate: date
    returnDate: Optional[date] = None

    def is_open(self) -> bool:
        """
        Returns True if the book has not yet been returned.
        """
        return self.returnDate is None


@dataclass
class Member:
    """
    Represents a library member.

    Attributes:
        memberId (str): Unique member identifier.
        name (str): Member name.
        borrowedBooks (List[str]): List of currently borrowed book ISBNs.
        fineBalance (float): Accumulated unpaid fines.
        _history (List[BorrowRecord]): Internal borrowing history.
    """
    memberId: str
    name: str
    borrowedBooks: List[str] = field(default_factory=list)
    fineBalance: float = 0.0
    _history: List[BorrowRecord] = field(default_factory=list)


# Library Core
class Library:
    """
    Core library system that manages books and members and enforces rules:

    Rules enforced:
        (1) Members can borrow at most 3 books at a time
        (2) Books are due 14 days from checkout
        (3) Overdue fine is $0.50 per day
        (4) Members with fines over $10 cannot checkout new books
    """

    MAX_BORROWED = 3
    DUE_DAYS = 14
    FINE_PER_DAY = 0.50
    FINE_BLOCK_THRESHOLD = 10.00

    def __init__(self) -> None:
        """
        Initializes an empty library with no books and no members.
        """
        self.books: Dict[str, Book] = {}
        self.members: Dict[str, Member] = {}

    
    # Public API
    
    def addBook(self, book: Book) -> None:
        """
        Adds a new book to the library.

        Raises:
            DuplicateBookError: If a book with the same ISBN already exists.
            ValueError: If ISBN is empty.
        """
        logger.info("addBook called | isbn=%s title=%s", book.isbn, book.title)

        if not book.isbn:
            raise ValueError("isbn cannot be empty")
        if book.isbn in self.books:
            raise DuplicateBookError(f"Book already exists: isbn={book.isbn}")

        self.books[book.isbn] = book
        logger.info("Book added successfully | isbn=%s", book.isbn)

    def registerMember(self, member: Member) -> None:
        """
        Registers a new member in the library.

        Raises:
            DuplicateMemberError: If memberId already exists.
            ValueError: If memberId is empty.
        """
        logger.info("registerMember called | memberId=%s", member.memberId)

        if not member.memberId:
            raise ValueError("memberId cannot be empty")
        if member.memberId in self.members:
            raise DuplicateMemberError(f"Member already exists: memberId={member.memberId}")

        self.members[member.memberId] = member
        logger.info("Member registered successfully | memberId=%s", member.memberId)

    def checkoutBook(
        self,
        memberId: str,
        isbn: str,
        checkout_date: Optional[date] = None
    ) -> None:
        """
        Checks out a book to a member.

        Enforces:
            - max 3 borrowed books
            - unpaid fine threshold
            - book availability

        Raises:
            MemberNotFoundError
            BookNotFoundError
            CheckoutRuleViolationError
        """
        logger.info("checkoutBook called | memberId=%s isbn=%s", memberId, isbn)

        member = self._get_member(memberId)
        book = self._get_book(isbn)

        if checkout_date is None:
            checkout_date = date.today()
        self._require_date(checkout_date, "checkout_date")

        # Update fine before enforcing fine rule
        self.calculateFine(memberId, on_date=checkout_date)

        if member.fineBalance > self.FINE_BLOCK_THRESHOLD:
            raise CheckoutRuleViolationError(
                f"Member {memberId} has unpaid fines ${member.fineBalance:.2f} (> $10)."
            )

        if len(member.borrowedBooks) >= self.MAX_BORROWED:
            raise CheckoutRuleViolationError(
                f"Member {memberId} already has {len(member.borrowedBooks)} books."
            )

        if not book.isAvailable:
            raise CheckoutRuleViolationError(f"Book {isbn} is not available.")

        due_date = checkout_date + timedelta(days=self.DUE_DAYS)

        book.isAvailable = False
        member.borrowedBooks.append(isbn)
        member._history.append(
            BorrowRecord(isbn=isbn, checkoutDate=checkout_date, dueDate=due_date)
        )

        logger.info("Checkout successful | memberId=%s isbn=%s", memberId, isbn)

    def returnBook(
        self,
        memberId: str,
        isbn: str,
        return_date: Optional[date] = None
    ) -> None:
        """
        Returns a previously borrowed book.

        Updates:
            - book availability
            - borrowing history
            - member fine balance

        Raises:
            CheckoutRuleViolationError
            MemberNotFoundError
            BookNotFoundError
        """
        logger.info("returnBook called | memberId=%s isbn=%s", memberId, isbn)

        member = self._get_member(memberId)
        book = self._get_book(isbn)

        if return_date is None:
            return_date = date.today()
        self._require_date(return_date, "return_date")

        if isbn not in member.borrowedBooks:
            raise CheckoutRuleViolationError(
                f"Member {memberId} does not have book {isbn} checked out."
            )

        rec = self._find_open_record(member, isbn)
        if return_date < rec.checkoutDate:
            raise ValueError("return_date cannot be before checkout_date")

        rec.returnDate = return_date
        book.isAvailable = True
        member.borrowedBooks.remove(isbn)

        self.calculateFine(memberId, on_date=return_date)
        logger.info("Return successful | memberId=%s isbn=%s", memberId, isbn)

    def calculateFine(self, memberId: str, on_date: Optional[date] = None) -> float:
        """
        Calculates and updates the total fine for a member.

        Fine rule:
            $0.50 per overdue day for each borrow record.

        Returns:
            float: Updated fine balance.
        """
        logger.info("calculateFine called | memberId=%s", memberId)

        member = self._get_member(memberId)

        if on_date is None:
            on_date = date.today()
        self._require_date(on_date, "on_date")

        total = 0.0
        for rec in member._history:
            effective_date = rec.returnDate or on_date
            if effective_date > rec.dueDate:
                overdue_days = (effective_date - rec.dueDate).days
                total += overdue_days * self.FINE_PER_DAY

        member.fineBalance = round(total, 2)
        return member.fineBalance

    def getAvailableBooks(self) -> List[Book]:
        """
        Returns all books currently available for checkout.
        """
        return [b for b in self.books.values() if b.isAvailable]

    def getMemberBorrowingHistory(self, memberId: str) -> List[dict]:
        """
        Returns the borrowing history for a member.

        Each record includes:
            - isbn
            - checkoutDate
            - dueDate
            - returnDate
        """
        member = self._get_member(memberId)
        return [
            {
                "isbn": rec.isbn,
                "checkoutDate": rec.checkoutDate,
                "dueDate": rec.dueDate,
                "returnDate": rec.returnDate,
            }
            for rec in member._history
        ]

    # Internal Helpers
    def _get_book(self, isbn: str) -> Book:
        """
        Retrieves a book by ISBN or raises BookNotFoundError.
        """
        if isbn not in self.books:
            raise BookNotFoundError(f"Book not found: isbn={isbn}")
        return self.books[isbn]

    def _get_member(self, memberId: str) -> Member:
        """
        Retrieves a member by ID or raises MemberNotFoundError.
        """
        if memberId not in self.members:
            raise MemberNotFoundError(f"Member not found: memberId={memberId}")
        return self.members[memberId]

    @staticmethod
    def _require_date(d: date, name: str) -> None:
        """
        Validates that the provided value is a datetime.date.
        """
        if not isinstance(d, date):
            raise ValueError(f"{name} must be a datetime.date")

    @staticmethod
    def _find_open_record(member: Member, isbn: str) -> BorrowRecord:
        """
        Finds the active (not returned) borrow record for a given ISBN.
        """
        for rec in reversed(member._history):
            if rec.isbn == isbn and rec.is_open():
                return rec
        raise CheckoutRuleViolationError(
            f"No active borrow record for memberId={member.memberId}, isbn={isbn}"
        )



# Main Program
def main() -> None:
    """
    Main driver program that demonstrates all library system operations.

    Demonstrated scenarios:
        - adding books
        - registering members
        - viewing available books
        - successful checkouts
        - checkout rule violations
            * max 3 books
            * book unavailable
            * unpaid fines > $10
        - book not found
        - member not found
        - returning books
        - overdue fine calculation
        - viewing borrowing history
    """
    from datetime import date

    print("\n=== Library Book Checkout System Demo ===\n")

    library = Library()

    
    # 1. Add Books
    
    print("Adding books...")
    library.addBook(Book("111", "Clean Code", "Robert C. Martin"))
    library.addBook(Book("222", "Design Patterns", "GoF"))
    library.addBook(Book("333", "Effective Java", "Joshua Bloch"))
    library.addBook(Book("444", "Refactoring", "Martin Fowler"))

    
    # 2. Register Members
    
    print("Registering members...")
    library.registerMember(Member("M1", "Apurv"))
    library.registerMember(Member("M2", "Alex"))

    
    # 3. Show Available Books
    
    print("\nAvailable books:")
    for b in library.getAvailableBooks():
        print(f"  {b.isbn} | {b.title}")

    checkout_day = date(2025, 1, 1)

    
    # 4. Successful Checkouts (Up to 3)
    
    print("\nChecking out 3 books for M1...")
    library.checkoutBook("M1", "111", checkout_date=checkout_day)
    library.checkoutBook("M1", "222", checkout_date=checkout_day)
    library.checkoutBook("M1", "333", checkout_date=checkout_day)

    
    # 5. Checkout Rule Violation: Max 3 Books
    
    print("\nAttempting 4th checkout (should fail)...")
    try:
        library.checkoutBook("M1", "444", checkout_date=checkout_day)
    except CheckoutRuleViolationError as e:
        print("Expected violation:", e)

    
    # 6. Checkout Rule Violation: Book Not Available
    
    print("\nAttempting to checkout unavailable book (M2 -> 111)...")
    try:
        library.checkoutBook("M2", "111", checkout_date=checkout_day)
    except CheckoutRuleViolationError as e:
        print("Expected violation:", e)

    
    # 7. Book Not Found
    
    print("\nAttempting to checkout non-existent book...")
    try:
        library.checkoutBook("M1", "999", checkout_date=checkout_day)
    except BookNotFoundError as e:
        print("Expected error:", e)

    
    # 8. Member Not Found
    
    print("\nAttempting checkout with invalid member...")
    try:
        library.checkoutBook("M999", "111", checkout_date=checkout_day)
    except MemberNotFoundError as e:
        print("Expected error:", e)

    
    # 9. Return Book Late (Incurs Fine)
    
    print("\nReturning book 111 late (overdue)...")
    library.returnBook("M1", "111", return_date=date(2025, 1, 25))
    print("Fine balance:", library.members["M1"].fineBalance)

    
    # 10. Create Fine > $10 and Block Checkout
    
    print("\nReturning book 222 very late to exceed $10 fine...")
    library.returnBook("M1", "222", return_date=date(2025, 2, 20))
    print("Fine balance:", library.members["M1"].fineBalance)

    print("\nAttempting checkout with fine > $10...")
    try:
        library.checkoutBook("M1", "444", checkout_date=date(2025, 2, 21))
    except CheckoutRuleViolationError as e:
        print("Expected violation:", e)

    
    # 11. Available Books After Returns
    
    print("\nAvailable books after returns:")
    for b in library.getAvailableBooks():
        print(f"  {b.isbn} | {b.title}")

    
    # 12. Borrowing History
    
    print("\nBorrowing history for M1:")
    history = library.getMemberBorrowingHistory("M1")
    for h in history:
        print(h)

    print("\n=== Demo Completed ===\n")


if __name__ == "__main__":
    try:
        main()
    except LibraryError as e:
        logger.error("LibraryError bubbled to top-level | %s", e)
        raise
    except Exception as e:
        logger.exception("Unhandled fatal error | %s", e)
        raise
