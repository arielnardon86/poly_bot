"""
Ejecutor de trades AMM para arbitraje negRisk.

Para cada oportunidad: compra YES de TODOS los outcomes del evento.
Exactamente uno va a valer $1.00 al resolverse — los demás $0.00.
La ganancia = $1.00 - costo_total.
"""
import time
import math
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

from src.arbitrage import NegRiskOpportunity
from config import settings


def execute_negrisk_arb(
    client: ClobClient,
    opportunity: NegRiskOpportunity,
    shares: Optional[float] = None,
) -> dict:
    """
    Ejecuta el arbitraje negRisk: compra YES de todos los outcomes.

    Args:
        client:      Cliente autenticado.
        opportunity: Oportunidad detectada por el scanner.
        shares:      Acciones por outcome. None = usa el máximo seguro.

    Returns:
        dict con resultado de la operación.
    """
    if shares is None:
        shares = math.floor(opportunity.max_shares)

    if shares < 1:
        return {"success": False, "error": "shares < 1"}

    cost_total = shares * opportunity.total_cost
    expected_profit = shares * opportunity.profit_per_dollar

    print(f"\n  Ejecutando arbitraje negRisk:")
    print(f"  Evento: {opportunity.event_title[:55]}")
    print(f"  {len(opportunity.outcomes)} outcomes × {shares} acciones")
    print(f"  Costo total: ${cost_total:.2f} | Ganancia esperada: ${expected_profit:.2f}")

    # --- DRY RUN ---
    if settings.DRY_RUN:
        for o in opportunity.outcomes:
            print(f"  [DRY RUN] BUY {shares} YES @ ${o['yes_price']:.3f}  {o['question'][:45]}")
        return {
            "success": True,
            "dry_run": True,
            "shares": shares,
            "cost_total": cost_total,
            "expected_profit": expected_profit,
            "orders_placed": len(opportunity.outcomes),
        }

    # --- PRODUCCIÓN ---
    placed = []
    failed = []

    for i, outcome in enumerate(opportunity.outcomes):
        token_id = outcome["token_id"]
        amount = shares * outcome["yes_price"]  # USDC a gastar en este outcome

        if amount < 1.0:
            amount = 1.0  # Mínimo de Polymarket

        print(f"  [{i+1}/{len(opportunity.outcomes)}] Comprando ${amount:.2f} en '{outcome['question'][:40]}'...")

        try:
            mo = MarketOrderArgs(
                token_id=token_id,
                amount=round(amount, 2),
                side=BUY,
            )
            signed = client.create_market_order(mo)
            resp = client.post_order(signed, OrderType.FOK)

            order_id = resp.get("orderID") or resp.get("id") or "ok"
            placed.append({"outcome": outcome["question"][:40], "order_id": order_id, "amount": amount})
            print(f"    ✓ {order_id}")

        except Exception as e:
            failed.append({"outcome": outcome["question"][:40], "error": str(e)})
            print(f"    ✗ Error: {e}")

        time.sleep(0.3)

    success = len(placed) == len(opportunity.outcomes)

    if not success and placed:
        print(f"\n  [ALERTA] Solo se ejecutaron {len(placed)}/{len(opportunity.outcomes)} outcomes.")
        print(f"  Posición parcial — revisá manualmente en Polymarket.")

    return {
        "success": success,
        "partial": len(placed) > 0 and not success,
        "shares": shares,
        "cost_total": cost_total,
        "expected_profit": expected_profit,
        "orders_placed": len(placed),
        "orders_failed": len(failed),
        "placed": placed,
        "failed": failed,
    }
