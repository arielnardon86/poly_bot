"""
Scanner de oportunidades de arbitraje en Polymarket — modelo AMM.

Estrategia negRisk: en eventos con múltiples outcomes mutuamente
excluyentes (ej: "¿Quién gana el torneo?"), si la suma de los precios
YES de todos los outcomes < $1.00, compramos todos.
Al resolverse, exactamente uno vale $1.00.

Ejemplo (NHL 2026):
  32 equipos, precio promedio $0.031 cada uno
  Suma total: 32 × $0.031 = $0.992 < $1.00
  Ganancia garantizada: $1.00 - $0.992 = $0.008 por dólar invertido (0.8% ROI)
"""
import requests
import json
import time
from dataclasses import dataclass, field
from config import settings

GAMMA_URL = settings.GAMMA_URL


@dataclass
class NegRiskOpportunity:
    event_id: str
    event_title: str
    outcomes: list[dict]        # [{question, token_id, yes_price, mid_price}]
    total_cost: float           # suma de todos los yes_price
    profit_per_dollar: float    # 1.0 - total_cost
    roi: float                  # profit / total_cost
    max_shares: float           # cuántas acciones de cada outcome comprar
    expected_profit: float

    def __str__(self):
        return (
            f"\n{'─'*65}\n"
            f"  {self.event_title[:60]}\n"
            f"  Outcomes: {len(self.outcomes)} | Costo total: ${self.total_cost:.4f}\n"
            f"  Ganancia: ${self.profit_per_dollar:.4f}/acc | ROI: {self.roi*100:.2f}%\n"
            f"  Acciones: {self.max_shares:.1f} | Ganancia esperada: ${self.expected_profit:.2f}\n"
            f"{'─'*65}"
        )


def _get_events(limit: int = 100) -> list[dict]:
    """Obtiene eventos activos de la Gamma API con sus mercados."""
    all_events = []
    offset = 0
    page = limit if limit <= 100 else 100

    while len(all_events) < limit:
        try:
            resp = requests.get(
                f"{GAMMA_URL}/events",
                params={"closed": "false", "active": "true", "limit": page, "offset": offset},
                timeout=10,
            )
            resp.raise_for_status()
            batch = resp.json()
        except Exception as e:
            print(f"  [ERROR] No se pudo obtener eventos: {e}")
            break

        if not batch:
            break

        all_events.extend(batch)
        offset += page
        if len(batch) < page:
            break

    return all_events[:limit]


def _parse_prices(raw) -> list[float]:
    """Parsea outcomePrices a lista de floats."""
    try:
        if isinstance(raw, str):
            return [float(p) for p in json.loads(raw)]
        return [float(p) for p in raw]
    except Exception:
        return []


def _is_mutually_exclusive(markets: list[dict]) -> bool:
    """
    Determina si los outcomes son mutuamente excluyentes.
    Requiere que al menos algunos mercados sean negRisk=True.
    """
    neg_risk_markets = [m for m in markets if m.get("negRisk", False)]
    return len(neg_risk_markets) >= 2


def scan_opportunities(verbose: bool = True) -> list[NegRiskOpportunity]:
    """
    Escanea eventos activos buscando oportunidades de arbitraje negRisk.

    Busca eventos donde:
    1. Tienen múltiples outcomes mutuamente excluyentes
    2. La suma de precios YES < $1.00 (después del margen mínimo)
    """
    if verbose:
        print("  Obteniendo eventos activos...")

    events = _get_events(limit=200)
    if not events:
        return []

    if verbose:
        print(f"  {len(events)} eventos. Filtrando mutuamente excluyentes...")

    opportunities = []

    for ev in events:
        markets = ev.get("markets", [])
        if len(markets) < 2:
            continue

        # Solo eventos donde los outcomes son mutuamente excluyentes
        if not _is_mutually_exclusive(markets):
            continue

        # Calcular costo total de comprar YES en todos los outcomes
        outcomes = []
        total_cost = 0.0
        MIN_MEANINGFUL_PRICE = 0.005  # Ignorar outcomes con prob. < 0.5% (slots vacíos)

        for m in markets:
            # Solo incluir mercados negRisk verdaderos (mutuamente excluyentes garantizados)
            if not m.get("negRisk", False):
                continue
            prices = _parse_prices(m.get("outcomePrices", "[]"))
            yes_price = prices[0] if prices else 0.0

            # Saltar slots vacíos/placeholder que el mercado considera imposibles
            if yes_price < MIN_MEANINGFUL_PRICE:
                continue

            raw_ids = m.get("clobTokenIds") or []
            if isinstance(raw_ids, str):
                try:
                    raw_ids = json.loads(raw_ids)
                except Exception:
                    raw_ids = []
            yes_token = raw_ids[0] if raw_ids else None

            if not yes_token:
                continue

            outcomes.append({
                "question": m.get("question", ""),
                "token_id": yes_token,
                "yes_price": yes_price,
                "market_id": m.get("id", ""),
            })
            total_cost += yes_price

        if len(outcomes) < 2:
            continue

        profit_per_dollar = 1.0 - total_cost
        if profit_per_dollar <= 0:
            continue

        roi = profit_per_dollar / total_cost
        if roi < settings.MIN_ROI:
            continue

        # Cuántas acciones comprar: limitado por capital / (precio × outcomes)
        cost_per_set = total_cost
        max_shares = min(
            settings.MAX_POSITION_SIZE / cost_per_set,
            50.0  # Cap de seguridad
        )
        if max_shares < 1.0:
            continue

        expected_profit = profit_per_dollar * max_shares

        opportunities.append(NegRiskOpportunity(
            event_id=str(ev.get("id", "")),
            event_title=ev.get("title", ev.get("slug", "Sin título")),
            outcomes=outcomes,
            total_cost=round(total_cost, 4),
            profit_per_dollar=round(profit_per_dollar, 4),
            roi=roi,
            max_shares=round(max_shares, 2),
            expected_profit=round(expected_profit, 2),
        ))

    if verbose:
        print(f"  {len(opportunities)} oportunidades encontradas.")

    opportunities.sort(key=lambda o: o.roi, reverse=True)
    return opportunities
