"""
Bot de Arbitraje negRisk — Polymarket AMM
==========================================
Escanea eventos buscando grupos de outcomes mutuamente excluyentes
donde la suma de precios YES < $1.00, y compra todos los outcomes.

Uso:
    python bot.py              # Loop cada 5 minutos
    python bot.py --once       # Un solo escaneo
    python bot.py --interval 2 # Cada 2 minutos
"""
import sys
import time
import argparse
from datetime import datetime

from src.arbitrage import scan_opportunities
from src.executor import execute_negrisk_arb
from src.portfolio import record_trade, print_summary
from src.client import build_client
from config import settings


def print_header():
    mode = "DRY RUN (simulación)" if settings.DRY_RUN else "PRODUCCIÓN — órdenes reales"
    print(f"""
╔══════════════════════════════════════════════════════╗
║      POLYMARKET NEGRISK ARBITRAGE BOT               ║
║  Modo: {mode:<44}║
║  Capital máx/op: ${settings.MAX_POSITION_SIZE:<5} | ROI mínimo: {settings.MIN_ROI*100:.1f}%          ║
╚══════════════════════════════════════════════════════╝""")


def run_scan_cycle(client, cycle_num: int) -> int:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] Ciclo #{cycle_num} — Escaneando eventos...")

    opportunities = scan_opportunities(verbose=True)

    if not opportunities:
        print(f"  Sin oportunidades (ROI mín {settings.MIN_ROI*100:.1f}%) en este momento.")
        return 0

    print(f"\n  ✓ {len(opportunities)} oportunidad(es):\n")
    for opp in opportunities:
        print(opp)

    executed = 0
    for opp in opportunities[:3]:
        print(f"\n  → Ejecutando: {opp.event_title[:50]}...")
        result = execute_negrisk_arb(client, opp)

        if result["success"] or result.get("partial"):
            # Adaptar para el portfolio tracker
            class OppAdapter:
                def __init__(self, o, r):
                    self.market_id = o.event_id
                    self.question = o.event_title
                    self.yes_token_id = o.outcomes[0]["token_id"] if o.outcomes else ""
                    self.no_token_id = o.outcomes[1]["token_id"] if len(o.outcomes) > 1 else ""
                    self.yes_ask = o.total_cost
                    self.no_ask = 0.0
                    self.roi = o.roi

            trade_id = record_trade(OppAdapter(opp, result), result)
            print(f"  ✓ [{trade_id}] Invertido: ${result['cost_total']:.2f} | Esperado: +${result['expected_profit']:.2f}")
            executed += 1
        else:
            print(f"  ✗ Fallido: {result.get('error', 'desconocido')}")

        time.sleep(1)

    return executed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()

    print_header()

    if not settings.DRY_RUN:
        print("\n⚠️  PRODUCCIÓN ACTIVO. Ctrl+C en 5 segundos para cancelar...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("Cancelado.")
            sys.exit(0)

    try:
        client = build_client(authenticated=not settings.DRY_RUN)
    except ValueError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    print_summary()

    cycle = 1
    total_executed = 0

    try:
        while True:
            executed = run_scan_cycle(client, cycle)
            total_executed += executed
            cycle += 1

            if args.once:
                break

            print(f"\n  Próximo escaneo en {args.interval} min. Ctrl+C para detener.")
            print(f"  Operaciones en esta sesión: {total_executed}")
            time.sleep(args.interval * 60)

    except KeyboardInterrupt:
        print(f"\n\nBot detenido.")

    print_summary()
    print(f"Sesión finalizada. Operaciones: {total_executed}")


if __name__ == "__main__":
    main()
