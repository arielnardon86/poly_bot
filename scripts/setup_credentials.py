"""
Script de configuración inicial.
Genera las API credentials (L2) a partir de tu private key (L1)
y las guarda automáticamente en tu archivo .env.

Uso:
    python scripts/setup_credentials.py
"""
import sys
import os

# Asegura que el root del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py_clob_client.client import ClobClient
from config import settings


def main():
    print("\n=== Polymarket - Configuración de Credenciales ===\n")

    # Verificar que tengamos lo mínimo necesario
    if not settings.PRIVATE_KEY:
        print("ERROR: PRIVATE_KEY no encontrada en .env")
        print("1. Copia .env.example a .env")
        print("2. Agrega tu private key de MetaMask")
        sys.exit(1)

    if not settings.WALLET_ADDRESS:
        print("ERROR: WALLET_ADDRESS no encontrada en .env")
        sys.exit(1)

    print(f"Wallet: {settings.WALLET_ADDRESS}")
    print("Conectando a Polymarket CLOB...")

    try:
        client = ClobClient(
            settings.CLOB_URL,
            key=settings.PRIVATE_KEY,
            chain_id=settings.CHAIN_ID,
            signature_type=2,       # Browser proxy (MetaMask via Polymarket web)
            funder=settings.WALLET_ADDRESS,
        )

        print("Generando credenciales API (esto firma un mensaje con tu wallet)...")
        creds = client.create_or_derive_api_creds()

        api_key = creds.api_key
        api_secret = creds.api_secret
        api_passphrase = creds.api_passphrase

        print("\n✓ Credenciales generadas exitosamente:")
        print(f"  API Key:        {api_key}")
        print(f"  API Secret:     {api_secret[:8]}...")
        print(f"  API Passphrase: {api_passphrase[:8]}...")

        # Guardar en .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

        if not os.path.exists(env_path):
            print(f"\nERROR: No existe el archivo .env en {env_path}")
            print("Crea el .env copiando desde .env.example primero.")
            sys.exit(1)

        # Leer el .env actual
        with open(env_path, "r") as f:
            content = f.read()

        # Reemplazar o agregar las variables
        def update_env_var(content: str, key: str, value: str) -> str:
            lines = content.splitlines()
            found = False
            new_lines = []
            for line in lines:
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={value}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"{key}={value}")
            return "\n".join(new_lines)

        content = update_env_var(content, "POLY_API_KEY", api_key)
        content = update_env_var(content, "POLY_API_SECRET", api_secret)
        content = update_env_var(content, "POLY_API_PASSPHRASE", api_passphrase)

        with open(env_path, "w") as f:
            f.write(content)

        print(f"\n✓ Credenciales guardadas en {env_path}")
        print("\nYa puedes ejecutar: python main.py")

    except Exception as e:
        print(f"\nERROR al generar credenciales: {e}")
        print("\nPosibles causas:")
        print("  - Private key incorrecta o en formato incorrecto")
        print("  - Sin conexión a internet")
        print("  - La wallet no tiene MATIC para gas (necesitas al menos $0.10 en MATIC)")
        sys.exit(1)


if __name__ == "__main__":
    main()
