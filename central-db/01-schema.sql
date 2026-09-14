-- Central (head office) schema.
--
-- Runs automatically on first boot, when the MySQL data volume is empty.
-- Destroying the environment with `make down` wipes the volume, so this file
-- runs again on the next `make up`.
--
-- This is MySQL, while the stores run PostgreSQL. That is deliberate: head
-- office and the stores are different systems, built by different teams at
-- different times, which is the normal state of affairs in a retail chain.
-- Where PostgreSQL writes SERIAL and NUMERIC, MySQL writes AUTO_INCREMENT and
-- DECIMAL; the concepts are the same.
--
-- Scope note: head office keeps NO product catalog. It only ever learns about
-- a product through an invoice that mentions it, which is why the product name
-- is stored on the invoice line.

-- The stores in the chain. Seeded in 02-seed.sql, never written by the API:
-- a store is part of the chain's configuration, not something an invoice can
-- create.
CREATE TABLE stores (
    id   VARCHAR(20)  NOT NULL PRIMARY KEY,
    name VARCHAR(80)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One consolidated invoice per completed purchase at a store.
CREATE TABLE invoices (
    id               INT            NOT NULL AUTO_INCREMENT PRIMARY KEY,
    store_id         VARCHAR(20)    NOT NULL,
    -- The invoice's identifier IN ITS OWN STORE. Both stores number their
    -- sales from 1, so this is unique only when paired with store_id — which
    -- is exactly what the constraint below says.
    store_invoice_id INT            NOT NULL,
    register_id      VARCHAR(40)    NOT NULL,
    -- When the sale happened, as reported by the store.
    sold_at          DATETIME       NOT NULL,
    -- When head office received it. Kept separately from sold_at so that a
    -- delivery delay, or a store whose clock is wrong, is visible rather than
    -- invisible.
    received_at      DATETIME       NOT NULL,
    total            DECIMAL(12, 2) NOT NULL,

    CONSTRAINT ck_invoices_total CHECK (total >= 0),
    CONSTRAINT fk_invoices_store FOREIGN KEY (store_id) REFERENCES stores (id),

    -- The idempotency guarantee. A forwarder that never saw our response
    -- retries the batch; without this constraint that retry would silently
    -- double the store's reported revenue and the dashboard would lie with a
    -- straight face. Enforced by the database rather than by an application
    -- check, so it holds even when two batches race.
    CONSTRAINT uq_invoices_store_invoice UNIQUE (store_id, store_invoice_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- One line per product sold on an invoice.
CREATE TABLE invoice_items (
    id           INT            NOT NULL AUTO_INCREMENT PRIMARY KEY,
    invoice_id   INT            NOT NULL,
    ean          VARCHAR(13)    NOT NULL,
    -- Denormalized on purpose. Head office has no catalog to resolve an EAN
    -- against, and an invoice is a historical document: the name printed on it
    -- is the name at the time of sale.
    product_name VARCHAR(120)   NOT NULL,
    quantity     INT            NOT NULL,
    -- Frozen at charge time, exactly as the store recorded them.
    unit_price   DECIMAL(12, 2) NOT NULL,
    subtotal     DECIMAL(12, 2) NOT NULL,

    CONSTRAINT ck_invoice_items_quantity CHECK (quantity > 0),
    CONSTRAINT ck_invoice_items_unit_price CHECK (unit_price >= 0),
    CONSTRAINT ck_invoice_items_subtotal CHECK (subtotal >= 0),
    CONSTRAINT fk_invoice_items_invoice
        FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes for the two dashboard reports. Without them both aggregations are
-- full table scans; the queries would still be correct, and would still be
-- fast at classroom volume, which is precisely why it is worth declaring them
-- explicitly rather than discovering the need later.

-- "Total sales per store" groups by this column.
CREATE INDEX idx_invoices_store_id ON invoices (store_id);

-- The top-products report joins lines back to their invoice to filter by store.
CREATE INDEX idx_invoice_items_invoice_id ON invoice_items (invoice_id);

-- The top-products report groups by EAN, which is the stable product identity.
CREATE INDEX idx_invoice_items_ean ON invoice_items (ean);
