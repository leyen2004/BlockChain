@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title Smart Parking DApp
color 0A

echo ============================================================
echo        SMART PARKING DAPP - HE THONG BAI XE THONG MINH
echo ============================================================
echo.

cd /d "%~dp0"

:: ============================================================
:: BUOC 1: Kiem tra Python
:: ============================================================
echo [1/5] Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python!
    echo       Cai dat tai: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo       %%i
echo.

:: ============================================================
:: BUOC 2: Kiem tra thu vien
:: ============================================================
echo [2/5] Kiem tra thu vien...
python -c "import web3, dotenv, PyQt6, cv2, ultralytics" >nul 2>&1
if errorlevel 1 (
    echo       Dang cai dat thu vien...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [LOI] Cai dat that bai!
        pause
        exit /b 1
    )
)
echo       OK
echo.

:: ============================================================
:: BUOC 3: Khoi dong Ganache
:: ============================================================
echo [3/5] Kiem tra Blockchain Devnet...

python -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('http://127.0.0.1:8545')); exit(0 if w3.is_connected() else 1)" >nul 2>&1
if not errorlevel 1 (
    echo       Devnet da dang chay tai port 8545
    goto :ganache_ok
)

echo       Ganache chua chay. Dang khoi dong...

where ganache >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Ganache CLI!
    echo       Cai dat: npm install -g ganache
    echo       Hoac mo Ganache GUI thu cong truoc.
    pause
    exit /b 1
)

:: Khoi dong Ganache ngam (cua so minimize)
start "Ganache" /min cmd /c "ganache --port 8545 --accounts 10 --defaultBalanceEther 1000 --chain.chainId 1337 2>&1 & pause"

:: Cho Ganache san sang (toi da 20 giay)
echo       Dang cho Ganache san sang
set /a COUNT=0

:wait_ganache
if !COUNT! GEQ 20 (
    echo.
    echo [LOI] Ganache khong khoi dong duoc sau 20 giay!
    echo       Thu mo Ganache thu cong roi chay lai.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
set /a COUNT+=1
<nul set /p "=."
python -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('http://127.0.0.1:8545')); exit(0 if w3.is_connected() else 1)" >nul 2>&1
if errorlevel 1 goto :wait_ganache

echo.
echo       Ganache da khoi dong! (%COUNT% giay)

:ganache_ok
python -c "from web3 import Web3; w3=Web3(Web3.HTTPProvider('http://127.0.0.1:8545')); accs=w3.eth.accounts; print(f'       Chain ID: {w3.eth.chain_id}  |  Accounts: {len(accs)}')" 2>nul
echo.

:: ============================================================
:: BUOC 4: Compile + Deploy (neu can)
:: ============================================================
echo [4/5] Kiem tra Smart Contract...

python -c "from blockchain_manager import BlockchainManager; bm=BlockchainManager(); assert bm.is_connected() and bm.contract; print(f'       Contract: {bm.get_contract_address()}')" 2>nul
if not errorlevel 1 (
    echo       Contract da san sang!
    goto :contract_ok
)

echo       Chua co contract. Compile + Deploy...
echo.

echo       [Compile] ParkingLot.sol...
python scripts/compile_contract.py
if errorlevel 1 (
    echo [LOI] Compile that bai!
    pause
    exit /b 1
)
echo       [Compile] OK

echo       [Deploy] Dang trien khai len Devnet...
python scripts/deploy.py
if errorlevel 1 (
    echo [LOI] Deploy that bai!
    pause
    exit /b 1
)
echo       [Deploy] OK

:contract_ok
echo.

:: ============================================================
:: BUOC 5: Chay ung dung
:: ============================================================
echo [5/5] Khoi dong ung dung...
echo.
echo ============================================================
echo   Log blockchain hien thi ben duoi.
echo   Dong cua so = tat ung dung.
echo ============================================================
echo.

python main.py

echo.
echo ============================================================
echo   App da dong.
echo ============================================================
pause
