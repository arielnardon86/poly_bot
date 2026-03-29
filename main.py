"""
Punto de entrada del bot de Polymarket.
En esta fase (Setup) solo verifica la conexión y muestra mercados activos.

Uso:
    python main.py
"""
import sys
from src.markets import get_active_markets, print_market_summary, get_best_prices
from config import settings


def check_connection():
    """Verifica que podemos conectar a la API sin autenticación."""
    print("Verificando conexión a Polymarket...")
    markets = get_active_markets(limit=5)
    if not markets:
        print("ERROR: No se pudo conectar a Polymarket. Verifica tu conexión a internet.")
        sys.exit(1)
    print(f"✓ Conexión exitosa. Mercados disponibles en este momento.")


def show_markets_overview():
    """Muestra los 15 mercados más activos."""
    print("\nObteniendo mercados activos...")
    markets = get_active_markets(limit=100)

    # Ordenar por volumen descendente
    markets_by_volume = sorted(markets, key=lambda m: m["volume"], reverse=True)

    print(f"Total de mercados activos encontrados: {len(markets)}")
    print("\nTop 15 mercados por volumen:")
    print_market_summary(markets_by_volume, top_n=15)


def show_price_check(market: dict):
    """Muestra precios detallados de un mercado específico."""
    print(f"\nDetalle de precios para: {market['question'][:60]}...")

    yes_prices = get_best_prices(market["yes_token_id"])
    no_prices = get_best_prices(market["no_token_id"]) if market["no_token_id"] else {}

    print(f"  YES → Mejor bid: {yes_prices.get('best_bid', 'N/A')} | Mejor ask: {yes_prices.get('best_ask', 'N/A')} | Spread: {yes_prices.get('spread', 'N/A')}")
    if no_prices:
        print(f"  NO  → Mejor bid: {no_prices.get('best_bid', 'N/A')} | Mejor ask: {no_prices.get('best_ask', 'N/A')} | Spread: {no_prices.get('spread', 'N/A')}")

    if yes_prices.get("best_ask") and no_prices.get("best_ask"):
        combined = yes_prices["best_ask"] + no_prices["best_ask"]
        gap = round(1.0 - combined, 4)
        print(f"\n  Suma de mejores asks: {combined:.4f} | Potencial arbitraje: {gap:.4f} USDC por par")
        if gap > 0:
            print("  *** POSIBLE OPORTUNIDAD DE ARBITRAJE ***")


def main():
    print("=" * 60)
    print("  POLYMARKET BOT — FASE D: Setup y Verificación")
    print(f"  Modo: {'DRY RUN (sin órdenes reales)' if settings.DRY_RUN else 'PRODUCCIÓN'}")
    print("=" * 60)

    # 1. Verificar conexión
    check_connection()

    # 2. Mostrar panorama de mercados
    show_markets_overview()

    # 3. Mostrar precios detallados del mercado más activo como demo
    print("\nCargando detalle del mercado más activo como ejemplo...")
    markets = get_active_markets(limit=100)
    if markets:
        top_market = sorted(markets, key=lambda m: m["volume"], reverse=True)[0]
        show_price_check(top_market)

    print("\n✓ Setup completado. El bot está listo para la Fase A (Arbitraje).")
    print("\nPróximos pasos:")
    print("  1. Copia .env.example → .env y agrega tu PRIVATE_KEY y WALLET_ADDRESS")
    print("  2. Ejecuta: python scripts/setup_credentials.py")
    print("  3. Cuando tengas las credenciales, implementaremos el bot de arbitraje")


if __name__ == "__main__":
    main()
