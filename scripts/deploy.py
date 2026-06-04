import os
import json
import sys
from web3 import Web3
from dotenv import load_dotenv


def _update_env_contract(dotenv_path, contract_address):
    """Cập nhật CONTRACT_ADDRESS vào file .env"""
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        for line in lines:
            if line.startswith("CONTRACT_ADDRESS="):
                new_lines.append(f"CONTRACT_ADDRESS={contract_address}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f"\nCONTRACT_ADDRESS={contract_address}\n")

        with open(dotenv_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        print("Da tu dong cap nhat CONTRACT_ADDRESS vao file .env!")
    except Exception as e:
        print(f"Khong the tu dong ghi de file .env: {e}")
        print(f"Vui long cau hinh thu cong: CONTRACT_ADDRESS={contract_address}")


def deploy():
    print("Dang khoi tao trien khai Smart Contract len Devnet...")

    # Nap cau hinh tu .env (dung duong dan tuyet doi de tranh loi khi chay tu thu muc khac)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dotenv_path = os.path.join(project_root, ".env")
    load_dotenv(dotenv_path)

    rpc_url = os.getenv("ETH_RPC_URL", "http://127.0.0.1:8545")
    private_key = os.getenv("PRIVATE_KEY")

    if not private_key:
        print("Loi: Chua cau hinh PRIVATE_KEY trong file .env!")
        sys.exit(1)

    # Ket noi RPC Node
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print(f"Loi: Khong the ket noi toi Ethereum RPC Node tai: {rpc_url}")
        print("Vui long khoi chay mang Devnet (Ganache/Anvil/Hardhat) truoc!")
        sys.exit(1)

    print(f"Da ket noi toi Devnet tai: {rpc_url}")

    # Doc thong tin contract da bien dich
    artifact_path = os.path.join(project_root, "contracts", "ParkingLot.json")
    if not os.path.exists(artifact_path):
        print(f"Loi: Khong tim thay file da bien dich: {artifact_path}")
        print("Vui long chay script compile_contract.py truoc!")
        sys.exit(1)

    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    # Khoi tao contract factory
    ParkingLot = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Lay tai khoan tuong ung voi Private Key
    try:
        account = w3.eth.account.from_key(private_key)
        print(f"Su dung tai khoan he thong: {account.address}")
        balance = w3.eth.get_balance(account.address)
        balance_eth = float(w3.from_wei(balance, 'ether'))
        print(f"So du tai khoan: {balance_eth} ETH")
    except Exception as e:
        print(f"Loi doc tai khoan tu PRIVATE_KEY: {e}")
        sys.exit(1)

    # Neu tai khoan khong du tien, thu lay account co tien tu node (Ganache/Anvil)
    if balance_eth < 0.01:
        print(f"\n[!] Tai khoan {account.address} khong du ETH de deploy!")
        print("Dang tim tai khoan co tien tu Devnet node...")

        node_accounts = w3.eth.accounts
        funded_account = None
        for addr in node_accounts:
            acc_balance = w3.eth.get_balance(addr)
            acc_eth = float(w3.from_wei(acc_balance, 'ether'))
            if acc_eth >= 1.0:
                funded_account = addr
                print(f"[OK] Tim thay tai khoan co tien: {addr} ({acc_eth:.2f} ETH)")
                break

        if funded_account:
            print("\n[TIP] Private Key trong .env khong khop voi Devnet dang chay.")
            print("Neu ban dung Ganache, hay copy Private Key tu Ganache GUI/CLI")
            print("va dan vao file .env (thay the PRIVATE_KEY=...)")
            print(f"\nDang thu deploy bang unlocked account: {funded_account}")

            # Deploy truc tiep bang unlocked account (Ganache/Anvil cho phep)
            nonce = w3.eth.get_transaction_count(funded_account)
            gas_estimate = ParkingLot.constructor().estimate_gas({'from': funded_account})

            tx = ParkingLot.constructor().build_transaction({
                'chainId': w3.eth.chain_id,
                'gas': int(gas_estimate * 1.2),
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'from': funded_account,
            })

            # Gui truc tiep (unlocked account — Ganache cho phep)
            print("Dang gui giao dich deploy (unlocked account)...")
            tx_hash = w3.eth.send_transaction(tx)
            print(f"Transaction Hash: {tx_hash.hex()}")

            print("Dang cho xac thuc giao dich...")
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            contract_address = tx_receipt.contractAddress
            print(f"\n[SUCCESS] Smart Contract da duoc deploy thanh cong!")
            print(f"[ADDRESS] {contract_address}")

            _update_env_contract(dotenv_path, contract_address)
            return
        else:
            print("\n[ERROR] Khong tim thay tai khoan nao co du ETH tren Devnet!")
            print("Hay kiem tra lai:")
            print("  1. Ganache/Anvil co dang chay khong?")
            print("  2. Copy dung Private Key tu Ganache vao .env")
            sys.exit(1)

    # --- Deploy binh thuong bang private key da cau hinh ---
    print("Dang tao va ky giao dich deploy...")
    nonce = w3.eth.get_transaction_count(account.address)

    # Phi gas uoc luong
    gas_estimate = ParkingLot.constructor().estimate_gas({'from': account.address})

    tx = ParkingLot.constructor().build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': int(gas_estimate * 1.2),
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })

    # Ky transaction
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)

    # Gui transaction
    print("Dang gui giao dich len blockchain...")
    raw_tx = getattr(signed_tx, "raw_transaction", getattr(signed_tx, "rawTransaction", None))
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print(f"Transaction Hash: {tx_hash.hex()}")

    # Cho transaction duoc khai thac (mining)
    print("Dang cho xac thuc giao dich...")
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress
    print(f"\n[SUCCESS] Smart Contract da duoc deploy thanh cong!")
    print(f"[ADDRESS] {contract_address}")

    _update_env_contract(dotenv_path, contract_address)


if __name__ == "__main__":
    deploy()
