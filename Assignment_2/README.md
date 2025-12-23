# Order Processing & Invoice Summary (Python)

---

## 1. Overview

This project implements an **order processing application** that reads order data from a **pipe-delimited text file** and generates **invoice summaries grouped by customer**.

Each input record follows this format:

`OrderID|CustomerName|ProductName|Quantity|UnitPrice|OrderDate`

Example:

`ORD001|John Smith|Laptop|2|999.99|2024-03-15`

The application:
1. Parses the input file and logs malformed records to an **error file**
2. Calculates **line totals** (`quantity × unit_price`)
3. Applies a **10% discount** when a **line total > $500**
4. Produces a **customer summary report**:
   - customer name
   - number of orders
   - total items purchased
   - gross total
   - discount amount
   - net total
5. Writes the report to an **output file** with formatted columns and a **GRAND TOTAL** row

Edge cases handled:
- empty input files
- negative or zero quantities
- invalid dates
- invalid numeric values

---

## 2. Project Structure
├── exceptions.py
├── order_processing.py
├── sample_input_orders.txt
└── test_order_processing.py


---

## 3. Setup Instructions

### 3.1 Prerequisites
- Python **3.9+** recommended
- `pip` available

### 3.2 (Optional) Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3.3 Install dependencies

Only pytest is needed for unit tests:
```pip install pytest```

### 4. How to Run the Application
## 4.1 Command
```python3 order_processing.py --input sample_input_orders.txt --output report.txt --error error_records.txt```

## 4.2 Outputs Produced

- report.txt — formatted customer summary report (valid records only)
- error_records.txt — malformed record lines with line number and reason

### 5. Sample Input
- File: sample_input_orders.txt
- Example valid lines:
    ORD001|John Smith|Laptop|1|999.99|2024-03-15
    ORD001|John Smith|Mouse|2|25.50|2024-03-15
    ORD004|Carla Diaz|Standing Desk|1|650.00|2024-03-17
- Example malformed lines (should appear in error file):
    ORD014|Eva Chen|Mouse|0|25.50|2024-03-24

### 6. Sample Output

File: summary_report.txt

Customer Name              # Orders   Total Items   Gross Total   Discount     Net Total
----------------------------------------------------------------------------------------
Alice Johnson              3          3            499.98       0.00         499.98
Bob Lee                    3          5            975.98       80.00        895.98
Carla Diaz                 3          5            1394.99      65.00        1329.99
Eva Chen                   3          4            299.95       0.00         299.95
John Smith                 2          4            1601.99      155.00       1446.99
----------------------------------------------------------------------------------------
GRAND TOTAL                14         21           4772.89      300.00       4472.89

### 7. Error File Output

File: error_records.txt

Line 16: Quantity must be positive (got 0) | RAW=ORD014|Eva Chen|Mouse|0|25.50|2024-03-24
Line 19: Invalid OrderDate (expected YYYY-MM-DD): '03-24-2024' | RAW=ORD017|Carla Diaz|Mouse|1|25.50|03-24-2024
Line 20: Wrong field count (expected 6, got 4) | RAW=BAD|LINE|MISSING|FIELDS


### 8. Assumptions

## 1. Discount rule interpretation
A. The requirement states: “Apply a 10% discount for orders with line totals over $500.”
    - This solution interprets that as:
    - If a single line’s total (quantity × unit_price) is > $500, apply 10% discount to that line.
    - Discount is computed per line and aggregated into customer totals.

B. Number of orders per customer
    - Counted as the number of unique OrderID values for that customer.

C. Valid quantities and prices
    - Quantity must be positive integer
    - Unit price must be positive decimal
    - Invalid or non-positive values are treated as malformed records

D. Date format
    - Only ISO format is accepted: YYYY-MM-DD

E. Empty input file
    - Produces:
        1. Empty output report (header + grand total with zeros is not generated here; report is still written if called)
        2. Empty error file

F. Precision and rounding
    - Monetary values are stored using Decimal
    - Rounded to 2 decimal places using standard rounding (ROUND_HALF_UP)

### 9. Running Unit Tests (Pytest)
## 9.1 Install pytest
```pip install pytest```

## 9.2 Run tests
```pytest -vv```

Example output:
collected 12 items

test_order_processing.py::test_parse_order_line_success PASSED
test_order_processing.py::test_parse_order_line_malformed[ORD001|John|Laptop|2|999.99] PASSED
...
test_order_processing.py::test_format_report_has_grand_total_row PASSED

============================== 12 passed in X.XXs =============================



### 10. Notes

- This solution is a CLI-based file processing tool.
- The code is designed to be easy to extend for:
    - different discount rules
    - different grouping logic (e.g., by order instead of by customer)
    - CSV export formats
