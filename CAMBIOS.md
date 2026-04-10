# Registro de Cambios — Resolución de Issues de GitHub

Documento que detalla los cambios realizados para resolver los 8 issues reportados en el repositorio **charlydime/cardissues**.

---

## Issue #1 — `feat: implement missing sql_generator.py module`

**Rama:** `copilot/fix-issue-1-sql-generator`  
**Commit:** [`4bf308f`](https://github.com/charlydime/cardissues/commit/4bf308fc9d73aa38fd3dfadffbbfff2681f56788)  
**Líneas cambiadas:** +350 / -2

### Problema
El módulo `src/card_issues/sql_generator.py` estaba documentado en `AGENTS.md` como parte del paquete, pero no existía en el repositorio. Sin él era imposible implementar el flujo de razonamiento del agente ni la herramienta `generate_sql_query`.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/sql_generator.py` | **Creado** | Módulo nuevo con la lista `_TEMPLATES` de tuplas `(patrón, plantilla SQL)` y la función `generate_sql_query(question: str) -> str`. Cubre patrones de disputas por comerciante, código de razón y rango de fechas. |
| `tests/test_sql_generator.py` | **Creado** | 147 líneas de pruebas unitarias que verifican el matching de plantillas NL→SQL. |
| `tests/__init__.py` | **Creado** | Archivo de inicialización del paquete de pruebas. |
| `src/card_issues/server.py` | **Modificado** | +29 líneas — Se expuso la función `generate_sql_query` como herramienta MCP provisional. |
| `src/card_issues/sqlite_store.py` | **Modificado** | Ajuste menor de importación. |

---

## Issue #2 — `feat: add generate_sql_query and execute_sql_query MCP tools`

**Rama:** `copilot/fix-issue-2-mcp-sql-tools`  
**Commit:** [`59270c3`](https://github.com/charlydime/cardissues/commit/59270c3cdea0e1c37de14134a45afa3224267300)  
**Líneas cambiadas:** +362 / -7

### Problema
El flujo de razonamiento del agente documentado en `AGENTS.md` requería dos herramientas MCP que no existían: `generate_sql_query` y `execute_sql_query`. Solo existían `visa_rules_search`, `merchant_dispute_lookup` y `kb_fallback`.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/server.py` | **Modificado** | +41 líneas — Se añadieron los decoradores `@mcp.tool()` para `generate_sql_query(question: str) -> str` (delega a `sql_generator.py`) y `execute_sql_query(sql: str) -> list[dict]` (delega a `sqlite_store.execute_readonly`). `execute_sql_query` rechaza cualquier sentencia no-SELECT. |
| `src/card_issues/sql_generator.py` | **Creado** | +98 líneas — Versión completa del motor de plantillas NL→SQL con `_TEMPLATES`. |
| `AGENTS.md` | **Modificado** | +2 líneas — Se actualizó la tabla de contrato de herramientas con las firmas de las dos nuevas tools. |
| `tests/test_execute_sql_query.py` | **Creado** | +98 líneas — Pruebas de integración para `execute_sql_query`: SELECT permitido, INSERT/UPDATE/DELETE/DROP rechazados. |
| `tests/test_sql_generator.py` | **Creado** | +45 líneas — Pruebas unitarias para el matching de patrones NL→SQL. |
| `pyproject.toml` | **Modificado** | +6 líneas — Se añadió pytest y dependencias de prueba. |
| `uv.lock` | **Modificado** | Actualización del lockfile. |

---

## Issue #3 — `test: create tests/ directory and unit tests for all modules`

**Rama:** `copilot/test-suite-3`  
**Commits:** [`1652db8`](https://github.com/charlydime/cardissues/commit/1652db81f9b6fe9af44cf5c19aec15e66d79602a) · [`3caa7a5`](https://github.com/charlydime/cardissues/commit/3caa7a57b88c0ecf3a95e6a3a6d2f8a614b8c8d0)  
**Líneas cambiadas:** +704 / -5

### Problema
No existía ningún directorio `tests/`. `AGENTS.md` indicaba que cada nueva herramienta debía tener pruebas unitarias, pero no había una base para construirlas ni ejecutarlas.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `tests/__init__.py` | **Creado** | Inicialización del paquete de pruebas. |
| `tests/test_sqlite_store.py` | **Creado** | +143 líneas — Pruebas para `execute_readonly` (SELECT permitido, 5 variantes no-SELECT rechazadas: INSERT, UPDATE, DELETE, DROP, insert en minúsculas) y para `get_merchant_disputes` (estructura de claves, total, stats, cap de 10 elementos, comerciante desconocido devuelve dict vacío). |
| `tests/test_chroma_store.py` | **Creado** | +171 líneas — Pruebas para `upsert_chunks` (individual, múltiple, upsert idempotente) y `search` (tipo lista, claves, cap de n_results, tipo distancia, filtro `where` de metadatos, colección vacía). Usa clase `_FakeEmbedding` mediante `monkeypatch` para evitar descarga del modelo ONNX. |
| `tests/test_ingest.py` | **Creado** | +146 líneas — Pruebas para `_clean` (eliminación de pie de página, colapso de líneas en blanco, eliminación de banners), `_infer_tx_type` (3 ramas vía parametrize) y `extract_conditions` (retorna Polars DataFrame, columnas correctas, parseo multi-condición, merge de páginas duplicadas). El parseo de PDF se mockea con `unittest.mock`. |
| `tests/test_server.py` | **Creado** | +193 líneas — Pruebas para las tres herramientas MCP: `visa_rules_search` (tipo retorno, claves requeridas, truncado a 400 chars, fallback sin filtro), `merchant_dispute_lookup` (delega a sqlite_store, retorna dict), `kb_fallback` (hits vacíos → `manual_review=True`, claves del resultado, umbrales de confianza, truncado a 800 chars). Todas las dependencias externas se mockean. |
| `pyproject.toml` | **Modificado** | +8 líneas — Se añadió `[tool.pytest.ini_options]` con `testpaths = ["tests"]` y `pytest>=8.0` en el grupo de dependencias de desarrollo. |
| `uv.lock` | **Modificado** | Actualización del lockfile. |

---

## Issue #4 — `docs: add README.md for developers and users`

**Rama:** `copilot/update-readme-file`  
**Commit:** [`7f10a3b`](https://github.com/charlydime/cardissues/commit/7f10a3b0cf059e9ce4482a6bf6eaf760fde76b3d)  
**Líneas cambiadas:** +173

### Problema
El repositorio tenía `AGENTS.md` (dirigido a agentes de IA) y `evidencia_funcionamient.md` (captura de sesión de chat), pero ningún `README.md` para desarrolladores humanos.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `README.md` | **Creado** | +173 líneas — Documentación completa que cubre: propósito del proyecto, prerrequisitos, instalación con `uv sync`, pipeline de datos (ingestión PDF y seed de datos), ejecución del servidor MCP, configuración del cliente MCP (VS Code / Claude Desktop), comandos de desarrollo (lint, formato, pruebas) y descripción breve de cada herramienta MCP con sus entradas y salidas esperadas. |

---

## Issue #5 — `improvement: improve kb_fallback answer quality`

**Rama:** `copilot/5-kb-fallback-mejora`  
**Commit:** [`b67e59e`](https://github.com/charlydime/cardissues/commit/b67e59e83649b197b4db22537674d3de6a8c6eee)  
**Líneas cambiadas:** +228 / -12

### Problema
`kb_fallback` devolvía hasta 800 caracteres del primer resultado de ChromaDB como `answer`. Era un fragmento de texto crudo del PDF que no siempre respondía directamente la pregunta y carecía de contexto. El llamante no podía identificar la fuente de la información.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/server.py` | **Modificado** | +36 / -5 líneas — `kb_fallback` ahora consulta los 3 mejores resultados de ChromaDB en lugar de 1. Por cada resultado calificado concatena el título de sección (`section`) + fragmento relevante para construir una respuesta más rica. Se añadió el campo `sources: list[str]` con los `condition_id` de las fuentes encontradas. Se preservaron los campos existentes: `confidence`, `manual_review`. |
| `AGENTS.md` | **Modificado** | +1 / -1 líneas — Se actualizó la tabla de contrato de la herramienta `kb_fallback` para reflejar el nuevo campo `sources`. |
| `tests/test_kb_fallback.py` | **Creado** | +113 líneas — 8 pruebas unitarias: hits vacíos → `manual_review=True`, claves del resultado, umbrales de confianza (alto/bajo), respuesta vacía por debajo de 0.3, respuesta poblada por encima de 0.3, truncado a 800 chars, y verificación de que `confidence` es `float`. |
| `pyproject.toml` | **Modificado** | Actualización de dependencias de prueba. |
| `uv.lock` | **Modificado** | Actualización del lockfile. |

---

## Issue #6 — `improvement: chunk PDF conditions by subsection for better search precision`

**Rama:** `copilot/pdf-chunking`  
**Commits:** [`e1a5562`](https://github.com/charlydime/cardissues/commit/e1a5562714f710d409482cb1e5dd11454397a567) · [`c50e7f6`](https://github.com/charlydime/cardissues/commit/c50e7f6e5c743fbf2d3b1a758753840146f532b7)  
**Líneas cambiadas:** +79 / -14

### Problema
`ingest.py` cargaba cada condición de disputa Visa completa como un único documento en ChromaDB. Las condiciones largas cubren múltiples subtemas (razón de notificación, pasos de respuesta, evidencia, plazos), lo que reducía la precisión de la búsqueda semántica — una query sobre "evidencia requerida" podía devolver un chunk donde la evidencia era solo un subtema menor.

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/ingest.py` | **Modificado** | +71 / -11 líneas — Se añadió lógica para dividir el cuerpo de cada condición por encabezados de subsección (ej. "Why did I get this notification?", "How should I respond?", "What evidence should I provide?"). Cada subsección se upserta como documento independiente con metadatos `condition_id` + nuevo campo `subsection`. Se añadieron constantes regex comentadas para los patrones de encabezado. La re-ingestión es idempotente (garantías de upsert mantenidas). |
| `src/card_issues/server.py` | **Modificado** | +7 / -2 líneas — El filtro `where` de `visa_rules_search` sigue funcionando con la nueva estructura de metadatos. Se restauró `condition_id` en el campo `rule_id` del resultado. |
| `src/card_issues/sqlite_store.py` | **Modificado** | Ajuste menor de importación. |

---

## Issue #7 — `improvement: add input validation and explicit not-found handling in sqlite_store`

**Rama:** `copilot/fix-issue-7-sqlite-validation`  
**Commits:** [`ef8424b`](https://github.com/charlydime/cardissues/commit/ef8424be0383eae03583abc5ad6b6f05e434521f) · [`16a439b`](https://github.com/charlydime/cardissues/commit/16a439bf57995472e085220dab1878101e7ae204)  
**Líneas cambiadas:** +146 / -2

### Problema
`get_merchant_disputes` en `sqlite_store.py` aceptaba cualquier cadena como `merchant_id` sin validar su formato, y devolvía un dict con aspecto válido (`{"total_disputes": 0, "recent_disputes": [], "resolution_stats": {}}`) cuando el comerciante no existía. El llamante no podía distinguir "comerciante existe pero sin disputas" de "comerciante no encontrado".

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/sqlite_store.py` | **Modificado** | +33 / -2 líneas — Se añadió validación del formato de `merchant_id`: no puede estar vacío, no puede contener caracteres especiales; lanza `ValueError` con mensaje descriptivo en caso de entrada inválida. Se añadió el campo booleano `found` en el dict de respuesta, lo que permite al cliente MCP informar apropiadamente al usuario cuando el comerciante no existe. |
| `tests/test_sqlite_store.py` | **Creado** | +113 líneas — Pruebas para: `execute_readonly` (SELECT permitido, INSERT/UPDATE/DELETE/DROP rechazados), `get_merchant_disputes` (estructura de claves, conteo total, stats de resolución, presencia de campos, cap de 10 elementos, comerciante desconocido devuelve dict con `found=False`). |

---

## Issue #8 — `feat: add a CLI command or flag to force-rebuild the ChromaDB index`

**Rama:** `copilot/fix-issue-8-force-rebuild`  
**Commits:** [`47367bb`](https://github.com/charlydime/cardissues/commit/47367bba84de9ce2be2c8aae5607f19eb2812ad4) · [`a7644da`](https://github.com/charlydime/cardissues/commit/a7644da4b413e8d1c45a1b2b8c8c061e76facce7)  
**Líneas cambiadas:** +97 / -8

### Problema
Actualizar el índice vectorial requería eliminación manual de `data/chroma/` y re-ejecución de `uv run python -m card_issues.ingest`. No había flag `--force`, ni ruta de actualización parcial, ni indicación del estado actual del índice (cuántos chunks, qué versión del PDF se usó).

### Cambios realizados

| Archivo | Tipo | Descripción |
|---|---|---|
| `src/card_issues/ingest.py` | **Modificado** | +48 / -4 líneas — Se añadió el argumento de línea de comandos `--force` mediante `argparse`. Cuando se pasa `--force`, la colección es eliminada y reconstruida desde cero. Al inicio, el script imprime el conteo de chunks existentes en la colección y compara el timestamp de última modificación del PDF con el de la colección, informando si el índice está desactualizado. |
| `src/card_issues/chroma_store.py` | **Modificado** | +41 / -2 líneas — Se añadió el método `delete_collection()` para soportar el rebuild forzado. Se ajustó el manejo de excepciones para capturar solo tipos específicos (no `Exception` genérico), cumpliendo con el feedback del code review. |
| `AGENTS.md` | **Modificado** | +7 / -1 líneas — Se documentó el nuevo comando `--force` bajo la sección "Data pipeline commands": `uv run python -m card_issues.ingest --force`. |
| `src/card_issues/sqlite_store.py` | **Modificado** | Ajuste menor de importación. |

---

## Resumen de cambios por archivo

| Archivo | Issues relacionados | Acción |
|---|---|---|
| `src/card_issues/sql_generator.py` | #1, #2 | Creado |
| `src/card_issues/server.py` | #1, #2, #5, #6 | Modificado |
| `src/card_issues/sqlite_store.py` | #7 | Modificado |
| `src/card_issues/ingest.py` | #6, #8 | Modificado |
| `src/card_issues/chroma_store.py` | #8 | Modificado |
| `README.md` | #4 | Creado |
| `AGENTS.md` | #2, #5, #8 | Modificado |
| `pyproject.toml` | #2, #3, #5 | Modificado |
| `tests/__init__.py` | #1, #3 | Creado |
| `tests/test_sql_generator.py` | #1, #2 | Creado |
| `tests/test_execute_sql_query.py` | #2 | Creado |
| `tests/test_sqlite_store.py` | #3, #7 | Creado |
| `tests/test_chroma_store.py` | #3 | Creado |
| `tests/test_ingest.py` | #3 | Creado |
| `tests/test_server.py` | #3 | Creado |
| `tests/test_kb_fallback.py` | #5 | Creado |
| `uv.lock` | #2, #3, #5 | Modificado |
