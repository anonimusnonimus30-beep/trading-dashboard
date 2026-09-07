#!/usr/bin/env python3
"""
Publica el indice Fear & Greed de CNN para que los bots lo muestren
junto al sentimiento de noticias.

Es SOLO INFORMATIVO: no mueve exposicion ni entra en ninguna decision
de trading. Se probo como senial (reconstruyendo sus componentes con 18
anios de historia, porque el endpoint de CNN solo entrega 1 anio movil)
y no valido: 0 de 8 ventanas de test le ganaron al buy&hold en retorno,
y en Sharpe fue cara o cruz. Lo unico consistente fue la reduccion de
drawdown (8/8), pero a un costo de retorno que no compensa.

Se consulta UNA sola vez desde aca y se publica, en vez de que lo pida
cada bot: son 13 bots x 8 corridas diarias contra un endpoint no oficial
que ya responde 418 a clientes que no parecen navegador. Un solo pedido
cada 15 minutos es mucho menos probable que termine bloqueado.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
SALIDA = Path("market_sentiment.json")

# CNN devuelve 418 sin estas cabeceras: el endpoint es el que usa su
# propia pagina, no una API publica documentada.
CABECERAS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://edition.cnn.com/",
    "Origin": "https://edition.cnn.com",
}

ETIQUETAS = [
    (25, "😱", "MIEDO EXTREMO"),
    (45, "😟", "MIEDO"),
    (55, "😐", "NEUTRAL"),
    (75, "🙂", "CODICIA"),
    (101, "🤑", "CODICIA EXTREMA"),
]


def etiquetar(score):
    for limite, emoji, texto in ETIQUETAS:
        if score < limite:
            return emoji, texto
    return "🤑", "CODICIA EXTREMA"


def obtener():
    r = requests.get(URL, headers=CABECERAS, timeout=20)
    r.raise_for_status()
    d = r.json()["fear_and_greed"]
    score = float(d["score"])
    emoji, texto = etiquetar(score)
    return {
        "score": round(score, 1),
        "etiqueta": texto,
        "emoji": emoji,
        "rating_cnn": d.get("rating"),
        "cierre_previo": round(float(d.get("previous_close", 0)), 1),
        "hace_una_semana": round(float(d.get("previous_1_week", 0)), 1),
        "hace_un_mes": round(float(d.get("previous_1_month", 0)), 1),
        "fuente": "CNN Fear & Greed Index",
        "solo_informativo": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def leer_publicado(archivo=SALIDA, max_edad_horas=6):
    """Lo usan los bots para mostrarlo en su mensaje. Devuelve None si
    el dato falta o esta viejo, y en ese caso el bot simplemente no lo
    muestra: al ser informativo, nunca debe frenar nada."""
    try:
        d = json.loads(Path(archivo).read_text())
        ts = datetime.fromisoformat(d["timestamp"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - ts > timedelta(hours=max_edad_horas):
            return None
        return d
    except Exception:
        return None


def como_texto(d):
    if not d:
        return ""
    flecha = "↑" if d["score"] > d["cierre_previo"] else ("↓" if d["score"] < d["cierre_previo"] else "→")
    return (f"{d['emoji']} Mercado (Fear & Greed): {d['score']:.0f}/100 — {d['etiqueta']}\n"
            f"   {flecha} previo {d['cierre_previo']:.0f} | semana {d['hace_una_semana']:.0f} | mes {d['hace_un_mes']:.0f}")


def main():
    try:
        datos = obtener()
    except Exception as e:
        print(f"⚠️ No se pudo consultar Fear & Greed ({e}). Se conserva el dato anterior.")
        return
    SALIDA.write_text(json.dumps(datos, indent=2, ensure_ascii=False))
    print(f"✅ {SALIDA} actualizado")
    print(como_texto(datos))


if __name__ == "__main__":
    main()
