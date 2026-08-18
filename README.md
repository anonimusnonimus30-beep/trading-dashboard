# 📊 Trading Dashboard

Dashboard centralizado para análisis de rendimiento y asignación de capital de sentinelas de trading automatizado.

## ✨ Características

- **Análisis de Rendimiento:** Calcula ROI, win rate, y P&L de cada bot (QQQ, QQQM, TQQQ, SPY, ARKK)
- **Asignación Dinámica de Capital:** Recalcula diariamente según rendimiento histórico
- **Dashboard HTML:** Visualización interactiva de operaciones y métricas
- **GitHub Pages:** Publicación automática en línea

## 📋 Estructura

```
├── performance_analyzer.py      # Analiza fills de Alpaca
├── positions_analyzer.py        # Posición actual + próxima señal + estado del workflow de cada bot
├── capital_allocator.py         # Calcula asignación óptima
├── dashboard_generator.py       # Genera HTML del dashboard
├── database.py                  # Actualiza sentinels.db (ver abajo)
├── requirements.txt
├── index.html                   # Dashboard (generado)
├── sentinels.db                 # Base SQLite con histórico de los 5 bots (generada)
└── .github/workflows/update-dashboard.yml
```

## 🗄️ Base de datos (sentinels.db)

SQLite con el histórico y estado de los 5 bots, para análisis propio
fuera del dashboard (no la lee el HTML generado). Se actualiza en cada
corrida del workflow. Consultarla con `sqlite3 sentinels.db` o desde
Python/pandas (`pd.read_sql("SELECT * FROM trades", sqlite3.connect("sentinels.db"))`).

Tablas:

- **`trades`** — cada operación cerrada (compra+venta emparejada por FIFO) de los 5 bots, histórico completo desde que arrancó cada uno.
- **`signal_history`** — score/exposición objetivo por día de cada bot, histórico completo (viene de `*_signal_log.csv` de cada repo). QQQ usa columnas distintas (`v5_active`, `bear_confirmed`) por tener otro modelo, no de score 0-100.
- **`positions_snapshot`** / **`performance_snapshot`** / **`capital_allocation_snapshot`** — una fila nueva por símbolo en CADA corrida (con `snapshot_at`). A diferencia de las dos tablas anteriores, esto **no es retroactivo**: el histórico de estas tres tablas arranca desde que existe esta base, no desde que arrancó cada bot (antes de esto el dashboard solo guardaba el último estado y lo sobreescribía).

`trades` y `signal_history` se reimportan completas en cada corrida pero no duplican (clave única + `INSERT OR IGNORE`).

⚠️ El historial de `signal_history` de SPY anterior al 2026-08-18 se calculó con precio de QQQM, no de SPY (bug de copy-paste ya corregido ese día) — es historial real de lo que el bot vio en ese momento, no un error de esta base.

## 🔐 Secrets Requeridos

- `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `APCA_BASE_URL` (Cuenta QQQ/QQQM/TQQQ)
- `SPY_APCA_API_KEY`, `SPY_APCA_API_SECRET`, `SPY_APCA_API_BASE_URL` (Cuenta SPY)

## ⚙️ Ejecución

Automática: **Diariamente 21:00 UTC** (después del cierre de mercado)

## 📊 Asignación de Capital

Reparto por niveles, no libre entre los 5 símbolos (ver capital_allocator.py):

- **Core (80% del capital): QQQ, SPY** — índices amplios, sin apalancamiento.
- **Satellite (20% del capital): TQQQ, ARKK** — apalancado / cartera concentrada, mayor riesgo.
- **Paused (0% del capital): QQQM** — mismo índice que QQQ, no diversifica; sigue corriendo (señal, estado, auto-aprendizaje) pero sin capital asignado.

Dentro de cada nivel, el score `(Win_Rate × 0.6) + (ROI × 0.4)` reparte el presupuesto de ESE nivel entre sus miembros (piso 30% / techo 70% por símbolo dentro del nivel). El rendimiento nunca mueve capital entre niveles.

- Operaciones: 1% - 3% del capital asignado
