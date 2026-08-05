# 📊 Trading Dashboard

Dashboard centralizado para análisis de rendimiento y asignación de capital de sentinelas de trading automatizado.

## ✨ Características

- **Análisis de Rendimiento:** Calcula ROI, win rate, y P&L de cada bot (QQQ, QQQM, TQQQ, SPY)
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

- Fórmula: `Score = (Win_Rate × 0.6) + (ROI × 0.4)`
- Rango por símbolo: 10% - 40%
- Operaciones: 1% - 3% del capital asignado
