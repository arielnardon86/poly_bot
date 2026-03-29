"""
Scanner de oportunidades de arbitraje interno en Polymarket.

Estrategia: cuando YES_ask + NO_ask < $1.00, comprar ambos tokens
garantiza una ganancia fija al resolverse el mercado.

Ejemplo:
  YES a $0.44 + NO a $0.51 = $0.95 total
  Al resolverse, uno valdrá $1.00 → ganancia de $0.05 por par (5.26% ROI)
"""
import requests
import time
import json
from dataclasses import dataclass
from typing import Optional
from config import settings


@dataclass
class ArbOpportunity:
    market_id: str
    question: str
    yes_token_id: str
    no_token_id: str
    yes_ask: float          # Precio al que compramos YES
    no_ask: float           # Precio al que compramos NO
    combined_cost: float    # yes_ask + no_ask
    profit_per_share: float # 1.00 - combined_cost
    roi: float              # profit / combined_cost
    yes_liquidity: float    # Cuántas acciones YES disponibles a ese precio
    no_liquidity: float     # Cuántas acciones NO disponibles a ese precio
    max_shares: float       # Limitado por la liquidez más baja y el capital máx
    expected_profit: float  # profit_per_share × max_shares
    neg_risk: bool

    def __str__(self):
        return (
            f"\n{'─'*60}\n"
            f"  {self.question[:55]}\n"
            f"  YES ask: ${self.yes_ask:.3f} | NO ask: ${self.no_ask:.3f}\n"
            f"  Costo combinado: ${self.combined_cost:.4f} | Ganancia: ${self.profit_per_share:.4f}/acc\n"
            f"  ROI: {self.roi*100:.2f}% | Acciones posibles: {self.max_shares:.1f}\n"
            f"  Ganancia esperada: ${self.expected_profit:.2f}\n"
            f"{'─'*60}"
        )


def _get_best_ask(token_id: str) -> tuple[float, float]:
    """
    Devuelve (mejor_ask, tamaño_disponible) para un token.
    Usa la CLOB API directamente.
    """
    try:
        resp = requests.get(
            f"{settings.CLOB_URL}/book",
            params={"token_id": token_id},
            timeout=8,
        )
        resp.raise_for_status()
        book = resp.json()
        asks = book.get("asks", [])
        if not asks:
            return 1.0, 0.0
        # El mejor ask es el de precio más bajo
        best = min(asks, key=lambda x: float(x["price"]))
        return float(best["price"]), float(best["size"])
    except Exception:
        return 1.0, 0.0


def _get_markets_batch(limit: int = 200) -> list[dict]:
    """Obtiene mercados activos de la Gamma API."""
    try:
        resp = requests.get(
            f"{settings.GAMMA_URL}/markets",
            params={"closed": "false", "limit": limit, "active": "true"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [ERROR] No se pudo obtener mercados: {e}")
        return []


def _parse_prices(raw) -> tuple[float, float]:
    """Parsea outcomePrices del API a (yes_price, no_price)."""
    try:
        if isinstance(raw, str):
            prices = json.loads(raw)
        else:
            prices = raw
        return float(prices[0]), float(prices[1])
    except Exception:
        return 0.5, 0.5


def scan_opportunities(verbose: bool = True) -> list[ArbOpportunity]:
    """
    Escanea todos los mercados activos buscando oportunidades de arbitraje.

    Proceso en dos pasos:
    1. Pre-filtro rápido con precios de Gamma API (sin rate limit)
    2. Verificación detallada con order book real para candidatos

    Returns lista de oportunidades ordenadas por ROI descendente.
    """
    if verbose:
        print("  Obteniendo mercados activos...")

    markets = _get_markets_batch(limit=200)
    if not markets:
        return []

    if verbose:
        print(f"  {len(markets)} mercados encontrados. Aplicando pre-filtro...")

    # Paso 1: pre-filtro con precios de Gamma
    # Usamos un umbral generoso (< 0.98) para no perder candidatos reales
    candidates = []
    for m in markets:
        token_ids = m.get("clobTokenIds") or []
        if len(token_ids) < 2:
            continue
        if m.get("negRisk", False):
            continue  # Mercados multi-outcome requieren lógica distinta

        yes_price, no_price = _parse_prices(m.get("outcomePrices", "[0.5,0.5]"))
        price_sum = yes_price + no_price

        if price_sum < 0.98:  # Candidato potencial
            candidates.append({
                "id": m.get("id", ""),
                "question": m.get("question", ""),
                "yes_token_id": token_ids[0],
                "no_token_id": token_ids[1],
                "gamma_sum": price_sum,
                "neg_risk": m.get("negRisk", False),
            })

    if verbose:
        print(f"  {len(candidates)} candidatos tras pre-filtro. Verificando order books...")

    # Paso 2: verificar con order book real
    opportunities = []
    for i, c in enumerate(candidates):
        if verbose and len(candidates) > 10:
            print(f"  Verificando {i+1}/{len(candidates)}: {c['question'][:40]}...", end="\r")

        yes_ask, yes_size = _get_best_ask(c["yes_token_id"])
        no_ask, no_size = _get_best_ask(c["no_token_id"])

        combined_cost = yes_ask + no_ask
        profit_per_share = 1.0 - combined_cost

        if profit_per_share <= 0:
            continue

        roi = profit_per_share / combined_cost

        if roi < settings.MIN_ROI:
            continue

        # Calcular cuántas acciones podemos comprar
        # Limitado por: liquidez disponible en ambos lados Y capital máximo
        max_by_liquidity = min(yes_size, no_size)
        max_by_capital = settings.MAX_POSITION_SIZE / combined_cost
        max_shares = min(max_by_liquidity, max_by_capital)

        if max_shares < 1.0:
            continue  # Sin liquidez suficiente

        expected_profit = profit_per_share * max_shares

        opportunities.append(ArbOpportunity(
            market_id=c["id"],
            question=c["question"],
            yes_token_id=c["yes_token_id"],
            no_token_id=c["no_token_id"],
            yes_ask=yes_ask,
            no_ask=no_ask,
            combined_cost=combined_cost,
            profit_per_share=profit_per_share,
            roi=roi,
            yes_liquidity=yes_size,
            no_liquidity=no_size,
            max_shares=max_shares,
            expected_profit=expected_profit,
            neg_risk=c["neg_risk"],
        ))

        # Pausa breve para no saturar el rate limit
        time.sleep(0.1)

    if verbose:
        print()  # Nueva línea tras el carriage return

    # Ordenar por ROI descendente
    opportunities.sort(key=lambda o: o.roi, reverse=True)
    return opportunities
