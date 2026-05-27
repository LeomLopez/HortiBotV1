BEGIN;

ALTER TABLE movimientos
DROP CONSTRAINT IF EXISTS chk_mov_contenedor;

ALTER TABLE movimientos
ADD CONSTRAINT chk_mov_contenedor
CHECK (
    (grupo = 'CON' AND contenedor IN ('PICK', 'C1', 'C2', 'C3'))
    OR
    (grupo <> 'CON' AND contenedor = 'N/A')
);

ALTER TABLE stock_actual
DROP CONSTRAINT IF EXISTS chk_stock_contenedor;

ALTER TABLE stock_actual
ADD CONSTRAINT chk_stock_contenedor
CHECK (
    (grupo = 'CON' AND contenedor IN ('PICK', 'C1', 'C2', 'C3'))
    OR
    (grupo <> 'CON' AND contenedor = 'N/A')
);

COMMIT;
