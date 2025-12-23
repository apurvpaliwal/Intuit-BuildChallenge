from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from exception import InputFileError, OutputFileError, RecordParseError

# -----------------------------
# Logging
# -----------------------------
logger = logging.getLogger("order_processing")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(h)

MONEY_Q = Decimal("0.01")
DISCOUNT_RATE = Decimal("0.10")
DISCOUNT_THRESHOLD = Decimal("500.00")  # apply discount if TOTAL > 500


def money(x: Decimal) -> Decimal:
    return x.quantize(MONEY_Q, rounding=ROUND_HALF_UP)



# Data Models
@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    customer_name: str
    product_name: str
    quantity: int
    unit_price: Decimal
    order_date: date

    @property
    def line_total(self) -> Decimal:
        return money(Decimal(self.quantity) * self.unit_price)

    @property
    def discount(self) -> Decimal:
        # Requirement (3): 10% discount for orders with line totals over $500
        # Interpreted as: if THIS line_total > 500, discount applies to THIS line.
        if self.line_total > DISCOUNT_THRESHOLD:
            return money(self.line_total * DISCOUNT_RATE)
        return Decimal("0.00")

    @property
    def net_total(self) -> Decimal:
        return money(self.line_total - self.discount)


@dataclass
class CustomerSummary:
    customer_name: str
    num_orders: int
    total_items: int
    gross_total: Decimal
    discount_total: Decimal
    net_total: Decimal



# Parsing / Validation
def parse_order_line(line: str) -> OrderRecord:
    """
    Expected format:
      OrderID|CustomerName|ProductName|Quantity|UnitPrice|OrderDate

    Example:
      ORD001|John Smith|Laptop|2|999.99|2024-03-15
    """
    parts = [p.strip() for p in line.strip().split("|")]
    if len(parts) != 6:
        raise RecordParseError(f"Wrong field count (expected 6, got {len(parts)})")

    order_id, customer, product, qty_s, price_s, date_s = parts

    if not order_id:
        raise RecordParseError("OrderID is empty")
    if not customer:
        raise RecordParseError("CustomerName is empty")
    if not product:
        raise RecordParseError("ProductName is empty")

    try:
        qty = int(qty_s)
    except Exception:
        raise RecordParseError(f"Invalid Quantity: {qty_s!r}")
    if qty <= 0:
        raise RecordParseError(f"Quantity must be positive (got {qty})")

    try:
        unit_price = Decimal(price_s)
    except (InvalidOperation, Exception):
        raise RecordParseError(f"Invalid UnitPrice: {price_s!r}")
    if unit_price <= 0:
        raise RecordParseError(f"UnitPrice must be positive (got {unit_price})")
    unit_price = money(unit_price)

    try:
        od = date.fromisoformat(date_s)
    except Exception:
        raise RecordParseError(f"Invalid OrderDate (expected YYYY-MM-DD): {date_s!r}")

    return OrderRecord(
        order_id=order_id,
        customer_name=customer,
        product_name=product,
        quantity=qty,
        unit_price=unit_price,
        order_date=od,
    )


def read_orders(input_path: str | Path, error_path: str | Path) -> List[OrderRecord]:
    """
    Requirement (1): Parse the input file and handle malformed records
    by logging them to an error file.

    - Blank lines are ignored.
    - Malformed lines are written to error file with reason + raw content.
    - Empty input file returns empty orders list and creates an empty error file.
    """
    input_path = Path(input_path)
    error_path = Path(error_path)

    logger.info("Reading input file | %s", input_path)

    try:
        text = input_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.exception("Cannot read input file | %s", e)
        raise InputFileError(f"Cannot read input file: {input_path}") from e

    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        # Edge case: empty file
        try:
            error_path.write_text("", encoding="utf-8")
        except Exception as e:
            raise OutputFileError(f"Cannot write error file: {error_path}") from e
        logger.error("Input file is empty | %s", input_path)
        return []

    valid: List[OrderRecord] = []
    errors: List[str] = []

    for idx, raw in enumerate(lines, start=1):
        try:
            rec = parse_order_line(raw)
            valid.append(rec)
        except RecordParseError as e:
            msg = f"Line {idx}: {e} | RAW={raw}"
            logger.error("Malformed record | %s", msg)
            errors.append(msg)

    try:
        error_path.write_text("\n".join(errors) + ("\n" if errors else ""), encoding="utf-8")
    except Exception as e:
        logger.error("Cannot write error file | %s", e)
        raise OutputFileError(f"Cannot write error file: {error_path}") from e

    logger.info("Parsed records | valid=%d malformed=%d", len(valid), len(errors))
    return valid



