import pytest
from datetime import date

from library_system import Library, Book, Member
from exceptions import (
    BookNotFoundError,
    MemberNotFoundError,
    CheckoutRuleViolationError,
    DuplicateBookError,
    DuplicateMemberError,
)


@pytest.fixture
def lib():
    """Fresh library with sample books + one member."""
    l = Library()
    l.addBook(Book("111", "Clean Code", "Robert C. Martin"))
    l.addBook(Book("222", "Design Patterns", "GoF"))
    l.addBook(Book("333", "Effective Java", "Joshua Bloch"))
    l.addBook(Book("444", "Refactoring", "Martin Fowler"))
    l.registerMember(Member("M1", "Apurv"))
    return l


def test_add_book_success(lib):
    lib.addBook(Book("555", "The Pragmatic Programmer", "Andrew Hunt"))
    assert "555" in lib.books
    assert lib.books["555"].isAvailable is True


def test_add_book_duplicate_raises(lib):
    with pytest.raises(DuplicateBookError):
        lib.addBook(Book("111", "Duplicate", "Someone"))


def test_register_member_success(lib):
    lib.registerMember(Member("M2", "Alex"))
    assert "M2" in lib.members


def test_register_member_duplicate_raises(lib):
    with pytest.raises(DuplicateMemberError):
        lib.registerMember(Member("M1", "Duplicate Name"))


def test_checkout_book_not_found(lib):
    with pytest.raises(BookNotFoundError):
        lib.checkoutBook("M1", "999", checkout_date=date(2025, 1, 1))


def test_checkout_member_not_found(lib):
    with pytest.raises(MemberNotFoundError):
        lib.checkoutBook("M999", "111", checkout_date=date(2025, 1, 1))


def test_checkout_marks_unavailable_and_updates_member(lib):
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)

    assert lib.books["111"].isAvailable is False
    assert "111" in lib.members["M1"].borrowedBooks

    hist = lib.getMemberBorrowingHistory("M1")
    assert len(hist) == 1
    assert hist[0]["isbn"] == "111"
    assert hist[0]["checkoutDate"] == d0
    assert hist[0]["dueDate"] == date(2025, 1, 15)  # 14 days from Jan 1
    assert hist[0]["returnDate"] is None


def test_due_date_exactly_14_days(lib):
    d0 = date(2025, 3, 10)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    hist = lib.getMemberBorrowingHistory("M1")
    assert hist[0]["dueDate"] == date(2025, 3, 24)


def test_cannot_checkout_unavailable_book(lib):
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    with pytest.raises(CheckoutRuleViolationError):
        lib.checkoutBook("M1", "111", checkout_date=d0)


def test_max_3_books_rule(lib):
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    lib.checkoutBook("M1", "222", checkout_date=d0)
    lib.checkoutBook("M1", "333", checkout_date=d0)

    with pytest.raises(CheckoutRuleViolationError):
        lib.checkoutBook("M1", "444", checkout_date=d0)


def test_return_book_not_borrowed_raises(lib):
    with pytest.raises(CheckoutRuleViolationError):
        lib.returnBook("M1", "111", return_date=date(2025, 1, 5))


def test_return_date_before_checkout_raises(lib):
    d0 = date(2025, 1, 10)
    lib.checkoutBook("M1", "111", checkout_date=d0)

    with pytest.raises(ValueError):
        lib.returnBook("M1", "111", return_date=date(2025, 1, 9))


def test_return_updates_availability_and_member_list(lib):
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)

    lib.returnBook("M1", "111", return_date=date(2025, 1, 5))
    assert lib.books["111"].isAvailable is True
    assert "111" not in lib.members["M1"].borrowedBooks

    hist = lib.getMemberBorrowingHistory("M1")
    assert hist[0]["returnDate"] == date(2025, 1, 5)


def test_fine_zero_if_returned_on_time(lib):
    d0 = date(2025, 1, 1)  # due Jan 15
    lib.checkoutBook("M1", "111", checkout_date=d0)
    lib.returnBook("M1", "111", return_date=date(2025, 1, 15))
    assert lib.members["M1"].fineBalance == 0.0


def test_fine_calculation_overdue_exact(lib):
    """
    Due: Jan 15
    Return: Jan 20 => 5 days overdue => 5 * 0.50 = 2.50
    """
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    lib.returnBook("M1", "111", return_date=date(2025, 1, 20))
    assert lib.members["M1"].fineBalance == 2.50


def test_calculateFine_for_open_borrow_as_of_date(lib):
    """
    If not returned, fine should be computed against on_date.
    Checkout: Jan 1, due Jan 15
    on_date: Jan 18 => 3 overdue days => 1.50
    """
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)

    fine = lib.calculateFine("M1", on_date=date(2025, 1, 18))
    assert fine == 1.50
    assert lib.members["M1"].fineBalance == 1.50


def test_fine_block_over_10_prevents_checkout(lib):
    """
    Make fine > $10 by returning very late.
    Due: Jan 15
    Return: Feb 20 => 36 overdue days => 18.00
    Then attempt checkout => should fail.
    """
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    lib.returnBook("M1", "111", return_date=date(2025, 2, 20))
    assert lib.members["M1"].fineBalance > 10.0

    with pytest.raises(CheckoutRuleViolationError):
        lib.checkoutBook("M1", "222", checkout_date=date(2025, 2, 21))


def test_getAvailableBooks_updates_correctly(lib):
    assert set(b.isbn for b in lib.getAvailableBooks()) == {"111", "222", "333", "444"}
    lib.checkoutBook("M1", "111", checkout_date=date(2025, 1, 1))
    assert set(b.isbn for b in lib.getAvailableBooks()) == {"222", "333", "444"}


def test_getMemberBorrowingHistory_member_not_found(lib):
    with pytest.raises(MemberNotFoundError):
        lib.getMemberBorrowingHistory("M999")


def test_history_contains_multiple_records(lib):
    d0 = date(2025, 1, 1)
    lib.checkoutBook("M1", "111", checkout_date=d0)
    lib.checkoutBook("M1", "222", checkout_date=d0)
    lib.returnBook("M1", "111", return_date=date(2025, 1, 10))

    hist = lib.getMemberBorrowingHistory("M1")
    assert len(hist) == 2
    assert {h["isbn"] for h in hist} == {"111", "222"}
    # One returned, one still open
    returned = [h for h in hist if h["isbn"] == "111"][0]
    open_rec = [h for h in hist if h["isbn"] == "222"][0]
    assert returned["returnDate"] == date(2025, 1, 10)
    assert open_rec["returnDate"] is None
