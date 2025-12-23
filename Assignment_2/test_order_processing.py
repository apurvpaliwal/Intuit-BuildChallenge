import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path

from exception import InputFileError, RecordParseError
from order_processing import (
    parse_order_line,
    read_orders,
    summarize_by_customer,
    format_report,
)


# -----------------------------
# Parsing tests
# -----------------------------
def test_parse_order_line_success():
    line = "ORD001|John Smith|Laptop|2|999.99|2024-03-15"
    r = parse_order_line(line)
    assert r.order_id == "ORD001"
    assert r.customer_name == "John Smith"
    assert r.product_name == "Laptop"
    assert r.quantity == 2
    assert r.unit_price == Decimal("999.99")
    assert r.order_date == date(2024, 3, 15)
    assert r.line_total == Decimal("1999.98")
    assert r.discount == Decimal("199.998").quantize(Decimal("0.01"))  # 10% of 1999.98
    assert r.net_total == Decimal("1799.98")


@pytest.mark.parametrize(
    "bad_line",
    [
        "ORD001|John|Laptop|2|999.99",               # missing field
        "ORD001|John|Laptop|two|999.99|2024-03-15",  # bad qty
        "ORD001|John|Laptop|2|abc|2024-03-15",       # bad price
        "ORD001|John|Laptop|0|999.99|2024-03-15",    # zero qty
        "ORD001|John|Laptop|-2|999.99|2024-03-15",   # negative qty
        "ORD001|John|Laptop|2|999.99|03-15-2024",    # bad date
    ],
)
def test_parse_order_line_malformed(bad_line):
    with pytest.raises(RecordParseError):
        parse_order_line(bad_line)


# -----------------------------
# File I/O tests
# -----------------------------
def test_read_orders_writes_malformed_to_error(tmp_path: Path):
    inp = tmp_path / "orders.txt"
    err = tmp_path / "errors.txt"

    inp.write_text(
        "\n".join(
            [
                "ORD001|Alice|Pen|10|1.50|2024-01-01",
                "BAD|LINE|MISSING|FIELDS",
                "ORD002|Alice|Notebook|-1|5.00|2024-01-02",
                "ORD003|Bob|Mouse|1|25.00|2024-01-03",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    orders = read_orders(inp, err)
    assert len(orders) == 2  # ORD001 and ORD003 valid
    err_text = err.read_text(encoding="utf-8")
    assert "Line 2" in err_text
    assert "Line 3" in err_text


def test_read_orders_empty_file(tmp_path: Path):
    inp = tmp_path / "orders.txt"
    err = tmp_path / "errors.txt"
    inp.write_text("", encoding="utf-8")

    orders = read_orders(inp, err)
    assert orders == []
    assert err.read_text(encoding="utf-8") == ""


def test_read_orders_missing_input_raises(tmp_path: Path):
    inp = tmp_path / "missing.txt"
    err = tmp_path / "errors.txt"
    with pytest.raises(InputFileError):
        read_orders(inp, err)


# -----------------------------
# Aggregation + discount tests
# -----------------------------
def test_discount_applies_only_when_line_total_over_500():
    # line_total 600 => discount 60
    r1 = parse_order_line("ORD100|Alice|Laptop|1|600.00|2024-01-01")
    assert r1.line_total == Decimal("600.00")
    assert r1.discount == Decimal("60.00")
    assert r1.net_total == Decimal("540.00")

    # line_total exactly 500 => no discount
    r2 = parse_order_line("ORD101|Alice|Monitor|1|500.00|2024-01-01")
    assert r2.line_total == Decimal("500.00")
    assert r2.discount == Decimal("0.00")
    assert r2.net_total == Decimal("500.00")


def test_summarize_by_customer_counts_unique_orders_and_totals():
    records = [
        parse_order_line("ORD001|Alice|Pen|10|1.00|2024-01-01"),          # line_total 10 no discount
        parse_order_line("ORD001|Alice|Notebook|2|5.00|2024-01-01"),      # line_total 10 no discount
        parse_order_line("ORD002|Alice|Laptop|1|600.00|2024-01-02"),      # line_total 600 discount 60
        parse_order_line("ORD010|Bob|Mouse|1|25.00|2024-01-03"),          # Bob
    ]
    summaries = summarize_by_customer(records)

    alice = next(s for s in summaries if s.customer_name == "Alice")
    bob = next(s for s in summaries if s.customer_name == "Bob")

    assert alice.num_orders == 2  # ORD001, ORD002
    assert alice.total_items == 13  # 10 + 2 + 1
    assert alice.gross_total == Decimal("620.00")
    assert alice.discount_total == Decimal("60.00")
    assert alice.net_total == Decimal("560.00")

    assert bob.num_orders == 1
    assert bob.total_items == 1
    assert bob.gross_total == Decimal("25.00")
    assert bob.discount_total == Decimal("0.00")
    assert bob.net_total == Decimal("25.00")


# -----------------------------
# Report formatting tests
# -----------------------------
def test_format_report_has_grand_total_row():
    records = [
        parse_order_line("ORD001|Alice|Laptop|1|600.00|2024-01-01"),  # discount 60
        parse_order_line("ORD002|Bob|Mouse|1|25.00|2024-01-02"),
    ]
    summaries = summarize_by_customer(records)
    report = format_report(summaries)

    assert "GRAND TOTAL" in report
    # gross = 625.00, discount = 60.00, net = 565.00
    assert "625.00" in report
    assert "60.00" in report
    assert "565.00" in report
