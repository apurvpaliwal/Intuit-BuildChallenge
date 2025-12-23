# Library Book Checkout System (Python)

---

## 1. Project Overview

This project implements a **Library Book Checkout System** in Python using an object-oriented design.  
The system manages books, members, checkouts, returns, fines, and borrowing history while enforcing the following business rules:

1. A member can borrow **at most 3 books** at a time  
2. A book is due **14 days** from the checkout date  
3. Overdue books incur a **$0.50 fine per day**  
4. Members with **unpaid fines over $10** cannot borrow new books  

The project includes:
- Clean separation of concerns
- Custom exception handling
- Logging for all major operations
- A demonstration `main()` program
- Comprehensive **pytest** unit tests

---

## 2. Project Structure

```text
├── exceptions.py
├── library_system.py
└── test_library_system.py
```

---

## 3. File Responsibilities

### 3.1 `exceptions.py`

Defines all custom exceptions used across the system:

- `LibraryError` – Base exception
- `BookNotFoundError` – Book ISBN not found
- `MemberNotFoundError` – Member ID not found
- `CheckoutRuleViolationError` – Checkout/return rule violation
- `DuplicateBookError` – Duplicate ISBN during add
- `DuplicateMemberError` – Duplicate member ID during registration

This keeps error handling explicit and readable.

---

### 3.2 `library_system.py`

Contains the full implementation of the library system, including domain models, business logic, logging, and a demo program.

---

## 4. Domain Models

### 4.1 `Book`
Represents a library book.

**Fields**
- `isbn`
- `title`
- `author`
- `isAvailable`

---

### 4.2 `Member`
Represents a library member.

**Fields**
- `memberId`
- `name`
- `borrowedBooks` – list of active ISBNs
- `fineBalance`
- `_history` – internal borrowing records

---

### 4.3 `BorrowRecord` (Internal Helper)
Tracks borrowing activity.

**Fields**
- `isbn`
- `checkoutDate`
- `dueDate`
- `returnDate`

Used for:
- Fine calculation
- Borrowing history
- Open/closed borrow tracking

---

### 5. The `Library` Class

The `Library` class is the core of the system.

## Internal Data Structures
- `books`: `Dict[str, Book]`
- `members`: `Dict[str, Member]`

---

### 6. Business Rule Enforcement

### Rule 1: Maximum 3 Books
Enforced in `checkoutBook()`:
- Raises `CheckoutRuleViolationError` if the member already has 3 books.

---

### Rule 2: Due Date = 14 Days
Applied during checkout:
```python due_date = checkout_date + timedelta(days=14) ```


### Rule 3: Fine = $0.50 per Day

Computed in calculateFine():
- Uses return date if returned
- Uses on_date if still borrowed
- Overdue days × $0.50

### Rule 4: Fine > $10 Blocks Checkout

Checked before checkout:
- calculateFine() is called first
- Checkout blocked if fineBalance > 10.00

### Rule 5. Library Methods (Flow of Execution)
## 5.1 addBook(book)
- Validate ISBN
- Check for duplicates
- Add to books

## 5.2 registerMember(member)
- Validate member ID
- Check for duplicates
- Add to members

## 5.3 checkoutBook(memberId, isbn)
- Validate member
- Validate book
- Update fine
- Enforce fine rule
- Enforce max-3 rule
- Verify availability
- Compute due date
- Update book and member state

## 5.4 returnBook(memberId, isbn)
- Validate member
- Validate book
- Verify member borrowed the book
- Update borrow record
- Restore availability
- Recalculate fine

## 5.5 calculateFine(memberId)

- Iterate over borrowing history
- Compute overdue days
- Update fineBalance

## 5.6 getAvailableBooks()

Returns all books where isAvailable == True.

## 5.7 getMemberBorrowingHistory(memberId)

Returns structured borrowing history:
- ISBN
- checkout date
- due date
- return date

### 7. Logging

- Uses Python’s logging module
- Logs:
   -  Method entry
   -  Successful operations
   -  Expected failures
   -  Unexpected exceptions with stack traces
   -  This improves debuggability and traceability.

### 8. Main Program (main())

The demo program performs the following:
1. Adds books
2. Registers members
3. Displays available books
4. Successfully checks out books
5. Demonstrates checkout rule violations:
    - Max 3 books
    - Book unavailable
    - Fine > $10
6. Demonstrates lookup errors:
    - Book not found
    - Member not found
7. Returns books late to incur fines
8. Displays final availability and borrowing history

Run the Demo
```python3 library_system.py```

### 9. Testing with Pytest
Test File
```test_library_system.py```

### 10. Test Coverage Summary
Book & Member Management

- Add book success
- Duplicate book error
- Register member success
- Duplicate member error

Lookup Errors

- Book not found
- Member not found

Checkout Rules

- Book availability
- Max 3 books
- Fine > $10 blocks checkout
- Due date accuracy

Return Rules:

- Return unborrowed book
- Return before checkout date
- Availability restoration

Fine Calculation

- On-time return
- Overdue return
- Open borrow fine calculation

History & Availability

- Correct available books
- Multiple borrowing records
- Open vs returned records

### 11. Running Tests (Option A)

Install pytest if needed:

pip install pytest


Run with verbose output:

pytest -vv


Example output:

test_library_system.py::test_add_book_success PASSED
test_library_system.py::test_add_book_duplicate_raises PASSED
...
test_library_system.py::test_history_contains_multiple_records PASSED

============================== 20 passed in X.XXs =============================

12. Requirements

Python 3.9+

pytest

13. Final Notes

The solution is framework-agnostic. Business rules are enforced centrally in the Library class.
Custom exceptions and logging provide clarity and robustness. The codebase is fully test-covered and easy to extend.
