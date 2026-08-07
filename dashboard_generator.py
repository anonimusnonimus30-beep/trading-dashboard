#!/usr/bin/env python3
"""
Generador de dashboard HTML con operaciones, P&L y asignación de capital.
"""

import json
from pathlib import Path


class DashboardGenerator:
    def __init__(
        self,
        performance_file="performance.json",
        allocation_file="capital_allocation.json",
        positions_file="positions.json",
    ):
        self.performance_file = performance_file
        self.allocation_file = allocation_file
        self.positions_file = positions_file
        self.performance_data = self._load_json(performance_file)
        self.allocation_data = self._load_json(allocation_file)
        self.positions_data = self._load_json(positions_file)

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
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 20px;
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
            <p class="last-update">Última actualización: {self.allocation_data.get("timestamp", "N/A")}</p>
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

        for symbol in ["QQQ", "QQQM", "TQQQ", "SPY"]:
            pct = allocation.get(symbol, 25)
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

        for symbol in ["QQQ", "QQQM", "TQQQ", "SPY"]:
            entry = self.positions_data.get(symbol, {})
            pos = entry.get("position", {})
            sig = entry.get("signal", {})

            has_position = pos.get("has_position", False)
            unrealized_pl = pos.get("unrealized_pl", 0)
            unrealized_class = "negative" if unrealized_pl < 0 else "positive"

            target_pct = sig.get("target_exposure_pct")
            executed_pct = sig.get("last_executed_target_pct")
            pending = sig.get("pending_rebalance", False)

            if target_pct is None:
                badge_html = '<span class="badge badge-none">Sin datos de señal</span>'
            elif pending:
                badge_html = (
                    f'<span class="badge badge-pending">⏳ Pendiente: '
                    f'{executed_pct:.0f}% → {target_pct:.0f}%</span>'
                )
            else:
                badge_html = f'<span class="badge badge-ok">✅ Al día en {target_pct:.0f}%</span>'

            html += f"""
                <div class="position-card">
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
                </div>
"""

        html += """
            </div>
        </div>

        <div class="performance-section">
            <h2 class="section-title">📈 Rendimiento por Símbolo</h2>
"""

        for symbol in ["QQQ", "QQQM", "TQQQ", "SPY"]:
            perf = self.performance_data.get(symbol, {})
            if not perf:
                continue

            trades = perf.get("trades", [])
            total_trades = len(trades)

            html += f"""
            <div style="margin-bottom: 40px;">
                <h3 style="color: #00ff88; margin-bottom: 15px;">{symbol} - {total_trades} Operaciones Históricas</h3>

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
