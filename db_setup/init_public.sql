-- SQL initialization script for the n8n Postgres database
-- Drop existing tables if they exist (useful when re‑running the
-- script manually).
-- SQL initialization script for the n8n Postgres database
--
-- This script is automatically executed by the Postgres image when
-- starting the container for the first time.  It defines core
-- database objects referenced in the workflow examples.


DROP TABLE IF EXISTS public.domain_values CASCADE;
DROP TABLE IF EXISTS public.domains CASCADE ;
DROP TABLE IF EXISTS public.fee_tariff CASCADE ;
DROP TABLE IF EXISTS public.products CASCADE;
DROP TABLE IF EXISTS public.product_types CASCADE;


CREATE TABLE IF NOT EXISTS public.domains (
  id              integer      PRIMARY KEY,
  domain_code     varchar(20)  NOT NULL UNIQUE,
  domain_desc     varchar(100) NOT NULL,
  domain_type     varchar(1)  NOT NUll, 
  creation_date   date         NOT NULL DEFAULT CURRENT_DATE,
  created_by     integer      NOT NULL
);

CREATE TABLE IF NOT EXISTS public.domain_values (
  id              integer      PRIMARY KEY,
  dmn_id          integer      NOT NULL REFERENCES public.domains(id) ON DELETE CASCADE,
  value           varchar(20)  NOT NULL,
  meaning         varchar(100) NOT NULL,
  date_in         date         NOT NULL DEFAULT CURRENT_DATE,
  date_out        date,
  creation_date   date         NOT NULL DEFAULT CURRENT_DATE,
  created_by     integer      NOT NULL
);



CREATE TABLE IF NOT EXISTS public.fee_tariff (
  id              integer PRIMARY KEY,
  fee_id          integer      NOT NULL,
  currency        varchar(3),
  tariff_percent          numeric(12,4),
  tariff_amount          numeric(12,2) ,
  min_amount      numeric(12,2),
  max_amount      numeric(12,2),
  date_in         date         NOT NULL DEFAULT CURRENT_DATE,
  date_out        date,
  creation_date   date         NOT NULL DEFAULT CURRENT_DATE,
  created_by     integer      NOT NULL
);



CREATE TABLE product_types (
    id SERIAL PRIMARY KEY,
    type_code VARCHAR(50) UNIQUE NOT NULL,
    type_description TEXT
);


CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    product_type_id INTEGER REFERENCES product_types(id) ON DELETE SET NULL,
    product_code VARCHAR(50) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    product_description TEXT
);



INSERT INTO public.domains (id, domain_code, domain_desc,domain_type, creation_date,created_by)
VALUES
  (1, 'DOM_COD_CAEN', 'Caen code register','S', DATE '2024-05-16',1439),
  (2, 'VALUE_CODE', 'Foreign key code','S', DATE '2024-08-22', 1439),
  (3, 'DOM_ASOC_OPT', 'Domain recording association between options and packages','S', DATE '2024-06-17',1122),
  (4, 'COD_SIND', 'Sind code register','S', DATE '2024-05-16',1439);


INSERT INTO public.domain_values (id, dmn_id, value, meaning, date_in, date_out, creation_date, created_by)
VALUES
  (1, 1, '1178', 'Found administration', DATE '2025-07-12', NULL, DATE '2024-05-10', 1295),
  (2, 1, '1186', 'Other auxiliary activities', DATE '2025-07-12', NULL, DATE '2024-02-16', 1781),
  (3, 1, '1125', 'Broker and insurance', DATE '2025-07-12', NULL, DATE '2024-08-05', 1978),
  (4, 2, 'EUR', 'Euro currency', DATE '2025-04-03', NULL, DATE '2024-10-23', 1409),
  (5, 2, 'USD', 'United States Dollar', DATE '2025-04-03', NULL, DATE '2024-08-29', 1431),
  (6, 2, 'GBP', 'British Pound Sterling', DATE '2025-04-03', NULL, DATE '2024-04-20', 1539),
  (7, 3, '670-3710', 'Association between option 670 and package 3710', DATE '2025-02-12', NULL, DATE '2024-12-15', 1589),
  (8, 3, '646-371', 'Association between option 646 and package 371', DATE '2025-02-12', NULL, DATE '2024-10-29', 1203),
  (9, 3, '517-2145', 'Association between option 517 and package 2145', DATE '2025-02-12', NULL, DATE '2024-10-16', 1643),
  (10, 4, 'CCCSND', 'Code from CCCSND products', DATE '2025-07-12', NULL, DATE '2024-05-10', 1295),
  (11, 4, 'CFSND', 'Code from CFSND products', DATE '2025-07-12', NULL, DATE '2025-02-16', 1781),
  (12, 4, 'VBSND', 'Code from VBSND products', DATE '2025-07-12', NULL, DATE '2025-08-05', 1968);
  


INSERT INTO public.fee_tariff 
(id, fee_id,currency, tariff_percent, tariff_amount, min_amount,max_amount,date_in,date_out,creation_date,created_by)
VALUES
  (1, 136,'ROL',null, 10 , 1,null,DATE '2023-05-16',null, DATE '2024-05-16',1248),
  (2, 138,'EUR',null, 20 , 1,null,DATE '2025-05-16',null, DATE '2024-05-16',1248),
  (3, 178,'ROL',0.01, null , 5,null,DATE '2024-07-16',null, DATE '2024-05-16',1283);



-- Seed data for product_types
INSERT INTO product_types (type_code, type_description) VALUES
    ('ELEC', 'Electronics'),
    ('FURN', 'Furniture'),
    ('CLOT', 'Clothing');


-- Seed data for products.  These reference the above product_types by id.
-- Note: the ids correspond to the insertion order above (ELEC=1, FURN=2, CLOT=3).
INSERT INTO products (product_type_id, product_code, product_name, product_description) VALUES
    (1, 'TV01', 'Television', '42 inch smart TV'),
    (1, 'LPTP', 'Laptop', 'Laptop with 16GB RAM'),
    (2, 'SOFA', 'Sofa', 'Three‑seater sofa'),
    (2, 'TABLE', 'Dining Table', 'Wooden dining table'),
    (3, 'TSHIRT', 'T‑Shirt', 'Cotton T‑shirt');


