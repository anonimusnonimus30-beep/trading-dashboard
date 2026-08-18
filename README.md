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
├── capital_allocator.py         # Calcula asignación óptima
├── dashboard_generator.py       # Genera HTML del dashboard
├── requirements.txt
├── index.html                   # Dashboard (generado)
└── .github/workflows/update-dashboard.yml
```

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
