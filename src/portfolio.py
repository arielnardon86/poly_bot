"""
Seguimiento de posiciones abiertas y P&L (ganancias/pérdidas).
Persiste en data/portfolio.json para sobrevivir reinicios del bot.
"""
import json
import os
from datetime import datetime

PORTFOLIO_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "portfolio.json"
)


def _load() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"positions": [], "closed": [], "stats": {"total_invested": 0, "total_profit": 0, "trades": 0}}


def _save(data: dict):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_trade(opportunity, result: dict):
    """Registra una operación ejecutada en el portfolio."""
    data = _load()

    position = {
        "id": f"arb_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "market_id": opportunity.market_id,
        "question": opportunity.question,
        "yes_token_id": opportunity.yes_token_id,
        "no_token_id": opportunity.no_token_id,
        "yes_ask": opportunity.yes_ask,
        "no_ask": opportunity.no_ask,
        "shares": result.get("shares", 0),
        "cost_total": result.get("cost_total", 0),
        "expected_profit": result.get("expected_profit", 0),
        "roi": opportunity.roi,
        "status": "open",
        "dry_run": result.get("dry_run", False),
    }

    data["positions"].append(position)
    data["stats"]["total_invested"] += position["cost_total"]
    data["stats"]["trades"] += 1
    _save(data)
    return position["id"]


def print_summary():
    """Imprime un resumen del portfolio en consola."""
    data = _load()
    stats = data["stats"]
    positions = data["positions"]
    open_positions = [p for p in positions if p["status"] == "open"]

    print(f"\n{'='*55}")
    print(f"  PORTFOLIO SUMMARY")
    print(f"{'='*55}")
    print(f"  Operaciones totales : {stats['trades']}")
    print(f"  Capital invertido   : ${stats['total_invested']:.2f}")
    print(f"  Ganancia realizada  : ${stats['total_profit']:.2f}")
    print(f"  Posiciones abiertas : {len(open_positions)}")

    if open_positions:
        total_expected = sum(p["expected_profit"] for p in open_positions)
        print(f"  Ganancia pendiente  : ${total_expected:.2f} (al resolver mercados)")
        print(f"\n  Posiciones abiertas:")
        for p in open_positions[-5:]:  # Últimas 5
            dry = " [DRY]" if p.get("dry_run") else ""
            print(f"    • {p['question'][:40]}...")
            print(f"      ${p['cost_total']:.2f} invertidos → +${p['expected_profit']:.2f} esperado{dry}")
    print(f"{'='*55}\n")


def get_open_positions() -> list:
    return [p for p in _load()["positions"] if p["status"] == "open"]
