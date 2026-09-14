-- Sample catalog so the system works from the first boot.
--
-- EAN codes use the `770` prefix, the GS1 country code for Colombia.
-- Product names are in Spanish: they are domain data of a Colombian store and
-- are read on screen by the cashier.
-- Prices are in Colombian pesos.

INSERT INTO products (ean, name, price) VALUES
    ('7702001010301', 'Arroz Diana 500g',              3200),
    ('7702001010318', 'Arroz Diana 1kg',               5900),
    ('7702354030014', 'Leche Alqueria Entera 1L',      4300),
    ('7702354030021', 'Leche Alqueria Deslactosada 1L', 5100),
    ('7702084010013', 'Panela Redonda 500g',           3800),
    ('7702191110026', 'Aceite Girasol 1L',             12400),
    ('7702011000123', 'Azucar Manuelita 1kg',          4700),
    ('7702025100019', 'Sal Refisal 500g',              1900),
    ('7702133000117', 'Cafe Sello Rojo 250g',          9800),
    ('7702133000124', 'Chocolate Corona 250g',         6500),
    ('7702007000418', 'Frijol Cargamanto 500g',        7200),
    ('7702007000425', 'Lenteja 500g',                  4100),
    ('7702189000212', 'Pasta Doria Espagueti 250g',    2800),
    ('7702189000229', 'Pasta Doria Tornillo 250g',     2800),
    ('7702426000315', 'Atun Van Camps Lomitos 160g',   6900),
    ('7702426000322', 'Sardina en Salsa 425g',         5400),
    ('7702093000116', 'Galletas Ducales 294g',         5600),
    ('7702093000123', 'Galletas Festival 403g',        7300),
    ('7702550000119', 'Papel Higienico Familia x4',    9900),
    ('7702550000126', 'Jabon Rey Barra 300g',          3400),
    ('7702018000217', 'Detergente Fab 900g',           11200),
    ('7702018000224', 'Crema Dental Colgate 150ml',    8700);
