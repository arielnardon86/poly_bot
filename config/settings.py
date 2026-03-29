import os
from dotenv import load_dotenv

load_dotenv()

# --- Blockchain ---
CHAIN_ID = 137  # Polygon Mainnet

# --- Wallet ---
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")

# --- API Credentials (se generan con setup_credentials.py) ---
POLY_API_KEY = os.getenv("POLY_API_KEY", "")
POLY_API_SECRET = os.getenv("POLY_API_SECRET", "")
POLY_API_PASSPHRASE = os.getenv("POLY_API_PASSPHRASE", "")

# --- URLs de la API ---
CLOB_URL = "https://clob.polymarket.com"
GAMMA_URL = "https://gamma-api.polymarket.com"
DATA_URL = "https://data-api.polymarket.com"

# --- Parámetros del bot ---
MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", 50))   # USDC máx por operación
MIN_ROI = float(os.getenv("MIN_ROI", 0.03))                      # 3% ROI mínimo
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

# --- Contratos en Polygon (para aprobaciones de tokens) ---
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACE5EA0476045"
EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"


def validate_config():
    """Verifica que las variables críticas estén configuradas."""
    errors = []
    if not PRIVATE_KEY:
        errors.append("PRIVATE_KEY no configurada en .env")
    if not WALLET_ADDRESS:
        errors.append("WALLET_ADDRESS no configurada en .env")
    if errors:
        raise ValueError("Configuración incompleta:\n" + "\n".join(f"  - {e}" for e in errors))
