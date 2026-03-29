"""
Dashboard web del bot de arbitraje — con login protegido.

Uso:
    python dashboard/app.py
    Luego abre: http://localhost:5001

Acceso remoto desde celular:
    ngrok http 5001
"""
import sys
import os
import json
from datetime import datetime
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from config import settings

app = Flask(__name__)
app.secret_key = settings.DASHBOARD_SECRET_KEY

PORTFOLIO_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "portfolio.json"
)


def load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"positions": [], "closed": [], "stats": {"total_invested": 0, "total_profit": 0, "trades": 0}}


def get_live_balance() -> dict:
    """Consulta el saldo real de USDC en Polymarket."""
    try:
        from src.client import build_client
        from py_clob_client.clob_types import AssetType, BalanceAllowanceParams
        client = build_client(authenticated=True)
        raw = client.get_balance_allowance(
            params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        # USDC tiene 6 decimales en Polygon
        raw_balance = int(raw.get("balance", 0))
        usdc = raw_balance / 1_000_000 if raw_balance > 1000 else raw_balance
        return {"usdc": round(usdc, 2), "error": None}
    except Exception as e:
        return {"usdc": None, "error": str(e)}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = request.form.get("username", "")
        pwd  = request.form.get("password", "")
        if user == settings.DASHBOARD_USER and pwd == settings.DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Usuario o contraseña incorrectos"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html",
        dry_run=settings.DRY_RUN,
        wallet=settings.WALLET_ADDRESS or "No configurada",
        max_position=settings.MAX_POSITION_SIZE,
        min_roi=settings.MIN_ROI * 100,
        initial_capital=settings.INITIAL_CAPITAL,
    )


@app.route("/api/balance")
@login_required
def api_balance():
    balance = get_live_balance()
    initial = settings.INITIAL_CAPITAL
    usdc = balance["usdc"]

    pnl = None
    pnl_pct = None
    if usdc is not None and initial > 0:
        # Saldo actual + ganancias pendientes (acciones abiertas)
        data = load_portfolio()
        positions = data.get("positions", [])
        pending = sum(p.get("expected_profit", 0) for p in positions if p.get("status") == "open")
        total_value = usdc + pending
        pnl = round(total_value - initial, 2)
        pnl_pct = round((pnl / initial) * 100, 2) if initial > 0 else 0

    return jsonify({
        "usdc_balance": usdc,
        "initial_capital": initial,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "error": balance["error"],
    })


@app.route("/api/portfolio")
@login_required
def api_portfolio():
    data = load_portfolio()
    positions = data.get("positions", [])
    stats = data.get("stats", {})

    open_pos   = [p for p in positions if p.get("status") == "open"]
    closed_pos = [p for p in positions if p.get("status") == "closed"]

    total_expected      = sum(p.get("expected_profit", 0) for p in open_pos)
    total_invested_open = sum(p.get("cost_total", 0) for p in open_pos)

    return jsonify({
        "stats": {
            "total_trades": stats.get("trades", 0),
            "total_invested": round(stats.get("total_invested", 0), 2),
            "total_profit_realized": round(stats.get("total_profit", 0), 2),
            "total_profit_pending": round(total_expected, 2),
            "open_positions": len(open_pos),
            "closed_positions": len(closed_pos),
            "invested_in_open": round(total_invested_open, 2),
        },
        "open_positions": sorted(open_pos, key=lambda p: p.get("timestamp", ""), reverse=True),
        "recent_trades":  sorted(positions, key=lambda p: p.get("timestamp", ""), reverse=True)[:20],
    })


@app.route("/api/status")
@login_required
def api_status():
    return jsonify({
        "bot_mode": "DRY RUN" if settings.DRY_RUN else "PRODUCCIÓN",
        "dry_run": settings.DRY_RUN,
        "wallet": settings.WALLET_ADDRESS,
        "max_position_size": settings.MAX_POSITION_SIZE,
        "min_roi_pct": settings.MIN_ROI * 100,
        "last_updated": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    print("\nDashboard iniciado en: http://localhost:5001")
    print(f"Usuario: {settings.DASHBOARD_USER}")
    print("Para acceso remoto: ngrok http 5001\n")
    app.run(debug=False, host="0.0.0.0", port=5001)
