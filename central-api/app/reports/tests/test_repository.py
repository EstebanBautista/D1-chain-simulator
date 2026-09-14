"""Unit tests for the dashboard's aggregations.

The dashboard shows exactly what these queries return, so the figures are
asserted against known data rather than assumed.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.base import Base
from app.ingestion.models import Invoice, InvoiceItem
from app.reports import repository
from app.stores.models import Store

LIMIT = 10


@pytest.fixture
def session():
    """An isolated database, created and discarded per test."""
    engine = create_engine("sqlite:///:memory:", future=True)

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    db_session = factory()
    db_session.add_all(
        [
            Store(id="store-1", name="Tienda 1 - Chapinero"),
            Store(id="store-2", name="Tienda 2 - Kennedy"),
        ]
    )
    db_session.commit()

    try:
        yield db_session
    finally:
        db_session.close()
        Base.metadata.drop_all(engine)


def add_invoice(session, store_id, store_invoice_id, lines):
    """`lines` is a list of (ean, product_name, quantity, unit_price)."""
    items = [
        InvoiceItem(
            ean=ean,
            product_name=name,
            quantity=quantity,
            unit_price=Decimal(price),
            subtotal=Decimal(price) * quantity,
        )
        for ean, name, quantity, price in lines
    ]
    invoice = Invoice(
        store_id=store_id,
        store_invoice_id=store_invoice_id,
        register_id="register-1",
        sold_at=datetime(2026, 8, 26, 12, 0, 0),
        received_at=datetime(2026, 8, 26, 12, 1, 0),
        total=sum(item.subtotal for item in items),
    )
    invoice.items = items
    session.add(invoice)
    session.commit()
    return invoice


# --- Sales per store -----------------------------------------------------


def test_each_store_reports_the_sum_of_its_own_invoices(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 2, "2000")])   # 4000
    add_invoice(session, "store-1", 2, [("222", "Leche", 1, "3500")])   # 3500
    add_invoice(session, "store-2", 1, [("111", "Arroz", 5, "2000")])   # 10000

    totals = {row.store_id: row for row in repository.sales_by_store(session)}

    assert totals["store-1"].total == Decimal("7500")
    assert totals["store-2"].total == Decimal("10000")


def test_a_store_total_never_includes_the_other_store(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 2, "2000")])

    totals = {row.store_id: row for row in repository.sales_by_store(session)}

    assert totals["store-2"].total == Decimal("0")


def test_a_store_with_no_sales_still_appears_with_zero(session):
    """Absent reads as a bug; zero reads as information."""
    add_invoice(session, "store-1", 1, [("111", "Arroz", 1, "2000")])

    rows = repository.sales_by_store(session)

    assert {row.store_id for row in rows} == {"store-1", "store-2"}
    assert next(r for r in rows if r.store_id == "store-2").invoice_count == 0


def test_the_report_carries_the_display_name_and_invoice_count(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 1, "2000")])
    add_invoice(session, "store-1", 2, [("111", "Arroz", 1, "2000")])

    row = next(r for r in repository.sales_by_store(session) if r.store_id == "store-1")

    assert row.store_name == "Tienda 1 - Chapinero"
    assert row.invoice_count == 2


def test_totals_with_no_data_at_all_are_zero_not_empty(session):
    rows = repository.sales_by_store(session)

    assert len(rows) == 2
    assert all(row.total == Decimal("0") for row in rows)


# --- Top products --------------------------------------------------------


def test_products_are_ranked_by_units_sold(session):
    add_invoice(
        session,
        "store-1",
        1,
        [("111", "Arroz", 3, "2000"), ("222", "Leche", 9, "1000")],
    )

    ranking = repository.top_products(session, limit=LIMIT)

    assert [row.ean for row in ranking] == ["222", "111"]
    assert ranking[0].units_sold == 9


def test_units_are_summed_per_ean_across_invoices_and_stores(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 3, "2000")])
    add_invoice(session, "store-2", 1, [("111", "Arroz", 4, "2000")])

    ranking = repository.top_products(session, limit=LIMIT)

    assert len(ranking) == 1
    assert ranking[0].units_sold == 7


def test_the_ranking_carries_revenue_alongside_units(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 3, "2000")])

    assert repository.top_products(session, limit=LIMIT)[0].revenue == Decimal("6000")


def test_the_ranking_is_capped_at_the_limit(session):
    lines = [(f"ean-{i}", f"Producto {i}", i + 1, "1000") for i in range(15)]
    for index, line in enumerate(lines):
        add_invoice(session, "store-1", index + 1, [line])

    assert len(repository.top_products(session, limit=LIMIT)) == LIMIT


def test_fewer_products_than_the_limit_are_not_padded(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 1, "2000")])

    assert len(repository.top_products(session, limit=LIMIT)) == 1


def test_no_sales_yields_an_empty_ranking(session):
    assert repository.top_products(session, limit=LIMIT) == []


# --- Store filter --------------------------------------------------------


def test_the_store_filter_counts_only_that_store(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 3, "2000")])
    add_invoice(session, "store-2", 1, [("111", "Arroz", 4, "2000")])

    ranking = repository.top_products(session, limit=LIMIT, store_id="store-1")

    assert ranking[0].units_sold == 3


def test_the_filtered_and_unfiltered_rankings_can_differ(session):
    # Arroz sells heavily at store 2, Leche at store 1.
    add_invoice(session, "store-1", 1, [("222", "Leche", 8, "1000")])
    add_invoice(session, "store-2", 1, [("111", "Arroz", 20, "2000")])

    chain_wide = [row.ean for row in repository.top_products(session, limit=LIMIT)]
    store_1 = [
        row.ean
        for row in repository.top_products(session, limit=LIMIT, store_id="store-1")
    ]

    assert chain_wide[0] == "111"
    assert store_1 == ["222"]


def test_a_filter_matching_nothing_yields_an_empty_ranking(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz", 3, "2000")])

    assert repository.top_products(session, limit=LIMIT, store_id="store-2") == []


# --- Grouping identity ---------------------------------------------------


def test_products_are_grouped_by_ean_not_by_name(session):
    """Two stores spelling the same product differently is still one product."""
    add_invoice(session, "store-1", 1, [("111", "Arroz Diana", 3, "2000")])
    add_invoice(session, "store-2", 1, [("111", "ARROZ DIANA 500g", 4, "2000")])

    ranking = repository.top_products(session, limit=LIMIT)

    assert len(ranking) == 1
    assert ranking[0].units_sold == 7


def test_one_name_is_shown_per_ean(session):
    add_invoice(session, "store-1", 1, [("111", "Arroz Diana", 3, "2000")])
    add_invoice(session, "store-2", 1, [("111", "ARROZ DIANA 500g", 4, "2000")])

    ranking = repository.top_products(session, limit=LIMIT)

    # The most recently recorded line wins.
    assert ranking[0].product_name == "ARROZ DIANA 500g"
