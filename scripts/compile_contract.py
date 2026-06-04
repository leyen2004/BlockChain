import json
import os
import sys

def compile():
    print("Đang chuẩn bị biên dịch Smart Contract...")
    try:
        import solcx
    except ImportError:
        print("Đang cài đặt thư viện py-solc-x...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "py-solc-x"])
        import solcx

    try:
        # Cài đặt solc phiên bản 0.8.20 nếu chưa có
        solc_version = "0.8.20"
        installed_versions = solcx.get_installed_solc_versions()
        if not any(str(v) == solc_version or getattr(v, "vstring", "") == solc_version for v in installed_versions):
            print(f"Đang cài đặt solc phiên bản {solc_version}...")
            solcx.install_solc(solc_version)
        solcx.set_solc_version(solc_version)
    except Exception as e:
        print(f"Không thể cài đặt solc: {e}")
        sys.exit(1)

    contract_path = os.path.join("contracts", "ParkingLot.sol")
    if not os.path.exists(contract_path):
        print(f"Không tìm thấy file hợp đồng: {contract_path}")
        sys.exit(1)

    print(f"Đang biên dịch: {contract_path}")
    try:
        compiled_sol = solcx.compile_files(
            [contract_path],
            output_values=["abi", "bin"]
        )
        
        contract_key = f"{contract_path}:ParkingLot"
        if contract_key not in compiled_sol:
            # Fallback nếu tên key khác
            contract_key = list(compiled_sol.keys())[0]
            
        contract_interface = compiled_sol[contract_key]
        
        output_path = os.path.join("contracts", "ParkingLot.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "abi": contract_interface["abi"],
                "bytecode": contract_interface["bin"]
            }, f, indent=2)
            
        print(f"Biên dịch thành công! Đã lưu ABI & Bytecode vào: {output_path}")
    except Exception as e:
        print(f"Lỗi biên dịch hợp đồng: {e}")
        sys.exit(1)

if __name__ == "__main__":
    compile()
