"""
Módulo para descubrir y consultar mercados de Polymarket.
Usa la Gamma API (sin autenticación) y la CLOB API para precios.
"""
import requests
from typing import Optional
from config import settings


def get_active_markets(limit: int = 50, offset: int = 0) -> list[dict]:
    """
    Devuelve mercados activos desde la Gamma API.

    Returns lista de dicts con campos relevantes ya procesados.
    """
    try:
        resp = requests.get(
            f"{settings.GAMMA_URL}/markets",
            params={"closed": "false", "limit": limit, "offset": offset},
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()
    except requests.RequestException as e:
        print(f"Error consultando Gamma API: {e}")
        return []

    result = []
    for m in markets:
        token_ids = m.get("clobTokenIds") or []
        if not token_ids or len(token_ids) < 2:
            continue  # Saltamos mercados sin tokens CLOB

        try:
            prices_raw = m.get("outcomePrices", "[0,0]")
            if isinstance(prices_raw, str):
                import json
                prices = json.loads(prices_raw)
            else:
                prices = prices_raw
            yes_price = float(prices[0]) if prices else 0.0
            no_price = float(prices[1]) if len(prices) > 1 else 0.0
        except (ValueError, IndexError):
            yes_price, no_price = 0.0, 0.0

        result.append({
            "id": m.get("id"),
            "question": m.get("question", "Sin descripción"),
            "yes_token_id": token_ids[0],
            "no_token_id": token_ids[1] if len(token_ids) > 1 else None,
            "yes_price": yes_price,
            "no_price": no_price,
            "price_sum": round(yes_price + no_price, 4),
            "volume": float(m.get("volume", 0)),
            "liquidity": float(m.get("liquidity", 0)),
            "neg_risk": m.get("negRisk", False),
            "end_date": m.get("endDate"),
        })

    return result


def get_order_book(token_id: str) -> dict:
    """
    Obtiene el order book de un token específico.

    Returns dict con 'bids' y 'asks', cada uno lista de {price, size}.
    """
    try:
        resp = requests.get(
            f"{settings.CLOB_URL}/book",
            params={"token_id": token_id},
            timeout=10,
        )
        resp.raise_for_status()
        book = resp.json()
        return {
            "bids": [{"price": float(b["price"]), "size": float(b["size"])} for b in book.get("bids", [])],
            "asks": [{"price": float(a["price"]), "size": float(a["size"])} for a in book.get("asks", [])],
        }
    except requests.RequestException as e:
        return {"error": str(e), "bids": [], "asks": []}


def get_best_prices(token_id: str) -> dict:
    """Devuelve el mejor bid y ask para un token."""
    book = get_order_book(token_id)
    best_bid = max((b["price"] for b in book["bids"]), default=0.0)
    best_ask = min((a["price"] for a in book["asks"]), default=1.0)
    return {"best_bid": best_bid, "best_ask": best_ask, "spread": round(best_ask - best_bid, 4)}


def get_tick_size(token_id: str) -> float:
    """Devuelve el tick size (incremento mínimo de precio) de un mercado."""
    try:
        resp = requests.get(
            f"{settings.CLOB_URL}/tick-size",
            params={"token_id": token_id},
            timeout=10,
        )
        resp.raise_for_status()
        return float(resp.json().get("minimum_tick_size", 0.01))
    except Exception:
        return 0.01  # Valor por defecto


def search_markets(keyword: str, limit: int = 20) -> list[dict]:
    """Busca mercados que contengan una palabra clave en la pregunta."""
    markets = get_active_markets(limit=200)
    keyword_lower = keyword.lower()
    return [m for m in markets if keyword_lower in m["question"].lower()][:limit]


def print_market_summary(markets: list[dict], top_n: int = 10):
    """Imprime un resumen de mercados en consola."""
    print(f"\n{'='*70}")
    print(f"{'PREGUNTA':<45} {'YES':>6} {'NO':>6} {'SUMA':>6} {'VOL':>8}")
    print(f"{'='*70}")
    for m in markets[:top_n]:
        question = m["question"][:44]
        print(
            f"{question:<45} "
            f"{m['yes_price']:>6.3f} "
            f"{m['no_price']:>6.3f} "
            f"{m['price_sum']:>6.3f} "
            f"${m['volume']:>7,.0f}"
        )
    print(f"{'='*70}\n")
