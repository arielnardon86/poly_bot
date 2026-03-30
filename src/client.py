"""
Cliente base para Polymarket.
Gestiona la conexión autenticada al CLOB y expone métodos de lectura/escritura.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from config import settings


def build_client(authenticated: bool = False) -> ClobClient:
    """
    Crea y devuelve un cliente CLOB.

    Args:
        authenticated: Si True, usa la private key para operar.
                       Si False, solo lectura (no requiere credenciales).
    """
    if not authenticated:
        return ClobClient(settings.CLOB_URL)

    settings.validate_config()
    client = ClobClient(
        settings.CLOB_URL,
        key=settings.PRIVATE_KEY,
        chain_id=settings.CHAIN_ID,
        signature_type=2,       # Browser proxy (MetaMask via Polymarket web)
        funder=settings.WALLET_ADDRESS,
    )

    # Si ya tenemos API keys en .env, las usamos directamente
    if settings.POLY_API_KEY and settings.POLY_API_SECRET and settings.POLY_API_PASSPHRASE:
        from py_clob_client.clob_types import ApiCreds
        client.set_api_creds(ApiCreds(
            api_key=settings.POLY_API_KEY,
            api_secret=settings.POLY_API_SECRET,
            api_passphrase=settings.POLY_API_PASSPHRASE,
        ))
    else:
        print("No se encontraron API credentials en .env")
        print("Ejecuta: python scripts/setup_credentials.py")

    return client


def get_balance(client: ClobClient) -> dict:
    """Devuelve el balance de USDC disponible para trading."""
    try:
        balance = client.get_balance()
        return {"usdc": float(balance)}
    except Exception as e:
        return {"error": str(e)}


def place_limit_order(
    client: ClobClient,
    token_id: str,
    price: float,
    size: float,
    side: str = "BUY",
) -> dict:
    """
    Coloca una orden límite.

    Args:
        token_id: ID del token (YES o NO) obtenido de la Gamma API.
        price:    Precio entre 0.01 y 0.99 (probabilidad implícita).
        size:     Cantidad de acciones a comprar/vender.
        side:     "BUY" o "SELL".

    Returns:
        Respuesta del exchange o error.
    """
    order_side = BUY if side.upper() == "BUY" else SELL

    if settings.DRY_RUN:
        print(f"[DRY RUN] Orden límite {side} | token={token_id[:12]}... | precio={price} | size={size}")
        return {"dry_run": True, "side": side, "price": price, "size": size}

    try:
        order = OrderArgs(token_id=token_id, price=price, size=size, side=order_side)
        signed = client.create_order(order)
        response = client.post_order(signed, OrderType.GTC)
        return response
    except Exception as e:
        return {"error": str(e)}


def place_market_order(
    client: ClobClient,
    token_id: str,
    amount_usdc: float,
    side: str = "BUY",
) -> dict:
    """
    Coloca una orden de mercado gastando `amount_usdc` dólares.

    Args:
        token_id:     ID del token objetivo.
        amount_usdc:  Cuántos USDC gastar.
        side:         "BUY" o "SELL".
    """
    order_side = BUY if side.upper() == "BUY" else SELL

    if settings.DRY_RUN:
        print(f"[DRY RUN] Orden mercado {side} | token={token_id[:12]}... | monto=${amount_usdc}")
        return {"dry_run": True, "side": side, "amount_usdc": amount_usdc}

    try:
        mo = MarketOrderArgs(token_id=token_id, amount=amount_usdc, side=order_side)
        signed = client.create_market_order(mo)
        response = client.post_order(signed, OrderType.FOK)
        return response
    except Exception as e:
        return {"error": str(e)}
