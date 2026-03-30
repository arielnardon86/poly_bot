"""
Script de aprobación on-chain de contratos de Polymarket.
Debe ejecutarse UNA SOLA VEZ antes de operar en producción.

Requiere: al menos 0.01 MATIC en la wallet para gas.

Uso:
    python scripts/approve_contracts.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web3 import Web3
from config import settings

# Contratos que necesitan aprobación
CONTRACTS = {
    "CTF_EXCHANGE (mercados binarios YES/NO)": settings.EXCHANGE_ADDRESS,
    "NEG_RISK_EXCHANGE (mercados multi-outcome)": settings.NEG_RISK_EXCHANGE,
    "NEG_RISK_ADAPTER (adaptador negRisk)": settings.NEG_RISK_ADAPTER,
}

ERC20_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

MAX_APPROVAL = 2**256 - 1  # Aprobación máxima (estándar DeFi)
POLYGON_RPC = "https://1rpc.io/matic"


def main():
    print("\n=== Polymarket — Aprobación de Contratos ===\n")

    if not settings.PRIVATE_KEY or not settings.WALLET_ADDRESS:
        print("ERROR: PRIVATE_KEY o WALLET_ADDRESS no configurados en .env")
        sys.exit(1)

    # Conectar a Polygon
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC, request_kwargs={"timeout": 15}))
    if not w3.is_connected():
        print("ERROR: No se pudo conectar a Polygon. Revisá tu conexión.")
        sys.exit(1)

    wallet = Web3.to_checksum_address(settings.WALLET_ADDRESS)
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(settings.USDC_ADDRESS),
        abi=ERC20_ABI
    )

    # Verificar balance de MATIC
    matic_balance = w3.eth.get_balance(wallet)
    matic_eth = w3.from_wei(matic_balance, "ether")
    print(f"Wallet: {wallet}")
    print(f"MATIC (gas): {matic_eth:.4f} MATIC")

    if matic_balance < w3.to_wei(0.001, "ether"):
        print("\n⚠️  PROBLEMA: Necesitás al menos 0.001 MATIC para pagar gas.")
        print("\n¿Cómo obtener MATIC?")
        print("  1. Faucet oficial de Polygon: https://faucet.polygon.technology")
        print("     (Requiere login con Twitter/Discord, da 0.2 MATIC gratis)")
        print("  2. Comprá en un exchange (Binance, Coinbase) y retirá a Polygon Mainnet")
        print("  3. Con $1 de MATIC alcanza para miles de transacciones.")
        sys.exit(1)

    print(f"\nVerificando allowances actuales...")
    needs_approval = []
    for name, addr in CONTRACTS.items():
        addr_cs = Web3.to_checksum_address(addr)
        allowance = usdc.functions.allowance(wallet, addr_cs).call()
        status = "✓ OK" if allowance > 0 else "✗ FALTA"
        print(f"  {status} {name}")
        if allowance == 0:
            needs_approval.append((name, addr_cs))

    if not needs_approval:
        print("\n✓ Todos los contratos ya tienen aprobación. Listo para operar.")
        return

    print(f"\n  {len(needs_approval)} contratos necesitan aprobación.")
    print("  Esto requiere firmar transacciones on-chain con gas (MATIC).")

    confirm = input("\n¿Continuar? (s/N): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        sys.exit(0)

    # Cargar private key
    pk = settings.PRIVATE_KEY
    if not pk.startswith("0x"):
        pk = "0x" + pk
    account = w3.eth.account.from_key(pk)

    nonce = w3.eth.get_transaction_count(wallet)

    for name, addr_cs in needs_approval:
        print(f"\n  Aprobando {name}...")
        try:
            gas_price = w3.eth.gas_price
            tx = usdc.functions.approve(addr_cs, MAX_APPROVAL).build_transaction({
                "from": wallet,
                "nonce": nonce,
                "gasPrice": gas_price,
                "gas": 100000,
                "chainId": settings.CHAIN_ID,
            })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"  ✓ TX enviada: {tx_hash.hex()}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.status == 1:
                print(f"  ✓ Confirmada en bloque {receipt.blockNumber}")
            else:
                print(f"  ✗ Transacción falló en bloque {receipt.blockNumber}")
            nonce += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")

    print("\n=== Verificación final ===")
    for name, addr in CONTRACTS.items():
        addr_cs = Web3.to_checksum_address(addr)
        allowance = usdc.functions.allowance(wallet, addr_cs).call()
        status = "✓ OK" if allowance > 0 else "✗ FALTA"
        print(f"  {status} {name}: {allowance}")

    print("\n✓ Listo. Ahora podés ejecutar el bot:")
    print("  python bot.py --interval 3")


if __name__ == "__main__":
    main()
