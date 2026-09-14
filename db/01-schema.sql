-- Store schema.
--
-- Runs automatically on first boot, when the PostgreSQL data volume is empty.
-- Destroying the environment with `make down` wipes the volume, so this file
-- runs again on the next `make up`.
--
-- Scope note: no stock control and no product images, by design.

-- Price master. `ean` is the barcode and doubles as the primary key, since a
-- product is identified by its barcode at the point of sale.
CREATE TABLE products (
    ean   VARCHAR(13)   PRIMARY KEY,
    name  VARCHAR(120)  NOT NULL,
    price NUMERIC(12, 2) NOT NULL CHECK (price >= 0)
);

-- Sale header. One row per completed purchase, written only after the payment
-- gateway approves the charge.
CREATE TABLE sales (
    id          SERIAL         PRIMARY KEY,
    sale_date   TIMESTAMP      NOT NULL,
    total       NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
    register_id VARCHAR(20)    NOT NULL,
    -- When head office confirmed it holds this sale. NULL means "still in the
    -- queue": the forwarder picks these up, ships them in batches and stamps
    -- this column only once the central site has acknowledged them.
    --
    -- The queue lives here, in the store's own database, rather than in the
    -- forwarder's memory. That is what lets the store keep selling while head
    -- office is unreachable, and lets you watch the backlog with:
    --     SELECT id, sale_date, total FROM sales WHERE forwarded_at IS NULL;
    forwarded_at TIMESTAMP     NULL
);

-- The forwarder asks for the oldest unforwarded sales on every polling cycle.
-- A partial index keeps that cheap: it only covers the rows still in the
-- queue, so it stays small no matter how many sales the store accumulates.
CREATE INDEX idx_sales_pending_forward
    ON sales (id)
    WHERE forwarded_at IS NULL;

-- Sale detail. `unit_price` and `subtotal` are stored rather than derived so
-- the sale stays auditable if the product price changes later.
CREATE TABLE sale_items (
    id         SERIAL         PRIMARY KEY,
    sale_id    INTEGER        NOT NULL REFERENCES sales (id) ON DELETE CASCADE,
    ean        VARCHAR(13)    NOT NULL REFERENCES products (ean),
    quantity   INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12, 2) NOT NULL CHECK (unit_price >= 0),
    subtotal   NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0)
);

-- Sale detail is always read by sale, never on its own.
CREATE INDEX idx_sale_items_sale_id ON sale_items (sale_id);