# Aggregation
def summarize_by_customer(records: List[OrderRecord]) -> List[CustomerSummary]:
    """
    Requirement (4): Grouped by customer showing:
      - customer name
      - number of orders (unique OrderID)
      - total items purchased (sum quantity)
      - gross total (sum line_total)
      - discount amount (sum discounts)
      - net total (gross - discount)
    """
    # customer -> set(order_ids), totals
    temp: Dict[str, Dict[str, object]] = {}

    for r in records:
        entry = temp.setdefault(
            r.customer_name,
            {
                "order_ids": set(),
                "total_items": 0,
                "gross": Decimal("0.00"),
                "discount": Decimal("0.00"),
            },
        )
        entry["order_ids"].add(r.order_id)
        entry["total_items"] += r.quantity
        entry["gross"] += r.line_total
        entry["discount"] += r.discount

    summaries: List[CustomerSummary] = []
    for customer, v in temp.items():
        gross = money(v["gross"])
        discount = money(v["discount"])
        net = money(gross - discount)

        summaries.append(
            CustomerSummary(
                customer_name=customer,
                num_orders=len(v["order_ids"]),
                total_items=int(v["total_items"]),
                gross_total=gross,
                discount_total=discount,
                net_total=net,
            )
        )

    summaries.sort(key=lambda s: s.customer_name.lower())
    return summaries


# Report Formatting / Output
def format_report(summaries: List[CustomerSummary]) -> str:
    """
    Requirement (5): Properly formatted columns + grand total row.
    """
    cols: List[Tuple[str, int]] = [
        ("Customer Name", 24),
        ("# Orders", 9),
        ("Total Items", 12),
        ("Gross Total", 12),
        ("Discount", 12),
        ("Net Total", 12),
    ]

    def line(values: List[Tuple[str, int]]) -> str:
        return "  ".join(str(v).ljust(w) for v, w in values).rstrip()

    total_width = sum(w for _, w in cols) + 2 * (len(cols) - 1)
    out: List[str] = []
    out.append(line(cols))
    out.append("-" * total_width)

    g_orders = 0
    g_items = 0
    g_gross = Decimal("0.00")
    g_discount = Decimal("0.00")
    g_net = Decimal("0.00")

    for s in summaries:
        out.append(
            line(
                [
                    (s.customer_name, 24),
                    (str(s.num_orders), 9),
                    (str(s.total_items), 12),
                    (f"{s.gross_total:.2f}", 12),
                    (f"{s.discount_total:.2f}", 12),
                    (f"{s.net_total:.2f}", 12),
                ]
            )
        )
        g_orders += s.num_orders
        g_items += s.total_items
        g_gross += s.gross_total
        g_discount += s.discount_total
        g_net += s.net_total

    out.append("-" * total_width)
    out.append(
        line(
            [
                ("GRAND TOTAL", 24),
                (str(g_orders), 9),
                (str(g_items), 12),
                (f"{money(g_gross):.2f}", 12),
                (f"{money(g_discount):.2f}", 12),
                (f"{money(g_net):.2f}", 12),
            ]
        )
    )
    return "\n".join(out) + "\n"


def write_report(output_path: str | Path, report_text: str) -> None:
    output_path = Path(output_path)
    logger.info("Writing report | %s", output_path)
    try:
        output_path.write_text(report_text, encoding="utf-8")
    except Exception as e:
        logger.exception("Cannot write output file | %s", e)
        raise OutputFileError(f"Cannot write output file: {output_path}") from e


# CLI / Main
def main() -> None:
    parser = argparse.ArgumentParser(description="Process order data and generate invoice summaries.")
    parser.add_argument("--input", required=True, help="Path to input orders text file")
    parser.add_argument("--output", required=True, help="Path to output summary report file")
    parser.add_argument("--error", required=True, help="Path to error file for malformed records")
    args = parser.parse_args()

    records = read_orders(args.input, args.error)
    summaries = summarize_by_customer(records)
    report = format_report(summaries)
    write_report(args.output, report)

    logger.info("Complete | valid_records=%d customers=%d", len(records), len(summaries))


if __name__ == "__main__":
    main()
