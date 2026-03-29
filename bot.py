"""
Bot de Arbitraje Interno — Polymarket
======================================
Escanea mercados cada N minutos buscando oportunidades donde
YES_ask + NO_ask < $1.00, y ejecuta las operaciones automáticamente.

Uso:
    python bot.py              # Escaneo cada 5 minutos
    python bot.py --once       # Un solo escaneo y termina
    python bot.py --interval 2 # Escaneo cada 2 minutos
"""
import sys
import time
import argparse
from datetime import datetime

from src.arbitrage import scan_opportunities
from src.executor import execute_arbitrage
from src.portfolio import record_trade, print_summary
from src.client import build_client
from config import settings


def print_header():
    mode = "DRY RUN (simulación)" if settings.DRY_RUN else "PRODUCCIÓN — órdenes reales"
    print(f"""
╔══════════════════════════════════════════════════════╗
║         POLYMARKET ARBITRAGE BOT                     ║
║  Modo: {mode:<44}║
║  Capital máx/op: ${settings.MAX_POSITION_SIZE:<5} | ROI mínimo: {settings.MIN_ROI*100:.0f}%           ║
╚══════════════════════════════════════════════════════╝""")


def run_scan_cycle(client, cycle_num: int) -> int:
    """
    Ejecuta un ciclo completo: escanear → filtrar → ejecutar.
    Devuelve el número de operaciones ejecutadas.
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] Ciclo #{cycle_num} — Escaneando mercados...")

    opportunities = scan_opportunities(verbose=True)

    if not opportunities:
        print(f"  Sin oportunidades de arbitraje en este momento.")
        return 0

    print(f"\n  ✓ {len(opportunities)} oportunidad(es) encontrada(s):\n")
    for opp in opportunities:
        print(opp)

    # Ejecutar las mejores (máximo 3 por ciclo para no arriesgar demasiado)
    executed = 0
    for opp in opportunities[:3]:
        print(f"\n  → Procesando: {opp.question[:50]}...")
        result = execute_arbitrage(client, opp)

        if result["success"]:
            trade_id = record_trade(opp, result)
            profit = result["expected_profit"]
            cost = result["cost_total"]
            print(f"  ✓ Operación registrada [{trade_id}]")
            print(f"    Invertido: ${cost:.2f} | Ganancia esperada: ${profit:.2f} ({opp.roi*100:.2f}% ROI)")
            executed += 1
        else:
            print(f"  ✗ Operación fallida: {result.get('error', 'desconocido')}")

        time.sleep(1)  # Pausa entre operaciones

    return executed


def main():
    parser = argparse.ArgumentParser(description="Polymarket Arbitrage Bot")
    parser.add_argument("--once", action="store_true", help="Ejecutar un solo ciclo y terminar")
    parser.add_argument("--interval", type=int, default=5, help="Minutos entre escaneos (default: 5)")
    args = parser.parse_args()

    print_header()

    if not settings.DRY_RUN:
        print("\n⚠️  MODO PRODUCCIÓN ACTIVO — Se ejecutarán órdenes reales.")
        print("   Presiona Ctrl+C en los próximos 5 segundos para cancelar...")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("Cancelado.")
            sys.exit(0)

    # Construir cliente (autenticado solo si no es DRY RUN o si hay credenciales)
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

            next_scan = datetime.now().strftime("%H:%M:%S")
            print(f"\n  Próximo escaneo en {args.interval} minuto(s). Presiona Ctrl+C para detener.")
            print(f"  Operaciones ejecutadas en esta sesión: {total_executed}")

            time.sleep(args.interval * 60)

    except KeyboardInterrupt:
        print(f"\n\nBot detenido por el usuario.")

    print_summary()
    print(f"Sesión finalizada. Operaciones ejecutadas: {total_executed}")


if __name__ == "__main__":
    main()
