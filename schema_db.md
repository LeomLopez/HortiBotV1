📦 ESQUEMA DE BASE DE DATOS

Proyecto: Bot de Estoque
Motor: PostgreSQL (Neon)
Tablas activas: movimientos, stock_actual

1️⃣ Tabla: movimientos
Propósito

Guarda el histórico completo de todos los movimientos de inventario.
Nunca se eliminan registros. Es la base para auditoría y análisis.

Estructura

id → integer, PRIMARY KEY

nombre → varchar, NOT NULL

cantidad → integer, NOT NULL

tipo → text, NOT NULL
(entrada | saida | descarte | devolucao | ajuste)

fecha_producto → date, NOT NULL

unidade → varchar, NULLABLE

grupo → varchar, NULLABLE
(HOR | CON | SEC | QUI | DES)

contenedor → varchar, NULLABLE
(C1 | C2 | C3 | N/A)

concepto → varchar, NULLABLE

fecha_movimiento → timestamp, DEFAULT CURRENT_TIMESTAMP

Características

Tabla de eventos (event sourcing)

No se actualiza

No se elimina

Representa la verdad histórica del sistema

2️⃣ Tabla: stock_actual
Propósito

Representa el estado actual consolidado del inventario.
Solo contiene lotes con cantidad mayor a 0.

Estructura

nombre → varchar, NOT NULL

unidade → varchar, NOT NULL

grupo → varchar, NOT NULL

fecha_producto → date, NOT NULL

contenedor → varchar, NOT NULL

cantidad → integer, NOT NULL DEFAULT 0

Clave primaria compuesta

PRIMARY KEY (nombre, unidade, grupo, fecha_producto, contenedor)

Esto permite:

Separar lotes por fecha (FIFO)

Separar congelados por contenedor

Usar ON CONFLICT en inserciones

Evitar duplicados de lote

🔄 Flujo del sistema

Se inserta registro en movimientos

Se actualiza stock_actual

Si cantidad <= 0, el lote se elimina de stock_actual

🧠 Modelo conceptual actual

Un lote está definido por:

nombre + unidade + grupo + fecha_producto + contenedor

Eso representa una unidad única de inventario.

📊 Arquitectura

movimientos → histórico completo
stock_actual → estado derivado

Sistema basado en eventos con estado materializado.
