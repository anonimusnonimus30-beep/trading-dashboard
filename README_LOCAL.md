# 📊 Dashboard Trading Local

## Configuración Inicial (UNA SOLA VEZ)

```bash
bash /home/juanitotrader/trading-dashboard/setup_once.sh
```

Te pedirá:
- API Key Cuenta 1 (QQQ, QQQM, TQQQ)
- API Secret Cuenta 1
- API Key Cuenta 2 (SPY)
- API Secret Cuenta 2

Las credenciales se guardan en: `~/.trading_dashboard_creds`

---

## Uso Diario

### Para actualizar datos:
```bash
bash /home/juanitotrader/trading-dashboard/update.sh
```

### Para ver el dashboard:
```bash
bash /home/juanitotrader/trading-dashboard/view.sh
```

Se abrirá automáticamente en: `http://localhost:8000`

---

## Flujo Completo

```bash
# Terminal 1: Ver dashboard (se queda corriendo)
bash /home/juanitotrader/trading-dashboard/view.sh

# Terminal 2: Actualizar datos (cuando quieras)
bash /home/juanitotrader/trading-dashboard/update.sh

# El navegador mostrará los datos nuevos AUTOMÁTICAMENTE
```

---

## Detalles

- Las credenciales se guardan **UNA SOLA VEZ**
- Después no necesitas ingresarlas nunca más
- Los datos se actualizan cada vez que ejecutas `update.sh`
- El navegador siempre muestra datos frescos (sin caché)

