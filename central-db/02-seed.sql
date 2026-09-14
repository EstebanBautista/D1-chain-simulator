-- The stores in the chain.
--
-- Seeded rather than created by the API: which stores exist is part of the
-- chain's configuration, and a batch naming an unknown store must be rejected
-- rather than quietly inventing one.
--
-- The identifiers are English, matching the STORE_ID each store's containers
-- are configured with. The names are Spanish, because they are what a reader
-- sees on the dashboard.

INSERT INTO stores (id, name) VALUES
    ('store-1', 'Tienda 1 - Chapinero'),
    ('store-2', 'Tienda 2 - Kennedy');
