#!/usr/bin/env python3
"""
Generador de dashboard HTML con operaciones, P&L y asignación de capital.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def safe_float_fmt(value, decimals=2):
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "0.00"


ECUADOR_OFFSET = timedelta(hours=-5)  # America/Guayaquil, sin horario de verano


def to_ecuador_time(iso_timestamp):
    """Convierte un timestamp ISO en UTC (el que guardan los scripts,
    ej. capital_allocation.json) a hora de Ecuador para mostrar en el
    dashboard. Ecuador no tiene horario de verano, así que un offset
    fijo de -5 alcanza -- no hace falta zoneinfo/tzdata."""
    if not iso_timestamp or iso_timestamp == "N/A":
        return "N/A"
    try:
        ts = iso_timestamp.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(ts)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        dt_ecuador = dt_utc.astimezone(timezone(ECUADOR_OFFSET))
        return dt_ecuador.strftime("%Y-%m-%d %H:%M:%S") + " (hora de Ecuador)"
    except (ValueError, TypeError):
        return iso_timestamp


class DashboardGenerator:
    def __init__(
        self,
        performance_file="performance.json",
        allocation_file="capital_allocation.json",
        positions_file="positions.json",
        analysis_progress_file="analysis_progress.json",
        nyse_scanner_file="nyse_scanner.json",
    ):
        self.performance_file = performance_file
        self.allocation_file = allocation_file
        self.positions_file = positions_file
        self.analysis_progress_file = analysis_progress_file
        self.nyse_scanner_file = nyse_scanner_file
        self.performance_data = self._load_json(performance_file)
        self.allocation_data = self._load_json(allocation_file)
        self.positions_data = self._load_json(positions_file)
        self.analysis_progress_data = self._load_json(analysis_progress_file)
        self.nyse_scanner_data = self._load_json(nyse_scanner_file)

    def _load_json(self, filepath):
        if not Path(filepath).exists():
            return {}
        with open(filepath) as f:
            return json.load(f)

    def generate_html(self):
        """Genera el HTML del dashboard"""
        allocation = self.allocation_data.get("allocation_pct", {})
        total_capital = self.allocation_data.get("total_capital", 0)
        trades_data = {}

        # Recolectar todas las operaciones
        for symbol, perf in self.performance_data.items():
            trades_data[symbol] = perf.get("trades", [])

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Dashboard - Sentinelas Alpaca</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        h1 {{
            color: #00ff88;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}

        .last-update {{
            color: #888;
            font-size: 0.9em;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .metric-card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}

        .metric-label {{
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}

        .metric-value {{
            font-size: 2em;
            color: #00ff88;
            font-weight: bold;
        }}

        .negative {{ color: #ff4444 !important; }}

        .allocation-section {{
            margin-bottom: 40px;
        }}

        .allocation-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}

        .allocation-card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
        }}

        .symbol {{
            font-size: 1.3em;
            font-weight: bold;
            color: #00ff88;
            margin-bottom: 10px;
        }}

        .allocation-bar {{
            background: rgba(0, 255, 136, 0.1);
            height: 30px;
            border-radius: 5px;
            overflow: hidden;
            margin-bottom: 10px;
            border: 1px solid rgba(0, 255, 136, 0.3);
        }}

        .allocation-fill {{
            background: linear-gradient(90deg, #00ff88, #00cc6a);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-weight: bold;
            font-size: 0.9em;
        }}

        .allocation-info {{
            font-size: 0.85em;
            color: #aaa;
        }}

        .section-title {{
            font-size: 1.5em;
            color: #00ff88;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(0, 255, 136, 0.3);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 30px;
        }}

        th {{
            background: rgba(0, 255, 136, 0.1);
            color: #00ff88;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            border-bottom: 1px solid rgba(0, 255, 136, 0.3);
        }}

        td {{
            padding: 12px 15px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        tr:hover {{
            background: rgba(0, 255, 136, 0.05);
        }}

        .positive {{
            color: #00ff88;
        }}

        .negative {{
            color: #ff4444;
        }}

        .position-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .position-card {{
            position: relative;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
            overflow: hidden;
        }}

        .position-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            font-size: 0.9em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .position-row span:first-child {{
            color: #aaa;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 600;
        }}

        .badge-pending {{
            background: rgba(255, 193, 7, 0.15);
            color: #ffc107;
            border: 1px solid rgba(255, 193, 7, 0.4);
        }}

        .badge-ok {{
            background: rgba(0, 255, 136, 0.1);
            color: #00ff88;
            border: 1px solid rgba(0, 255, 136, 0.3);
        }}

        .badge-none {{
            background: rgba(255, 255, 255, 0.05);
            color: #888;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .position-card.suspended {{
            opacity: 0.75;
        }}

        .learning-bar {{
            background: rgba(255, 255, 255, 0.06);
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin: 4px 0 2px;
        }}

        .learning-fill {{
            background: linear-gradient(90deg, #7dd3fc, #38bdf8);
            height: 100%;
        }}

        .learning-fill.due {{
            background: linear-gradient(90deg, #ffc107, #ff9800);
        }}

        .stamp-suspended {{
            position: absolute;
            top: 18px;
            right: -34px;
            width: 150px;
            transform: rotate(28deg);
            text-align: center;
            padding: 5px 0;
            font-size: 0.72em;
            font-weight: 800;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #ff5757;
            background: rgba(255, 87, 87, 0.12);
            border-top: 2px solid #ff5757;
            border-bottom: 2px solid #ff5757;
            pointer-events: none;
        }}

        footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: #666;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .metrics-grid {{
                grid-template-columns: 1fr;
            }}
            .allocation-grid {{
                grid-template-columns: 1fr;
            }}
            h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Trading Dashboard</h1>
            <p class="last-update">Última actualización: {to_ecuador_time(self.allocation_data.get("timestamp"))}</p>
            <p style="margin-top: 10px; color: #00ff88; font-size: 1.2em;">
                Capital Total: <strong>${total_capital:,.2f}</strong>
            </p>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Operaciones Totales</div>
                <div class="metric-value">{sum(len(trades_data.get(s, [])) for s in self.performance_data)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">P&L Realizado</div>
                <div class="metric-value {('negative' if sum(self.performance_data.get(s, {}).get('realized_pnl', 0) for s in self.performance_data) < 0 else '')}">
                    ${sum(self.performance_data.get(s, {}).get('realized_pnl', 0) for s in self.performance_data):,.2f}
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate Promedio</div>
                <div class="metric-value">
                    {(sum(self.performance_data.get(s, {}).get('win_rate', 0) for s in self.performance_data) / len(self.performance_data) if self.performance_data else 0):.1f}%
                </div>
            </div>
        </div>

        <div class="allocation-section">
            <h2 class="section-title">💰 Asignación de Capital Diaria</h2>
            <div class="allocation-grid">
"""

        for symbol in ["QQQ", "SPY", "TQQQ", "ARKK", "DIA", "IWM", "USMV", "NVDA", "AVGO", "MU", "SMH", "SOXX", "QTUM"]:
            pct = allocation.get(symbol, 20)
            usd = self.allocation_data.get("allocation_usd", {}).get(symbol, 0)
            trade_range = self.allocation_data.get("trade_size_range", {}).get(symbol, {})

            html += f"""
                <div class="allocation-card">
                    <div class="symbol">{symbol}</div>
                    <div class="allocation-bar">
                        <div class="allocation-fill" style="width: {pct}%;">{pct}%</div>
                    </div>
                    <div class="allocation-info">
                        <div>Capital: ${usd:,.2f}</div>
                        <div style="margin-top: 8px; font-size: 0.8em; color: #666;">
                            Rango: ${trade_range.get('min', 0):,.2f} - ${trade_range.get('max', 0):,.2f}
                        </div>
                    </div>
                </div>
"""

        html += """
            </div>
        </div>

        <div class="position-section">
            <h2 class="section-title">📍 Posición Actual y Próxima Señal</h2>
            <div class="position-grid">
"""

        for symbol in ["QQQ", "SPY", "TQQQ", "ARKK", "DIA", "IWM", "USMV", "NVDA", "AVGO", "MU", "SMH", "SOXX", "QTUM"]:
            entry = self.positions_data.get(symbol, {})
            pos = entry.get("position", {})
            sig = entry.get("signal", {})

            has_position = pos.get("has_position", False)
            unrealized_pl = pos.get("unrealized_pl", 0)
            unrealized_class = "negative" if unrealized_pl < 0 else "positive"

            target_pct = sig.get("target_exposure_pct")
            executed_pct = sig.get("last_executed_target_pct")
            pending = sig.get("pending_rebalance", False)
            suspended = entry.get("suspended", False)

            if target_pct is None:
                badge_html = '<span class="badge badge-none">Sin datos de señal</span>'
            elif pending:
                badge_html = (
                    f'<span class="badge badge-pending">⏳ Pendiente: '
                    f'{executed_pct:.0f}% → {target_pct:.0f}%</span>'
                )
            else:
                badge_html = f'<span class="badge badge-ok">✅ Al día en {target_pct:.0f}%</span>'

            card_class = "position-card suspended" if suspended else "position-card"
            stamp_html = '<div class="stamp-suspended">Suspendido</div>' if suspended else ""
            html += f"""
                <div class="{card_class}">
                    {stamp_html}
                    <div class="symbol">{symbol}</div>
                    <div style="margin-bottom: 12px;">{badge_html}</div>
"""

            if has_position:
                html += f"""
                    <div class="position-row"><span>Cantidad</span><span>{pos.get('qty', 0):.4f}</span></div>
                    <div class="position-row"><span>Precio promedio</span><span>${pos.get('avg_entry_price', 0):,.2f}</span></div>
                    <div class="position-row"><span>Precio actual</span><span>${pos.get('current_price', 0):,.2f}</span></div>
                    <div class="position-row"><span>Valor de mercado</span><span>${pos.get('market_value', 0):,.2f}</span></div>
                    <div class="position-row"><span>P&L no realizado</span><span class="{unrealized_class}">${unrealized_pl:,.2f} ({pos.get('unrealized_plpc', 0):+.2f}%)</span></div>
"""
            else:
                html += """
                    <div class="position-row"><span>Posición</span><span>Sin posición abierta</span></div>
"""

            html += f"""
                    <div class="position-row"><span>Última señal</span><span>{sig.get('signal_date', 'N/A')}</span></div>
                    <div class="position-row"><span>Último target ejecutado</span><span>{f"{executed_pct:.0f}%" if executed_pct is not None else 'N/A'}</span></div>
                    <div class="position-row"><span>Última acción</span><span>{sig.get('last_action', 'N/A')}</span></div>
"""

            learning = self.analysis_progress_data.get(symbol)
            if learning:
                since = learning.get("trades_since_analysis", 0)
                target = learning.get("trades_target", 50)
                due = learning.get("analysis_due", False)
                fill_pct = min(100, round(since / target * 100)) if target else 0
                fill_class = "learning-fill due" if due else "learning-fill"
                due_label = " 🔔 toca análisis" if due else ""
                html += f"""
                    <div class="position-row"><span>Auto-aprendizaje</span><span>{since}/{target} operaciones{due_label}</span></div>
                    <div class="learning-bar"><div class="{fill_class}" style="width: {fill_pct}%;"></div></div>
"""

            html += """
                </div>
"""

        html += """
            </div>
        </div>

        <div class="performance-section">
            <h2 class="section-title">📈 Rendimiento por Símbolo</h2>
"""

        for symbol in ["QQQ", "SPY", "TQQQ", "ARKK", "DIA", "IWM", "USMV", "NVDA", "AVGO", "MU", "SMH", "SOXX", "QTUM"]:
            # Antes se saltaba el símbolo entero si no tenía NINGÚN fill
            # (perf vacío) -- eso lo hacía desaparecer del dashboard, no
            # solo mostrar "0 operaciones". Ahora siempre se muestra.
            perf = self.performance_data.get(symbol) or {}

            trades = perf.get("trades", [])
            total_trades = len(trades)

            open_position_note = ""
            if total_trades == 0:
                pos = self.positions_data.get(symbol, {}).get("position", {})
                if pos.get("has_position"):
                    unrealized = pos.get("unrealized_pl", 0)
                    unrealized_pct = pos.get("unrealized_plpc", 0)
                    unrealized_class = "positive" if unrealized > 0 else ("negative" if unrealized < 0 else "")
                    open_position_note = f"""
                <p style="color: #999; margin: -10px 0 15px 0; font-size: 0.9em;">
                    Sin operaciones CERRADAS todavía — tiene una posición abierta:
                    ${pos.get('market_value', 0):,.2f}
                    (<span class="{unrealized_class}">{unrealized_pct:+.2f}% / ${unrealized:,.2f} no realizado</span>)
                </p>"""

            html += f"""
            <div style="margin-bottom: 40px;">
                <h3 style="color: #00ff88; margin-bottom: 15px;">{symbol} - {total_trades} Operaciones Históricas</h3>{open_position_note}

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
                    <div class="metric-card">
                        <div class="metric-label">P&L Realizado</div>
                        <div class="metric-value {('negative' if perf.get('realized_pnl', 0) < 0 else '')}">
                            ${perf.get('realized_pnl', 0):,.2f}
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value">{perf.get('win_rate', 0):.1f}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">P&L Promedio</div>
                        <div class="metric-value">
                            ${perf.get('avg_pnl_per_trade', 0):,.2f}
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Operaciones Ganadoras</div>
                        <div class="metric-value positive">{perf.get('winning_trades', 0)}</div>
                    </div>
                </div>

                <div style="overflow-x: auto; background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 10px;">
                    <table style="width: 100%;">
                        <tr>
                            <th>Fecha</th>
                            <th>ID Orden</th>
                            <th>Precio Compra</th>
                            <th>Precio Venta</th>
                            <th>Cantidad</th>
                            <th>P&L</th>
                            <th>Ganancia %</th>
                        </tr>
"""

            for trade in trades:
                pnl = trade.get("pnl", 0)
                buy_price = trade.get("buy_price", 0)
                pnl_pct = ((trade.get("sell_price", 0) - buy_price) / buy_price * 100) if buy_price > 0 else 0
                pnl_class = "positive" if pnl > 0 else ("negative" if pnl < 0 else "")

                html += f"""
                        <tr>
                            <td>{trade.get('date', 'N/A')}</td>
                            <td>{trade.get('order_id', 'N/A')}</td>
                            <td>${buy_price:.2f}</td>
                            <td>${trade.get('sell_price', 0):.2f}</td>
                            <td>{trade.get('qty', 0):.4f}</td>
                            <td class="{pnl_class}">${pnl:,.2f}</td>
                            <td class="{pnl_class}">{pnl_pct:+.2f}%</td>
                        </tr>
"""

            html += """
                    </table>
                </div>
            </div>
"""

        # NYSE Scanner: símbolo variable (uno a la vez), no encaja en el
        # patrón de símbolo fijo del resto de la familia -- sección
        # propia en vez de forzarlo en los loops de arriba.
        ns = self.nyse_scanner_data
        if ns:
            status = ns.get("status", "flat")
            status_color = {"in_position": "#00ff88", "pending_entry": "#ffcc00", "flat": "#999"}.get(status, "#999")

            position_html = ""
            pos = ns.get("position")
            if pos:
                pl_class = "positive" if pos.get("unrealized_pl", 0) >= 0 else "negative"
                position_html = f"""
                <div class="metric-card">
                    <div class="metric-label">Valor de la posición</div>
                    <div class="metric-value">${pos.get('market_value', 0):,.2f}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">P&L no realizado</div>
                    <div class="metric-value {pl_class}">{pos.get('unrealized_plpc', 0):+.2f}% (${pos.get('unrealized_pl', 0):,.2f})</div>
                </div>"""

            html += f"""
        <div class="performance-section">
            <h2 class="section-title">🔎 NYSE Scanner</h2>
            <div style="margin-bottom: 20px;">
                <span style="color: {status_color}; font-weight: bold; font-size: 1.1em;">{ns.get('status_label', '')}</span>
                <p style="color: #999; margin-top: 8px; font-size: 0.9em;">
                    Última corrida: {ns.get('today_date', 'n/d')} — {ns.get('today_evaluated', 0)} tickers evaluados,
                    {ns.get('today_signals_count', 0)} señal(es) con score ≥ 80
                </p>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div class="metric-card">
                    <div class="metric-label">Operaciones Cerradas</div>
                    <div class="metric-value">{ns.get('total_trades', 0)}</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">{ns.get('win_rate', 0):.1f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">P&L Realizado</div>
                    <div class="metric-value {'negative' if ns.get('realized_pnl', 0) < 0 else ''}">${ns.get('realized_pnl', 0):,.2f}</div>
                </div>{position_html}
            </div>
"""

            trades = ns.get("trades", [])
            if trades:
                html += """
            <div style="overflow-x: auto; background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 10px;">
                <table style="width: 100%;">
                    <tr>
                        <th>Símbolo</th>
                        <th>Entrada</th>
                        <th>Salida</th>
                        <th>Precio Compra</th>
                        <th>Precio Venta</th>
                        <th>Motivo</th>
                        <th>P&L</th>
                        <th>Ganancia %</th>
                    </tr>
"""
                for t in trades:
                    pnl = t.get("pnl_usd", 0)
                    pnl_class = "positive" if pnl > 0 else ("negative" if pnl < 0 else "")
                    reason_label = {"stop": "Stop -8%", "target": "Target +20%", "horizonte": "Horizonte 15d"}.get(t.get("exit_reason"), t.get("exit_reason", ""))
                    html += f"""
                    <tr>
                        <td>{t.get('symbol', 'N/A')}</td>
                        <td>{t.get('entry_date', 'N/A')}</td>
                        <td>{t.get('exit_date', 'N/A')}</td>
                        <td>${safe_float_fmt(t.get('entry_price'))}</td>
                        <td>${safe_float_fmt(t.get('exit_price'))}</td>
                        <td>{reason_label}</td>
                        <td class="{pnl_class}">${pnl:,.2f}</td>
                        <td class="{pnl_class}">{t.get('pnl_pct', 0):+.2f}%</td>
                    </tr>
"""
                html += """
                </table>
            </div>
"""
            html += """
        </div>
"""

        html += """
        </div>

        <footer>
            <p>Trading Dashboard | Actualización automática diaria | Operaciones en Alpaca Paper Trading</p>
        </footer>
    </div>
</body>
</html>
"""

        return html

    def save_dashboard(self, filepath="index.html"):
        html = self.generate_html()
        with open(filepath, "w") as f:
            f.write(html)
        print(f"✅ Dashboard generado en {filepath}")


if __name__ == "__main__":
    generator = DashboardGenerator()
    generator.save_dashboard()
