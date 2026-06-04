import os
import json
from web3 import Web3
from dotenv import load_dotenv

# Tự động nạp cấu hình khi import module
load_dotenv()

class BlockchainManager:
    def __init__(self):
        self.rpc_url = os.getenv("ETH_RPC_URL", "http://127.0.0.1:8545")
        self.private_key = os.getenv("PRIVATE_KEY")
        self.contract_address = os.getenv("CONTRACT_ADDRESS")
        
        self.w3 = None
        self.account = None
        self.contract = None
        self.abi = None
        
        self.connect()

    def connect(self):
        """Khởi tạo kết nối tới Ethereum Devnet RPC Node"""
        try:
            load_dotenv(override=True)
            self.rpc_url = os.getenv("ETH_RPC_URL", "http://127.0.0.1:8545")
            self.private_key = os.getenv("PRIVATE_KEY")
            self.contract_address = os.getenv("CONTRACT_ADDRESS")
            
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if not self.w3.is_connected():
                return False
                
            if self.private_key:
                self.account = self.w3.eth.account.from_key(self.private_key)
                
                # Kiểm tra xem account có ETH không (hỗ trợ trường hợp dùng key Anvil trên Ganache)
                try:
                    balance = self.w3.eth.get_balance(self.account.address)
                    if balance == 0:
                        print(f"[Blockchain] Admin account {self.account.address} has 0 ETH, auto-detecting funded account...")
                        node_accounts = self.w3.eth.accounts
                        for addr in node_accounts:
                            acc_bal = self.w3.eth.get_balance(addr)
                            if acc_bal > 0:
                                # Tạo pseudo-account object cho unlocked address
                                self.account = type('Account', (), {'address': addr})()
                                self.private_key = None  # Không cần ký, dùng unlocked account
                                print(f"[Blockchain] Using unlocked admin: {addr}")
                                break
                except Exception:
                    pass
                
            artifact_path = os.path.join(os.path.dirname(__file__), "contracts", "ParkingLot.json")
            if os.path.exists(artifact_path) and self.contract_address:
                try:
                    self.contract_address = self.w3.to_checksum_address(self.contract_address)
                except Exception:
                    pass
                
                try:
                    code = self.w3.eth.get_code(self.contract_address)
                    if not code or code == b'' or code.hex() == '0x':
                        print(f"[Blockchain] WARNING: Khong tim thay bytecode tai dia chi hop dong: {self.contract_address}. Hop dong chua duoc deploy hoac Ganache da bi restart.")
                        self.contract = None
                    else:
                        with open(artifact_path, "r", encoding="utf-8") as f:
                            artifact = json.load(f)
                        self.abi = artifact["abi"]
                        self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.abi)
                        print(f"[Blockchain] Ket noi thanh cong toi contract tai dia chi: {self.contract_address}")
                except Exception as contract_err:
                    print(f"[Blockchain] Loi khi xac thuc bytecode contract: {contract_err}")
                    self.contract = None
            else:
                self.contract = None
            return True
        except Exception as e:
            print(f"[Blockchain] Loi ket noi Web3: {e}")
            self.contract = None
            return False

    def is_connected(self):
        """Kiểm tra kết nối blockchain"""
        if not self.w3:
            return self.connect()
        try:
            connected = self.w3.is_connected()
            if connected and not self.contract and os.getenv("CONTRACT_ADDRESS"):
                self.connect()
            return connected
        except Exception:
            return False

    def get_system_wallet_address(self):
        if self.account:
            return self.account.address
        return "N/A"

    def get_balance(self, wallet_address=None):
        """Lấy số dư tài khoản (đơn vị ETH)"""
        if not self.is_connected():
            return 0.0
        try:
            target = wallet_address if wallet_address else (self.account.address if self.account else None)
            if not target:
                return 0.0
            balance_wei = self.w3.eth.get_balance(target)
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc số dư ví: {e}")
            return 0.0

    def get_contract_address(self):
        return self.contract_address if self.contract_address else "Chưa deploy"

    def get_contract_balance(self):
        """Lấy số dư ETH trong Smart Contract (bao gồm cọc + doanh thu)"""
        if not self.is_connected() or not self.contract_address:
            return 0.0
        try:
            balance_wei = self.w3.eth.get_balance(self.contract_address)
            return float(self.w3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc số dư hợp đồng: {e}")
            return 0.0

    def get_total_revenue(self):
        """Lấy tổng doanh thu có thể rút (totalRevenue trong contract)"""
        if not self.is_connected() or not self.contract:
            return 0.0
        try:
            rev_wei = self.contract.functions.totalRevenue().call()
            return float(self.w3.from_wei(rev_wei, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc totalRevenue: {e}")
            return 0.0

    def get_total_held_deposits(self):
        """Lấy tổng tiền cọc đang giữ (totalHeldDeposits trong contract)"""
        if not self.is_connected() or not self.contract:
            return 0.0
        try:
            dep_wei = self.contract.functions.totalHeldDeposits().call()
            return float(self.w3.from_wei(dep_wei, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc totalHeldDeposits: {e}")
            return 0.0

    def get_deposit_amount_eth(self):
        """Lấy mức tiền cọc yêu cầu (đơn vị ETH)"""
        if not self.is_connected() or not self.contract:
            return 0.005
        try:
            dep_wei = self.contract.functions.depositAmount().call()
            return float(self.w3.from_wei(dep_wei, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc depositAmount: {e}")
            return 0.005

    def get_parking_rate_eth_per_min(self):
        """Lấy đơn giá đỗ xe (ETH mỗi phút)"""
        if not self.is_connected() or not self.contract:
            return 0.00006
        try:
            rate_wei_per_sec = self.contract.functions.parkingRate().call()
            rate_wei_per_min = rate_wei_per_sec * 60
            return float(self.w3.from_wei(rate_wei_per_min, 'ether'))
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc parkingRate: {e}")
            return 0.00006

    def get_booking_status(self, slot_id):
        """Lấy thông tin đặt chỗ từ blockchain: (user, startTime, duration, active)"""
        if not self.is_connected() or not self.contract:
            return "0x0000000000000000000000000000000000000000", 0, 0, False
        try:
            return self.contract.functions.getBookingStatus(int(slot_id)).call()
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc getBookingStatus: {e}")
            return "0x0000000000000000000000000000000000000000", 0, 0, False

    def get_session_status(self, slot_id):
        """Lấy thông tin phiên đỗ xe từ blockchain: (user, entryTime, deposit, active, vehicleId)"""
        if not self.is_connected() or not self.contract:
            return "0x0000000000000000000000000000000000000000", 0, 0, False, ""
        try:
            return self.contract.functions.getSessionStatus(int(slot_id)).call()
        except Exception as e:
            print(f"[Blockchain] Lỗi đọc getSessionStatus: {e}")
            return "0x0000000000000000000000000000000000000000", 0, 0, False, ""

    # ─── Giao dịch ghi (Write transactions) ────────────────────────

    def _is_address(self, key_or_addr):
        """Kiểm tra xem input là địa chỉ (42 ký tự) hay private key (66 ký tự)"""
        if not key_or_addr:
            return False
        return key_or_addr.startswith("0x") and len(key_or_addr) == 42

    def _send_signed_tx(self, tx_data, private_key=None):
        """Helper: Ký và gửi giao dịch bằng private key, trả về (tx_hash_hex, receipt)"""
        key = private_key or self.private_key
        signed_tx = self.w3.eth.account.sign_transaction(tx_data, private_key=key)
        raw_tx = getattr(signed_tx, "raw_transaction", getattr(signed_tx, "rawTransaction", None))
        tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        return tx_hash.hex(), tx_receipt

    def _send_unlocked_tx(self, tx_data):
        """Helper: Gửi giao dịch bằng unlocked account (Ganache), trả về (tx_hash_hex, receipt)"""
        tx_hash = self.w3.eth.send_transaction(tx_data)
        tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        return tx_hash.hex(), tx_receipt

    def _send_admin_tx(self, tx_data):
        """Gửi giao dịch admin: dùng signed nếu có private key, fallback unlocked (Ganache)"""
        if self.private_key:
            try:
                return self._send_signed_tx(tx_data)
            except Exception as sign_err:
                print(f"[Blockchain] Signed tx failed: {sign_err}, trying unlocked account...")
        # Fallback hoặc trực tiếp: gửi bằng unlocked account (Ganache)
        tx_data['from'] = self.account.address
        return self._send_unlocked_tx(tx_data)

    def book_slot_on_chain(self, client_key_or_addr, slot_id, duration_minutes):
        """Khách hàng đặt chỗ và nạp cọc ETH. Hỗ trợ cả private key và unlocked address."""
        if not self.is_connected() or not self.contract:
            return None, False, "Chưa kết nối Smart Contract!"
        try:
            duration_secs = int(duration_minutes * 60)
            deposit_wei = self.contract.functions.depositAmount().call()
            
            if self._is_address(client_key_or_addr):
                # Ganache unlocked account
                client_address = client_key_or_addr
                nonce = self.w3.eth.get_transaction_count(client_address)
                tx_data = self.contract.functions.bookSlot(
                    int(slot_id), duration_secs
                ).build_transaction({
                    'chainId': self.w3.eth.chain_id,
                    'gas': 250000,
                    'gasPrice': self.w3.eth.gas_price,
                    'value': deposit_wei,
                    'nonce': nonce,
                    'from': client_address,
                })
                tx_hash_hex, tx_receipt = self._send_unlocked_tx(tx_data)
            else:
                # Signed transaction (có private key)
                client_account = self.w3.eth.account.from_key(client_key_or_addr)
                nonce = self.w3.eth.get_transaction_count(client_account.address)
                tx_data = self.contract.functions.bookSlot(
                    int(slot_id), duration_secs
                ).build_transaction({
                    'chainId': self.w3.eth.chain_id,
                    'gas': 250000,
                    'gasPrice': self.w3.eth.gas_price,
                    'value': deposit_wei,
                    'nonce': nonce,
                })
                tx_hash_hex, tx_receipt = self._send_signed_tx(tx_data, client_key_or_addr)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Đặt chỗ thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch đặt chỗ bị revert!"
        except Exception as e:
            return None, False, f"Lỗi đặt chỗ: {e}"

    def cancel_booking_on_chain(self, client_key_or_addr, slot_id):
        """Khách hàng hủy đặt chỗ, hoàn cọc tự động. Hỗ trợ cả private key và unlocked address."""
        if not self.is_connected() or not self.contract:
            return None, False, "Chưa kết nối Smart Contract!"
        try:
            if self._is_address(client_key_or_addr):
                client_address = client_key_or_addr
                nonce = self.w3.eth.get_transaction_count(client_address)
                tx_data = self.contract.functions.cancelBooking(int(slot_id)).build_transaction({
                    'chainId': self.w3.eth.chain_id,
                    'gas': 200000,
                    'gasPrice': self.w3.eth.gas_price,
                    'nonce': nonce,
                    'from': client_address,
                })
                tx_hash_hex, tx_receipt = self._send_unlocked_tx(tx_data)
            else:
                client_account = self.w3.eth.account.from_key(client_key_or_addr)
                nonce = self.w3.eth.get_transaction_count(client_account.address)
                tx_data = self.contract.functions.cancelBooking(int(slot_id)).build_transaction({
                    'chainId': self.w3.eth.chain_id,
                    'gas': 200000,
                    'gasPrice': self.w3.eth.gas_price,
                    'nonce': nonce,
                })
                tx_hash_hex, tx_receipt = self._send_signed_tx(tx_data, client_key_or_addr)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Hủy đặt chỗ và hoàn cọc thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch hủy bị revert!"
        except Exception as e:
            return None, False, f"Lỗi hủy đặt chỗ: {e}"

    def check_in_on_chain(self, slot_id, vehicle_id):
        """Hệ thống check-in xe vào ô đỗ (Admin)"""
        if not self.is_connected() or not self.contract or not self.account:
            return None, False, "Chưa kết nối ví Admin!"
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx_data = self.contract.functions.checkIn(
                int(slot_id), str(vehicle_id)
            ).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 250000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            tx_hash_hex, tx_receipt = self._send_admin_tx(tx_data)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Check In thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch Check In bị revert!"
        except Exception as e:
            return None, False, f"Lỗi Check In: {e}"

    def check_out_on_chain(self, slot_id):
        """Hệ thống check-out xe, tự động thu phí và hoàn cọc"""
        if not self.is_connected() or not self.contract or not self.account:
            return None, False, "Chưa kết nối ví Admin!"
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx_data = self.contract.functions.checkOut(int(slot_id)).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            tx_hash_hex, tx_receipt = self._send_admin_tx(tx_data)
            
            if tx_receipt.status == 1:
                refund_val = 0
                fee_val = 0
                try:
                    logs = self.contract.events.ParkedOut().process_receipt(tx_receipt)
                    if logs:
                        args = logs[0]['args']
                        fee_val = float(self.w3.from_wei(args['actualFee'], 'ether'))
                        refund_val = float(self.w3.from_wei(args['refundAmount'], 'ether'))
                except Exception as log_err:
                    print(f"[Blockchain] Lỗi đọc log sự kiện checkout: {log_err}")
                
                return tx_hash_hex, True, f"Check Out thành công! Phí: {fee_val:.6f} ETH. Hoàn cọc: {refund_val:.6f} ETH."
            else:
                return tx_hash_hex, False, "Giao dịch Check Out bị revert!"
        except Exception as e:
            return None, False, f"Lỗi Check Out: {e}"

    def set_rate_on_chain(self, new_rate_eth_per_min):
        """Admin thay đổi giá đỗ xe (ETH mỗi phút)"""
        if not self.is_connected() or not self.contract or not self.account:
            return None, False, "Chưa kết nối ví Admin!"
        try:
            rate_wei_per_min = self.w3.to_wei(new_rate_eth_per_min, 'ether')
            rate_wei_per_sec = int(rate_wei_per_min / 60)
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx_data = self.contract.functions.setRate(rate_wei_per_sec).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            tx_hash_hex, tx_receipt = self._send_admin_tx(tx_data)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Thay đổi đơn giá thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch setRate bị revert!"
        except Exception as e:
            return None, False, f"Lỗi setRate: {e}"

    def set_deposit_amount_on_chain(self, new_deposit_eth):
        """Admin thay đổi mức tiền cọc đặt chỗ"""
        if not self.is_connected() or not self.contract or not self.account:
            return None, False, "Chưa kết nối ví Admin!"
        try:
            deposit_wei = self.w3.to_wei(new_deposit_eth, 'ether')
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx_data = self.contract.functions.setDepositAmount(deposit_wei).build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            tx_hash_hex, tx_receipt = self._send_admin_tx(tx_data)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Thay đổi mức tiền cọc thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch setDepositAmount bị revert!"
        except Exception as e:
            return None, False, f"Lỗi setDepositAmount: {e}"

    def withdraw_revenues_on_chain(self):
        """Admin rút doanh thu (CHỈ phần revenue, KHÔNG rút cọc khách hàng)"""
        if not self.is_connected() or not self.contract or not self.account:
            return None, False, "Chưa kết nối ví Admin!"
        try:
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            tx_data = self.contract.functions.withdrawRevenues().build_transaction({
                'chainId': self.w3.eth.chain_id,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            tx_hash_hex, tx_receipt = self._send_admin_tx(tx_data)
            
            if tx_receipt.status == 1:
                return tx_hash_hex, True, "Rút doanh thu thành công!"
            else:
                return tx_hash_hex, False, "Giao dịch withdrawRevenues bị revert!"
        except Exception as e:
            return None, False, f"Lỗi rút doanh thu: {e}"

    # Fallback tương thích ngược
    def record_event_on_chain(self, slot_id, vehicle_id, event_type, preset_name=""):
        if event_type.upper() == "IN":
            return self.check_in_on_chain(slot_id, vehicle_id)
        else:
            return self.check_out_on_chain(slot_id)
