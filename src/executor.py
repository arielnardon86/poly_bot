"""
Ejecutor de trades de arbitraje.

Para cada oportunidad detectada:
1. Compra YES al precio ask
2. Compra NO al precio ask
3. Si alguna pierna falla, cancela la otra (gestión de riesgo)
"""
import time
import math
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY

from src.arbitrage import ArbOpportunity
from config import settings


def _round_to_tick(price: float, tick: float = 0.01) -> float:
    """Redondea un precio al tick size más cercano."""
    return round(round(price / tick) * tick, 6)


def _get_tick_size(client: ClobClient, token_id: str) -> float:
    """Obtiene el tick size de un token."""
    try:
        resp = client.get_tick_size(token_id)
        return float(resp) if resp else 0.01
    except Exception:
        return 0.01


def execute_arbitrage(
    client: ClobClient,
    opportunity: ArbOpportunity,
    shares: Optional[float] = None,
) -> dict:
    """
    Ejecuta el arbitraje: compra YES y NO simultáneamente.

    Args:
        client:      Cliente autenticado de Polymarket.
        opportunity: Oportunidad detectada por el scanner.
        shares:      Cantidad de acciones a comprar. Si es None, usa el máximo seguro.

    Returns:
        dict con resultado: {success, yes_order, no_order, cost, expected_profit, error}
    """
    if shares is None:
        shares = math.floor(opportunity.max_shares)  # Solo números enteros

    if shares < 1:
        return {"success": False, "error": "Cantidad de acciones insuficiente (< 1)"}

    cost_total = shares * opportunity.combined_cost
    expected_profit = shares * opportunity.profit_per_share

    print(f"\n  Ejecutando arbitraje:")
    print(f"  Acciones: {shares} | Costo: ${cost_total:.2f} | Ganancia esperada: ${expected_profit:.2f}")

    # --- DRY RUN ---
    if settings.DRY_RUN:
        print(f"  [DRY RUN] Comprando {shares} YES @ ${opportunity.yes_ask:.3f}")
        print(f"  [DRY RUN] Comprando {shares} NO  @ ${opportunity.no_ask:.3f}")
        return {
            "success": True,
            "dry_run": True,
            "shares": shares,
            "cost_total": cost_total,
            "expected_profit": expected_profit,
            "yes_order": {"simulated": True, "price": opportunity.yes_ask, "size": shares},
            "no_order": {"simulated": True, "price": opportunity.no_ask, "size": shares},
        }

    # --- PRODUCCIÓN ---
    yes_tick = _get_tick_size(client, opportunity.yes_token_id)
    no_tick = _get_tick_size(client, opportunity.no_token_id)

    yes_price = _round_to_tick(opportunity.yes_ask, yes_tick)
    no_price = _round_to_tick(opportunity.no_ask, no_tick)

    yes_order_id = None
    no_order_id = None

    try:
        # Pierna 1: comprar YES
        print(f"  Comprando {shares} YES @ ${yes_price:.3f}...")
        yes_args = OrderArgs(
            token_id=opportunity.yes_token_id,
            price=yes_price,
            size=float(shares),
            side=BUY,
        )
        yes_signed = client.create_order(yes_args)
        yes_resp = client.post_order(yes_signed, OrderType.GTC)
        yes_order_id = yes_resp.get("orderID") or yes_resp.get("id")
        print(f"  ✓ YES order: {yes_order_id}")

        # Pequeña pausa para no saturar el API
        time.sleep(0.3)

        # Pierna 2: comprar NO
        print(f"  Comprando {shares} NO  @ ${no_price:.3f}...")
        no_args = OrderArgs(
            token_id=opportunity.no_token_id,
            price=no_price,
            size=float(shares),
            side=BUY,
        )
        no_signed = client.create_order(no_args)
        no_resp = client.post_order(no_signed, OrderType.GTC)
        no_order_id = no_resp.get("orderID") or no_resp.get("id")
        print(f"  ✓ NO order:  {no_order_id}")

        return {
            "success": True,
            "shares": shares,
            "cost_total": cost_total,
            "expected_profit": expected_profit,
            "yes_order": yes_resp,
            "no_order": no_resp,
        }

    except Exception as e:
        error_msg = str(e)
        print(f"  [ERROR] Fallo en ejecución: {error_msg}")

        # Gestión de riesgo: si YES se compró pero NO falló, cancela YES
        if yes_order_id and not no_order_id:
            print(f"  Cancelando orden YES {yes_order_id} para evitar exposición...")
            try:
                client.cancel(yes_order_id)
                print(f"  ✓ Orden YES cancelada")
            except Exception as cancel_err:
                print(f"  [ALERTA] No se pudo cancelar YES: {cancel_err}")

        return {
            "success": False,
            "error": error_msg,
            "yes_order_id": yes_order_id,
        }


