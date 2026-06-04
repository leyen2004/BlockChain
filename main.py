import cv2
import numpy as np
import time
import os
import json
import sys
import ctypes
from datetime import datetime

from ultralytics import YOLO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QFileDialog, QMessageBox, 
    QListWidget, QFrame, QDialog, QScrollArea, QGridLayout,
    QGraphicsOpacityEffect, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QThread
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette
import threading
import uuid

from db_manager import ParkingDB
from blockchain_manager import BlockchainManager

PRESETS_DIR = "presets"
if not os.path.exists(PRESETS_DIR):
    os.makedirs(PRESETS_DIR)

# ================= THEMES =================

LIGHT_THEME = """
QWidget {
    background-color: #f5f6fa;
    color: #2f3640;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #f5f6fa;
}
QFrame#MainFrame {
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #dcdde1;
}
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 15px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:disabled {
    background-color: #bdc3c7;
    color: #ecf0f1;
}
QPushButton#CheckInBtn {
    background-color: #27ae60;
}
QPushButton#CheckInBtn:hover {
    background-color: #2ecc71;
}
QPushButton#CheckInBtn:disabled {
    background-color: #95a5a6;
}
QPushButton#DangerBtn {
    background-color: #e74c3c;
}
QPushButton#DangerBtn:hover {
    background-color: #c0392b;
}
QPushButton#SuccessBtn {
    background-color: #2ecc71;
}
QPushButton#SuccessBtn:hover {
    background-color: #27ae60;
}
QLineEdit {
    padding: 5px;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    background-color: #ffffff;
    color: #2c3e50;
}
QListWidget {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #3498db;
    color: white;
}
QLabel#HeaderLabel {
    font-size: 18px;
    font-weight: bold;
    color: #2c3e50;
}
QLabel#SubHeaderLabel {
    font-size: 12px;
    color: #7f8c8d;
}
QTableWidget {
    font-size: 14px;
    font-weight: bold;
}
QHeaderView::section {
    font-size: 14px;
    font-weight: bold;
    background-color: #ecf0f1;
}
"""

DARK_THEME = """
QWidget {
    background-color: #1e272e;
    color: #f5f6fa;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e272e;
}
QFrame#MainFrame {
    background-color: #2f3640;
    border-radius: 10px;
    border: 1px solid #353b48;
}
QPushButton {
    background-color: #0984e3;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 15px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #74b9ff;
}
QPushButton:disabled {
    background-color: #7f8fa6;
    color: #dcdde1;
}
QPushButton#CheckInBtn {
    background-color: #00b894;
}
QPushButton#CheckInBtn:hover {
    background-color: #55efc4;
}
QPushButton#CheckInBtn:disabled {
    background-color: #7f8fa6;
}
QPushButton#DangerBtn {
    background-color: #d63031;
}
QPushButton#DangerBtn:hover {
    background-color: #ff7675;
}
QPushButton#SuccessBtn {
    background-color: #00b894;
}
QPushButton#SuccessBtn:hover {
    background-color: #55efc4;
}
QLineEdit {
    padding: 5px;
    border: 1px solid #7f8fa6;
    border-radius: 4px;
    background-color: #353b48;
    color: #f5f6fa;
}
QListWidget {
    background-color: #353b48;
    border: 1px solid #7f8fa6;
    border-radius: 4px;
    color: #f5f6fa;
}
QListWidget::item:selected {
    background-color: #0984e3;
    color: white;
}
QLabel#HeaderLabel {
    font-size: 18px;
    font-weight: bold;
    color: #00a8ff;
}
QLabel#SubHeaderLabel {
    font-size: 12px;
    color: #b2bec3;
}
QTableWidget {
    font-size: 14px;
    font-weight: bold;
}
QHeaderView::section {
    font-size: 14px;
    font-weight: bold;
    background-color: #2f3640;
}
"""

# ================= TITLE BAR THEME =================
def set_titlebar_theme(window, is_dark):
    if sys.platform != "win32":
        return
    try:
        from ctypes.wintypes import HWND, DWORD
        import ctypes
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        hwnd = HWND(int(window.winId()))
        value = DWORD(1 if is_dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        
        DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, ctypes.byref(value), ctypes.sizeof(value))
    except Exception as e:
        pass

# ================= THREADING =================

class DetectionWorker(QObject):
    # Signals
    on_error = pyqtSignal(str)
    on_finished = pyqtSignal()
    show_checkin_signal = pyqtSignal()
    
    def __init__(self, app_logic, screen_w, screen_h):
        super().__init__()
        self.app = app_logic
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._is_running = True
        
    def run(self):
        try:
            model = YOLO(resource_path('yolov8m.pt'))
        except Exception as e:
            self.on_error.emit(f"Gặp sự cố khi khởi tạo model YOLO: {e}")
            return
            
        is_webcam = self.app.is_webcam
        
        if is_webcam:
            cap = cv2.VideoCapture(self.app.webcam_index)
        else:
            cap = cv2.VideoCapture(self.app.video_path)
            
        if not cap.isOpened():
            self.on_error.emit(f"Không thể kết nối với Camera số {self.app.webcam_index}." if is_webcam else "Không thể đọc đường dẫn video.")
            self.on_finished.emit()
            return
        
        if not is_webcam:
            try:
                start_sec = float(self.app.entry_start.text())
                end_sec = float(self.app.entry_end.text()) if float(self.app.entry_end.text()) > 0 else float('inf')
            except:
                start_sec, end_sec = 0.0, float('inf')
            cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
        else:
            start_sec, end_sec = 0.0, float('inf')
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        delay = int(1000 / fps) if fps > 0 else 30
        
        self.app.prev_poly_status = [False] * len(self.app.polygons)
        
        DEBOUNCE_THRESHOLD = 10
        debounce_counters = [0] * len(self.app.polygons)
        confirmed_status = [False] * len(self.app.polygons)
        
        if self.app.polygons:
            self.app.db.reset_slot_status(len(self.app.polygons))
            
        polygons_copy = [poly[:] for poly in self.app.polygons]
        preset_name = self.app.current_preset_name
        
        if is_webcam:
            w = int(self.screen_w * 2 / 3)
            h = self.screen_h - 100
            cv2.namedWindow("Video Detection", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Video Detection", w, h)
            cv2.moveWindow("Video Detection", 0, 0)
            
        while cap.isOpened() and self._is_running:
            if not is_webcam:
                current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                if current_msec > end_sec * 1000:
                    break
                    
            start_time_proc = time.time()
            
            ret, frame = cap.read()
            if not ret:
                break
                
            results = model.predict(frame, stream=True, verbose=False, classes=[2, 5, 7])
            
            car_centers = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    cx = int((x1 + x2) / 2)
                    cy = int(y2 - (y2 - y1) * 0.3)
                    car_centers.append((cx, cy))
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (200, 200, 200), 1)
                    cv2.circle(frame, (cx, cy), 4, (0, 255, 255), -1)
                    
            occupied_count = 0
            current_status = []
            for idx, poly in enumerate(polygons_copy):
                poly_np = np.array(poly, np.int32)
                is_occupied = False
                for cx, cy in car_centers:
                    if cv2.pointPolygonTest(poly_np, (cx, cy), False) >= 0:
                        is_occupied = True
                        break
                
                current_status.append(is_occupied)
                pcx = int(sum(p[0] for p in poly) / len(poly))
                pcy = int(sum(p[1] for p in poly) / len(poly))
                
                if is_occupied:
                    cv2.polylines(frame, [poly_np], True, (0, 0, 255), 3)
                    occupied_count += 1
                else:
                    cv2.polylines(frame, [poly_np], True, (0, 255, 0), 3)
                
                cv2.putText(frame, str(idx + 1), (pcx - 8, pcy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
            if len(current_status) == len(confirmed_status):
                for idx in range(len(current_status)):
                    if current_status[idx] != confirmed_status[idx]:
                        debounce_counters[idx] += 1
                        if debounce_counters[idx] >= DEBOUNCE_THRESHOLD:
                            slot_id = idx + 1
                            if current_status[idx] and not confirmed_status[idx]:
                                self.app.db.record_vehicle_in(slot_id, preset_name)
                                self.app.record_blockchain_event(slot_id, "IN", preset_name)
                            elif not current_status[idx] and confirmed_status[idx]:
                                self.app.db.record_vehicle_out(slot_id, preset_name)
                                self.app.record_blockchain_event(slot_id, "OUT", preset_name)
                            confirmed_status[idx] = current_status[idx]
                            debounce_counters[idx] = 0
                    else:
                        debounce_counters[idx] = 0
                        
            self.app.last_poly_status = current_status
            
            cv2.putText(frame, "'Q' stop | 'I' Check In", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame, f"Trang thai: {occupied_count}/{len(polygons_copy)} cho", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            
            cv2.imshow("Video Detection", frame)
            
            elapsed = int((time.time() - start_time_proc) * 1000)
            wait_time = max(1, delay - elapsed)
            
            key = cv2.waitKey(wait_time) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('i') and is_webcam:
                self.show_checkin_signal.emit()
                
        cap.release()
        try:
            cv2.destroyWindow("Video Detection")
        except:
            pass
            
        self.on_finished.emit()

    def stop(self):
        self._is_running = False


# ================= MAIN UI =================

class ParkingAppUI(QMainWindow):
    update_blockchain_ui_signal = pyqtSignal()
    # Signal để thread blockchain thông báo kết quả về main thread
    # Args: (success: bool, message: str, callback_id: str)
    _bc_action_done = pyqtSignal(bool, str, str)

    def __init__(self):
        super().__init__()
        # State
        self.db = ParkingDB()
        self.blockchain_mgr = BlockchainManager()
        
        # Private Keys của 3 tài khoản khách hàng — tự động lấy từ Ganache/Anvil
        self.customer_wallets = self._detect_customer_wallets()
        self._threads = []
        self._workers = []
        self.polygons = []
        self.current_polygon = []
        self.current_preset_name = ""
        self.video_path = ""
        self.is_webcam = False
        self.webcam_index = 0
        
        self.detection_active = False
        self.last_poly_status = []
        self.prev_poly_status = []
        
        self.is_dark_mode = False
        
        self.update_blockchain_ui_signal.connect(self.update_blockchain_ui)
        self._bc_action_done.connect(self._on_bc_action_done)
        self._bc_callbacks = {}
        
        self.init_ui()
        self.update_blockchain_ui()
        
        # Timer cập nhật blockchain định kỳ (chạy trên worker thread)
        self.bc_timer = QTimer(self)
        self.bc_timer.timeout.connect(self._update_blockchain_ui_async)
        self.bc_timer.start(5000)
        
        # Timer cập nhật bảng slot status
        self.slot_timer = QTimer(self)
        self.slot_timer.timeout.connect(self._refresh_slot_grid)
        self.slot_timer.start(2000)

    def _detect_customer_wallets(self):
        """Đọc danh sách tài khoản từ Devnet node (Ganache/Anvil) và lấy 3 account có ETH (bỏ qua account #0 là Admin)"""
        wallets = []
        try:
            if not self.blockchain_mgr.is_connected() or not self.blockchain_mgr.w3:
                return wallets
            
            w3 = self.blockchain_mgr.w3
            accounts = w3.eth.accounts
            admin_addr = self.blockchain_mgr.get_system_wallet_address()
            
            for addr in accounts:
                # Bỏ qua tài khoản Admin
                if addr.lower() == admin_addr.lower():
                    continue
                balance = w3.eth.get_balance(addr)
                if balance > 0:
                    wallets.append({"address": addr, "private_key": None})
                if len(wallets) >= 3:
                    break
            
            if wallets:
                print(f"[Ganache] Tìm thấy {len(wallets)} ví khách hàng từ Devnet node")
            else:
                print("[Ganache] Không tìm thấy ví khách hàng nào có ETH")
        except Exception as e:
            print(f"[Ganache] Lỗi đọc accounts từ node: {e}")
        return wallets
        
    def init_ui(self):
        self.setWindowIcon(QIcon(resource_path("icon.ico")))
        self.setWindowTitle("Parking Vehicle Detection - Blockchain DApp console")
        self.resize(1150, 600)
        
        # Central widget & Layout
        central = QWidget()
        self.setCentralWidget(central)
        
        # main_layout chứa header ở trên cùng, và chia 2 cột ở dưới
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header Controls
        header_layout = QHBoxLayout()
        self.toggle_theme_btn = QPushButton("🌞 Chế độ Sáng")
        self.toggle_theme_btn.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.toggle_theme_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        header_layout.addStretch()
        
        self.btn_dashboard = QPushButton("📊 Báo Cáo")
        self.btn_dashboard.clicked.connect(self.show_dashboard)
        header_layout.addWidget(self.btn_dashboard)
        
        self.btn_checkin = QPushButton("✅ Check In")
        self.btn_checkin.setObjectName("CheckInBtn")
        self.btn_checkin.clicked.connect(self.show_checkin_popup)
        self.btn_checkin.setEnabled(False)
        header_layout.addWidget(self.btn_checkin)
        
        main_layout.addLayout(header_layout)
        
        # Giao diện chính chia làm hai cột
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # ---------------- CỘT TRÁI (Nhận diện AI & Log Node) ----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)
        
        # Main Frame Box (AI Settings)
        frame_main = QFrame()
        frame_main.setObjectName("MainFrame")
        frame_layout = QVBoxLayout(frame_main)
        frame_layout.setContentsMargins(20, 20, 20, 20)
        frame_layout.setSpacing(15)
        
        lbl_title = QLabel("CÀI ĐẶT CHỨC NĂNG NHẬN DIỆN")
        lbl_title.setObjectName("HeaderLabel")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(lbl_title)
        
        # Video settings
        v_layout1 = QHBoxLayout()
        v_layout1.addWidget(QLabel("Video/Camera:"))
        self.entry_video = QLineEdit()
        self.entry_video.setReadOnly(True)
        v_layout1.addWidget(self.entry_video)
        
        self.btn_browse = QPushButton("Duyệt File")
        self.btn_browse.clicked.connect(self.browse_file)
        v_layout1.addWidget(self.btn_browse)
        
        self.btn_webcam = QPushButton("Sử Dụng Camera")
        self.btn_webcam.clicked.connect(self.choose_webcam)
        v_layout1.addWidget(self.btn_webcam)
        
        frame_layout.addLayout(v_layout1)
        
        # Time settings
        v_layout2 = QHBoxLayout()
        v_layout2.addWidget(QLabel("Thời điểm bắt đầu (giây):"))
        self.entry_start = QLineEdit("0")
        v_layout2.addWidget(self.entry_start)
        
        v_layout2.addWidget(QLabel("Thời điểm kết thúc (giây):"))
        self.entry_end = QLineEdit("0")
        v_layout2.addWidget(self.entry_end)
        
        frame_layout.addLayout(v_layout2)
        
        lbl_hint = QLabel("0 = chạy hết video")
        lbl_hint.setObjectName("SubHeaderLabel")
        frame_layout.addWidget(lbl_hint)
        
        # Action Buttons
        v_layout3 = QHBoxLayout()
        self.btn_mark = QPushButton("Khoanh Vùng Đỗ Xe")
        self.btn_mark.clicked.connect(self.start_draw_regions)
        v_layout3.addWidget(self.btn_mark)
        
        self.btn_detect = QPushButton("BẮT ĐẦU NHẬN DIỆN")
        self.btn_detect.setObjectName("SuccessBtn")
        self.btn_detect.clicked.connect(self.start_detection)
        v_layout3.addWidget(self.btn_detect)
        frame_layout.addLayout(v_layout3)
        
        left_layout.addWidget(frame_main)
        
        # Blockchain Info Frame
        self.frame_bc = QFrame()
        self.frame_bc.setObjectName("MainFrame")
        bc_layout = QVBoxLayout(self.frame_bc)
        bc_layout.setContentsMargins(15, 15, 15, 15)
        bc_layout.setSpacing(10)
        
        bc_header = QHBoxLayout()
        lbl_bc_title = QLabel("🔗 HỆ THỐNG BLOCKCHAIN DEVNET")
        lbl_bc_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #3498db;")
        bc_header.addWidget(lbl_bc_title)
        
        self.lbl_bc_status = QLabel("🔴 Mất kết nối")
        self.lbl_bc_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #e74c3c;")
        bc_header.addWidget(self.lbl_bc_status, alignment=Qt.AlignmentFlag.AlignRight)
        bc_layout.addLayout(bc_header)
        
        bc_grid = QGridLayout()
        bc_grid.addWidget(QLabel("Hợp đồng:"), 0, 0)
        self.lbl_contract = QLineEdit("N/A")
        self.lbl_contract.setReadOnly(True)
        self.lbl_contract.setStyleSheet("border: none; background: transparent; font-family: monospace; font-weight: bold;")
        bc_grid.addWidget(self.lbl_contract, 0, 1)
        
        bc_grid.addWidget(QLabel("Ví hệ thống:"), 1, 0)
        self.lbl_wallet = QLineEdit("N/A")
        self.lbl_wallet.setReadOnly(True)
        self.lbl_wallet.setStyleSheet("border: none; background: transparent; font-family: monospace; font-weight: bold;")
        bc_grid.addWidget(self.lbl_wallet, 1, 1)
        
        bc_grid.addWidget(QLabel("Số dư ví:"), 2, 0)
        self.lbl_balance = QLabel("0.0 ETH")
        self.lbl_balance.setStyleSheet("font-weight: bold; color: #2ecc71;")
        bc_grid.addWidget(self.lbl_balance, 2, 1)
        
        bc_layout.addLayout(bc_grid)
        left_layout.addWidget(self.frame_bc)
        
        # ─── Bảng Trạng thái Ô đỗ Thời gian thực ───
        self.frame_slots = QFrame()
        self.frame_slots.setObjectName("MainFrame")
        slots_layout = QVBoxLayout(self.frame_slots)
        slots_layout.setContentsMargins(15, 15, 15, 15)
        slots_layout.setSpacing(8)
        
        lbl_slots_title = QLabel("🅿️ TRẠNG THÁI Ô ĐỖ XE")
        lbl_slots_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #9b59b6;")
        slots_layout.addWidget(lbl_slots_title)
        
        self.slot_grid_widget = QWidget()
        self.slot_grid_layout = QGridLayout(self.slot_grid_widget)
        self.slot_grid_layout.setSpacing(6)
        slots_layout.addWidget(self.slot_grid_widget)
        
        left_layout.addWidget(self.frame_slots)
        
        # ─── Log Sự kiện Thời gian thực ───
        self.frame_events = QFrame()
        self.frame_events.setObjectName("MainFrame")
        events_layout = QVBoxLayout(self.frame_events)
        events_layout.setContentsMargins(15, 10, 15, 10)
        events_layout.setSpacing(5)
        
        lbl_events_title = QLabel("📋 SỰ KIỆN GẦN NHẤT")
        lbl_events_title.setStyleSheet("font-weight: bold; font-size: 13px; color: #16a085;")
        events_layout.addWidget(lbl_events_title)
        
        self.event_log = QListWidget()
        self.event_log.setMaximumHeight(120)
        self.event_log.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px;")
        events_layout.addWidget(self.event_log)
        
        left_layout.addWidget(self.frame_events)
        
        content_layout.addWidget(left_widget)
        
        # ---------------- CỘT PHẢI (Trình giả lập DApp & Admin) ----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # 1. Customer Simulator Card
        self.frame_customer = QFrame()
        self.frame_customer.setObjectName("MainFrame")
        cust_layout = QVBoxLayout(self.frame_customer)
        cust_layout.setContentsMargins(15, 15, 15, 15)
        cust_layout.setSpacing(10)
        
        lbl_cust_title = QLabel("📱 DAPP GIẢ LẬP KHÁCH HÀNG")
        lbl_cust_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2ecc71;")
        cust_layout.addWidget(lbl_cust_title)
        
        cust_grid = QGridLayout()
        cust_grid.addWidget(QLabel("Chọn ví khách:"), 0, 0)
        self.combo_wallets = QComboBox()
        # Tạo labels dựa trên ví đã detect từ Ganache/Anvil
        wallet_labels = []
        for i, w in enumerate(self.customer_wallets):
            addr = w["address"]
            wallet_labels.append(f"Ví Khách {i+1} ({addr[:6]}...{addr[-4:]})")
        if not wallet_labels:
            wallet_labels = ["(Không tìm thấy ví — nhập Private Key bên dưới)"]
        self.combo_wallets.addItems(wallet_labels)
        self.combo_wallets.currentIndexChanged.connect(self.update_customer_wallet_info)
        cust_grid.addWidget(self.combo_wallets, 0, 1)
        
        cust_grid.addWidget(QLabel("Địa chỉ ví:"), 1, 0)
        self.entry_cust_address = QLineEdit()
        self.entry_cust_address.setReadOnly(True)
        self.entry_cust_address.setStyleSheet("border: none; background: transparent; font-family: monospace; font-weight: bold;")
        cust_grid.addWidget(self.entry_cust_address, 1, 1)
        
        cust_grid.addWidget(QLabel("Số dư ví:"), 2, 0)
        self.lbl_cust_balance = QLabel("0.0 ETH")
        self.lbl_cust_balance.setStyleSheet("font-weight: bold; color: #2ecc71;")
        cust_grid.addWidget(self.lbl_cust_balance, 2, 1)

        cust_grid.addWidget(QLabel("Private Key khác (tùy chọn):"), 3, 0)
        self.entry_cust_key = QLineEdit()
        self.entry_cust_key.setPlaceholderText("Dán Private Key từ terminal để đổi tài khoản...")
        self.entry_cust_key.textChanged.connect(self.update_customer_wallet_info)
        cust_grid.addWidget(self.entry_cust_key, 3, 1)
        
        cust_layout.addLayout(cust_grid)
        
        # Form đặt chỗ
        book_layout = QHBoxLayout()
        book_layout.addWidget(QLabel("Đặt Ô đỗ: "))
        self.entry_book_slot = QLineEdit("1")
        self.entry_book_slot.setMaximumWidth(40)
        book_layout.addWidget(self.entry_book_slot)
        
        book_layout.addWidget(QLabel("Thời gian đặt (phút): "))
        self.entry_book_duration = QLineEdit("30")
        self.entry_book_duration.setMaximumWidth(55)
        book_layout.addWidget(self.entry_book_duration)
        cust_layout.addLayout(book_layout)
        
        btn_layout_cust = QHBoxLayout()
        self.btn_book = QPushButton("Đặt Chỗ Trước (Nạp Cọc)")
        self.btn_book.setObjectName("SuccessBtn")
        self.btn_book.clicked.connect(self.book_slot_action)
        btn_layout_cust.addWidget(self.btn_book)
        
        self.btn_cancel_book = QPushButton("Hủy Đặt Chỗ (Hoàn Cọc)")
        self.btn_cancel_book.setObjectName("DangerBtn")
        self.btn_cancel_book.clicked.connect(self.cancel_booking_action)
        btn_layout_cust.addWidget(self.btn_cancel_book)
        cust_layout.addLayout(btn_layout_cust)
        
        # ─── Bảng Booking đang hoạt động ───
        lbl_bookings = QLabel("📋 Đặt chỗ đang hoạt động:")
        lbl_bookings.setStyleSheet("font-weight: bold; font-size: 12px; color: #f39c12; margin-top: 5px;")
        cust_layout.addWidget(lbl_bookings)
        
        self.table_bookings = QTableWidget()
        self.table_bookings.setColumnCount(4)
        self.table_bookings.setHorizontalHeaderLabels(["Ô đỗ", "Ví", "Thời lượng", "Cọc"])
        self.table_bookings.verticalHeader().setVisible(False)
        self.table_bookings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_bookings.setMaximumHeight(100)
        self.table_bookings.setStyleSheet("font-size: 11px;")
        cust_layout.addWidget(self.table_bookings)
        
        right_layout.addWidget(self.frame_customer)
        
        # 2. Admin Management Card
        self.frame_admin_bc = QFrame()
        self.frame_admin_bc.setObjectName("MainFrame")
        admin_layout = QVBoxLayout(self.frame_admin_bc)
        admin_layout.setContentsMargins(15, 15, 15, 15)
        admin_layout.setSpacing(10)
        
        lbl_admin_title = QLabel("⚙️ QUẢN TRỊ ADMIN BÃI XE")
        lbl_admin_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #e67e22;")
        admin_layout.addWidget(lbl_admin_title)
        
        admin_grid = QGridLayout()
        admin_grid.addWidget(QLabel("Số dư Contract:"), 0, 0)
        self.lbl_contract_balance = QLabel("0.0 ETH")
        self.lbl_contract_balance.setStyleSheet("font-weight: bold; color: #e67e22; font-size: 14px;")
        admin_grid.addWidget(self.lbl_contract_balance, 0, 1)
        
        admin_grid.addWidget(QLabel("Doanh thu (rút được):"), 1, 0)
        self.lbl_revenue = QLabel("0.0 ETH")
        self.lbl_revenue.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 13px;")
        admin_grid.addWidget(self.lbl_revenue, 1, 1)
        
        admin_grid.addWidget(QLabel("Cọc đang giữ:"), 2, 0)
        self.lbl_held_deposits = QLabel("0.0 ETH")
        self.lbl_held_deposits.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 13px;")
        admin_grid.addWidget(self.lbl_held_deposits, 2, 1)
        
        admin_grid.addWidget(QLabel("Đơn giá (ETH/min):"), 3, 0)
        self.entry_rate = QLineEdit("0.00006")
        self.entry_rate.setMaximumWidth(100)
        admin_grid.addWidget(self.entry_rate, 3, 1)
        
        admin_grid.addWidget(QLabel("Tiền cọc (ETH):"), 4, 0)
        self.entry_deposit = QLineEdit("0.005")
        self.entry_deposit.setMaximumWidth(100)
        admin_grid.addWidget(self.entry_deposit, 4, 1)
        admin_layout.addLayout(admin_grid)
        
        btn_layout_admin = QHBoxLayout()
        self.btn_set_rate = QPushButton("Cập Nhật Biểu Phí")
        self.btn_set_rate.clicked.connect(self.set_rate_action)
        btn_layout_admin.addWidget(self.btn_set_rate)
        
        self.btn_set_deposit = QPushButton("Cập Nhật Tiền Cọc")
        self.btn_set_deposit.clicked.connect(self.set_deposit_action)
        btn_layout_admin.addWidget(self.btn_set_deposit)
        
        self.btn_withdraw = QPushButton("Rút Doanh Thu")
        self.btn_withdraw.setObjectName("CheckInBtn")
        self.btn_withdraw.clicked.connect(self.withdraw_revenues_action)
        btn_layout_admin.addWidget(self.btn_withdraw)
        admin_layout.addLayout(btn_layout_admin)
        
        right_layout.addWidget(self.frame_admin_bc)
        
        content_layout.addWidget(right_widget)
        
        main_layout.addLayout(content_layout)
        
        self.apply_theme()
        
    def fade_in(self, widget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.start()
        widget.anim = anim
        
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()
        if self.is_dark_mode:
            self.toggle_theme_btn.setText("🌞 Chế độ Sáng")
        else:
            self.toggle_theme_btn.setText("🌙 Chế độ Tối")
            
    def apply_theme(self):
        theme = DARK_THEME if self.is_dark_mode else LIGHT_THEME
        self.setStyleSheet(theme)
        
        # Áp dụng màu titlebar cho toàn bộ các cửa sổ/dialog đang mở
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, (QMainWindow, QDialog)):
                set_titlebar_theme(widget, self.is_dark_mode)
                
        if hasattr(self, 'dash') and self.dash.isVisible():
            self.dash.setStyleSheet(theme)
        if hasattr(self, '_checkin_dialog') and self._checkin_dialog.isVisible():
            self._checkin_dialog.setStyleSheet(theme)
        
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn Video", "", "Video Files (*.mp4 *.avi *.mkv *.mov)")
        if file_path:
            self.video_path = file_path
            self.entry_video.setText(file_path)
            self.entry_start.setText("0")
            self.entry_end.setText("0")
            self.is_webcam = False
            self.btn_webcam.setText("Sử Dụng Camera")
            self.polygons = []
            
    def choose_webcam(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Chọn Camera")
        dialog.resize(300, 200)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("Đang tìm các camera khả dụng..."))
        # Force UI update
        QApplication.processEvents()
        
        available_cameras = []
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available_cameras.append(i)
                cap.release()
                
        # clear loading
        for i in reversed(range(layout.count())): 
            layout.itemAt(i).widget().setParent(None)
            
        if not available_cameras:
            layout.addWidget(QLabel("Không tìm thấy camera nào."))
            btn = QPushButton("Đóng")
            btn.clicked.connect(dialog.accept)
            layout.addWidget(btn)
        else:
            layout.addWidget(QLabel("Chọn một camera:"))
            for cam_idx in available_cameras:
                btn = QPushButton(f"Camera {cam_idx}")
                btn.clicked.connect(lambda checked, idx=cam_idx: self.set_webcam(idx, dialog))
                layout.addWidget(btn)
                
        set_titlebar_theme(dialog, self.is_dark_mode)
        self.fade_in(dialog)
        dialog.exec()
        
    def set_webcam(self, idx, dialog):
        self.webcam_index = idx
        self.is_webcam = True
        self.video_path = ""
        self.entry_video.setText(f"Webcam {idx}")
        self.btn_webcam.setText(f"Đang Chọn Camera {idx}")
        self.entry_start.setEnabled(False)
        self.entry_end.setEnabled(False)
        self.polygons = []
        dialog.accept()

    def get_preset_list(self):
        files = [f for f in os.listdir(PRESETS_DIR) if f.endswith('.json')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(PRESETS_DIR, x)), reverse=True)
        return [f.replace('.json', '') for f in files]

    def start_draw_regions(self):
        if not self.video_path and not self.is_webcam:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video trước bằng nút Duyệt File hoặc chọn Camera!")
            return
            
        presets = self.get_preset_list()
        if not presets:
            self.execute_draw()
            return
            
        self.show_preset_dialog(presets)
        
    def show_preset_dialog(self, presets):
        dialog = QDialog(self)
        dialog.setWindowTitle("Chọn Preset hoặc Vẽ mới")
        dialog.resize(400, 350)
        layout = QVBoxLayout(dialog)
        
        lbl = QLabel("CHỌN VÙNG ĐỖ XE")
        lbl.setObjectName("HeaderLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        layout.addWidget(QLabel("Chọn preset có sẵn hoặc vẽ mới:"))
        
        lw = QListWidget()
        lw.addItems(presets)
        layout.addWidget(lw)
        
        btn_layout = QHBoxLayout()
        
        btn_load = QPushButton("Tải Preset")
        btn_load.setObjectName("SuccessBtn")
        btn_draw = QPushButton("Vẽ Mới")
        btn_del = QPushButton("Xóa Preset")
        btn_del.setObjectName("DangerBtn")
        
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_draw)
        btn_layout.addWidget(btn_del)
        layout.addLayout(btn_layout)
        
        def on_load():
            item = lw.currentItem()
            if not item:
                QMessageBox.warning(dialog, "Chưa chọn", "Vui lòng chọn một preset từ danh sách.")
                return
            self.load_preset(item.text())
            dialog.accept()
            
        def on_draw():
            dialog.accept()
            self.execute_draw()
            
        def on_del():
            item = lw.currentItem()
            if not item:
                QMessageBox.warning(dialog, "Chưa chọn", "Vui lòng chọn một preset.")
                return
            name = item.text()
            rep = QMessageBox.question(dialog, "Xác nhận", f"Bạn có chắc muốn xóa preset '{name}'?")
            if rep == QMessageBox.StandardButton.Yes:
                p = os.path.join(PRESETS_DIR, name + ".json")
                if os.path.exists(p): os.remove(p)
                lw.takeItem(lw.row(item))
                
        btn_load.clicked.connect(on_load)
        btn_draw.clicked.connect(on_draw)
        btn_del.clicked.connect(on_del)
        
        set_titlebar_theme(dialog, self.is_dark_mode)
        self.fade_in(dialog)
        dialog.exec()
        
    def load_preset(self, name):
        p = os.path.join(PRESETS_DIR, name + ".json")
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.polygons = [list(map(tuple, poly)) for poly in data.get("polygons", [])]
            self.current_preset_name = name
            QMessageBox.information(self, "Thành công", f"Đã tải preset '{name}' với {len(self.polygons)} ô đỗ.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi tải preset: {e}")

    def execute_draw(self):
        # Implement raw OpenCV drawing logic with blocking waitKey
        if self.is_webcam:
            cap = cv2.VideoCapture(self.webcam_index)
        else:
            cap = cv2.VideoCapture(self.video_path)
        
        if not self.is_webcam:
            try:
                start_sec = float(self.entry_start.text())
                cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)
            except:
                pass
        else:
            # Warm-up webcam: Read and discard ~20 frames 
            # to let DroidCam connect and auto-exposure settle
            for _ in range(20):
                cap.read()
                
        ret, frame = cap.read()
        if not ret:
            QMessageBox.critical(self, "Lỗi", "Không thể đọc khung hình từ video.")
            cap.release()
            return
            
        temp_frame = frame.copy()
        cv2.namedWindow('Draw Parking Regions', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Draw Parking Regions', frame.shape[1], frame.shape[0])
        
        self.current_polygon = []
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.current_polygon.append((x, y))
            elif event == cv2.EVENT_RBUTTONDOWN:
                if len(self.current_polygon) > 2:
                    self.polygons.append(self.current_polygon.copy())
                    self.current_polygon = []
                    
        cv2.setMouseCallback('Draw Parking Regions', mouse_callback)
        
        while True:
            display = temp_frame.copy()
            for i, poly in enumerate(self.polygons):
                cv2.polylines(display, [np.array(poly)], True, (255, 0, 0), 2)
                cx = int(sum(p[0] for p in poly) / len(poly))
                cy = int(sum(p[1] for p in poly) / len(poly))
                cv2.putText(display, str(i + 1), (cx - 8, cy + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            if self.current_polygon:
                for i in range(len(self.current_polygon)):
                    cv2.circle(display, self.current_polygon[i], 3, (0, 0, 255), -1)
                    if i > 0:
                        cv2.line(display, self.current_polygon[i-1], self.current_polygon[i], (0, 0, 255), 2)
                        
            cv2.imshow('Draw Parking Regions', display)
            key = cv2.waitKey(20) & 0xFF
            
            if key == ord(' ') or key == 13 or key == ord('q'):
                break
            elif key == ord('c'):
                self.polygons.clear()
                self.current_polygon.clear()
            elif key == ord('z') or key == 8:
                if self.current_polygon: self.current_polygon.pop()
                elif self.polygons: self.polygons.pop()
                
        cv2.destroyWindow('Draw Parking Regions')
        cap.release()
        
        if self.polygons:
            self.show_save_preset_dialog()
            
    def show_save_preset_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Lưu Preset")
        dialog.resize(350, 180)
        layout = QVBoxLayout(dialog)
        
        lbl = QLabel("ĐẶT TÊN PRESET")
        lbl.setObjectName("HeaderLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        layout.addWidget(QLabel(f"Đã vẽ {len(self.polygons)} ô đỗ. Nhập tên:"))
        
        name_entry = QLineEdit(f"Preset_{datetime.now().strftime('%d%m_%H%M')}")
        layout.addWidget(name_entry)
        
        btn_save = QPushButton("Lưu")
        btn_save.setObjectName("SuccessBtn")
        layout.addWidget(btn_save)
        
        def on_save():
            name = name_entry.text().strip()
            if not name: return
            data = {
                "name": name,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "polygons": [list(map(list, poly)) for poly in self.polygons]
            }
            p = os.path.join(PRESETS_DIR, name + ".json")
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.current_preset_name = name
            QMessageBox.information(dialog, "Thành công", f"Đã lưu preset '{name}'!")
            dialog.accept()
            
        btn_save.clicked.connect(on_save)
        set_titlebar_theme(dialog, self.is_dark_mode)
        self.fade_in(dialog)
        dialog.exec()
        
    def start_detection(self):
        if self.detection_active: return
        
        if not self.video_path and not self.is_webcam:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn video trước!")
            return
        
        if not self.polygons:
            res = QMessageBox.question(self, "Cảnh báo", "Bạn chưa khoanh vùng nhận diện bãi đỗ nào!\nVideo sẽ chạy nhưng không hiện chỗ trống đậu xe. Bạn có muốn tiếp tục chạy luôn không?")
            if res == QMessageBox.StandardButton.No:
                return
            
        screen = QApplication.primaryScreen().geometry()
        self.worker = DetectionWorker(self, screen.width(), screen.height())
        self.worker.on_error.connect(lambda e: QMessageBox.critical(self, "Lỗi", e))
        self.worker.show_checkin_signal.connect(self.show_checkin_popup)
        self.worker.on_finished.connect(self._on_detection_finished)
        
        self.detection_active = True
        self.btn_detect.setText("ĐANG CHẠY...")
        self.btn_detect.setEnabled(False)
        self.btn_checkin.setEnabled(self.is_webcam)
        
        # Use python threading to avoid Qt Event Loop deadlock with cv2 UI functions
        t = threading.Thread(target=self.worker.run, daemon=True)
        t.start()
        
    def _on_detection_finished(self):
        self.detection_active = False
        self.btn_detect.setText("BẮT ĐẦU NHẬN DIỆN")
        self.btn_detect.setEnabled(True)
        self.btn_checkin.setEnabled(False)

    def get_current_customer_key(self):
        """Lấy private key của khách hàng hiện tại. Trả về None nếu là unlocked account."""
        custom_key = self.entry_cust_key.text().strip()
        if custom_key:
            if not custom_key.startswith("0x"):
                custom_key = "0x" + custom_key
            return custom_key
        idx = self.combo_wallets.currentIndex()
        if idx >= 0 and idx < len(self.customer_wallets):
            pk = self.customer_wallets[idx].get("private_key")
            if pk:
                return pk
            # Ganache unlocked account — trả về địa chỉ thay vì key
            return self.customer_wallets[idx]["address"]
        return None

    def _is_unlocked_account(self, key_or_addr):
        """Kiểm tra xem key_or_addr là private key hay là địa chỉ unlocked"""
        if not key_or_addr:
            return False
        return key_or_addr.startswith("0x") and len(key_or_addr) == 42

    def update_customer_wallet_info(self):
        custom_key = self.entry_cust_key.text().strip()
        address = "N/A"
        
        if custom_key:
            try:
                if not custom_key.startswith("0x"):
                    custom_key = "0x" + custom_key
                account = self.blockchain_mgr.w3.eth.account.from_key(custom_key)
                address = account.address
            except (ValueError, AttributeError):
                self.entry_cust_address.setText("Khóa bí mật không hợp lệ!")
                self.lbl_cust_balance.setText("0.0 ETH")
                return
        else:
            idx = self.combo_wallets.currentIndex()
            if idx >= 0 and idx < len(self.customer_wallets):
                wallet = self.customer_wallets[idx]
                address = wallet["address"]
                
        self.entry_cust_address.setText(address)
        
        # Cập nhật số dư ví khách hàng bất đồng bộ
        if self.blockchain_mgr.is_connected() and address != "N/A":
            balance = self.blockchain_mgr.get_balance(address)
            self.lbl_cust_balance.setText(f"{balance:.4f} ETH")
        else:
            self.lbl_cust_balance.setText("0.0 ETH")

    def set_dapp_buttons_enabled(self, enabled):
        self.btn_book.setEnabled(enabled)
        self.btn_cancel_book.setEnabled(enabled)
        self.btn_set_rate.setEnabled(enabled)
        self.btn_set_deposit.setEnabled(enabled)
        self.btn_withdraw.setEnabled(enabled)
        if enabled:
            self.btn_book.setText("Đặt Chỗ Trước (Nạp Cọc)")
            self.btn_cancel_book.setText("Hủy Đặt Chỗ (Hoàn Cọc)")
        else:
            self.btn_book.setText("Đang xử lý...")
            self.btn_cancel_book.setText("Đang xử lý...")

    def run_blockchain_action(self, action_func, success_callback, *args):
        """Chạy blockchain action trên background thread, trả kết quả về main thread qua signal."""
        self.set_dapp_buttons_enabled(False)
        
        # Lưu callback để gọi khi thành công
        callback_id = str(uuid.uuid4())[:8]
        self._bc_callbacks[callback_id] = success_callback
        
        def _worker():
            success = False
            msg = "Lỗi không xác định"
            try:
                print(f"[BC-Thread] Bắt đầu action: {action_func.__name__} args={args}")
                tx_hash, success, msg = action_func(*args)
                print(f"[BC-Thread] Kết quả: success={success}, msg={msg}, tx={tx_hash}")
                if not msg:
                    msg = f"Tx Hash: {tx_hash[:10]}..." if tx_hash else "Hoàn thành"
            except Exception as e:
                success = False
                msg = str(e)
                print(f"[BC-Thread] Exception: {e}")
            
            # Emit signal về main thread (thread-safe)
            try:
                self._bc_action_done.emit(success, msg, callback_id)
            except RuntimeError:
                print(f"[BC-Thread] Không thể emit signal (UI đã đóng?)")
        
        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_bc_action_done(self, success, msg, callback_id):
        """Slot xử lý kết quả blockchain action — LUÔN chạy trên main thread."""
        print(f"[BC-Main] Nhận kết quả: success={success}, msg={msg}")
        
        # Bật lại buttons
        self.set_dapp_buttons_enabled(True)
        self._update_blockchain_ui_async()
        
        # Hiển thị kết quả
        if success:
            QMessageBox.information(self, "Blockchain", msg)
            # Gọi success callback
            cb = self._bc_callbacks.pop(callback_id, None)
            if cb:
                try:
                    cb(msg)
                except Exception as cb_err:
                    print(f"[BC-Main] Callback error: {cb_err}")
        else:
            QMessageBox.warning(self, "Lỗi Blockchain", msg)
            self._bc_callbacks.pop(callback_id, None)

    def book_slot_action(self):
        try:
            slot_id = int(self.entry_book_slot.text())
            duration = float(self.entry_book_duration.text())
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Nhập liệu", "Vui lòng nhập ID ô đỗ và thời lượng hợp lệ!")
            return
        
        # Validation slot_id
        if slot_id <= 0:
            QMessageBox.warning(self, "Nhập liệu", "Slot ID phải lớn hơn 0!")
            return
        if self.polygons and slot_id > len(self.polygons):
            QMessageBox.warning(self, "Nhập liệu", f"Slot ID tối đa là {len(self.polygons)} (theo số ô đỗ đã vẽ)!")
            return
            
        private_key = self.get_current_customer_key()
        if not private_key:
            QMessageBox.warning(self, "Lỗi ví", "Chưa có cấu hình ví hợp lệ!")
            return
        
        # Kiểm tra booking trên blockchain trước khi đặt
        bc_booking = self.blockchain_mgr.get_booking_status(slot_id)
        if bc_booking and bc_booking[3]:  # active == True
            QMessageBox.warning(self, "Đã có đặt chỗ", f"Ô {slot_id} đã được đặt chỗ trên blockchain bởi {bc_booking[0][:10]}...!")
            return
            
        def on_success(msg):
            dep = self.blockchain_mgr.get_deposit_amount_eth()
            addr = self.entry_cust_address.text()
            self.db.record_booking(slot_id, addr, int(duration), dep)
            self.update_customer_wallet_info()
            self._refresh_slot_grid()
            self._refresh_bookings_table()
            self._add_event_log(f"📱 Đặt chỗ ô #{slot_id} — Ví: {addr[:10]}... — Cọc: {dep} ETH")
            
        self.run_blockchain_action(
            self.blockchain_mgr.book_slot_on_chain,
            on_success,
            private_key, slot_id, duration
        )

    def cancel_booking_action(self):
        try:
            slot_id = int(self.entry_book_slot.text())
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Nhập liệu", "Vui lòng nhập ID ô đỗ hợp lệ!")
            return
            
        private_key = self.get_current_customer_key()
        if not private_key:
            QMessageBox.warning(self, "Lỗi ví", "Chưa có cấu hình ví hợp lệ!")
            return
            
        def on_success(msg):
            self.db.cancel_booking(slot_id)
            self.update_customer_wallet_info()
            self._refresh_slot_grid()
            self._refresh_bookings_table()
            self._add_event_log(f"❌ Hủy đặt chỗ ô #{slot_id} — Hoàn cọc thành công")
            
        self.run_blockchain_action(
            self.blockchain_mgr.cancel_booking_on_chain,
            on_success,
            private_key, slot_id
        )

    def set_rate_action(self):
        try:
            rate = float(self.entry_rate.text())
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Nhập liệu", "Vui lòng nhập đơn giá hợp lệ!")
            return
            
        self.run_blockchain_action(
            self.blockchain_mgr.set_rate_on_chain,
            lambda msg: self._add_event_log(f"⚙️ Cập nhật đơn giá: {rate} ETH/min"),
            rate
        )

    def set_deposit_action(self):
        try:
            dep = float(self.entry_deposit.text())
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Nhập liệu", "Vui lòng nhập mức tiền cọc hợp lệ!")
            return
            
        self.run_blockchain_action(
            self.blockchain_mgr.set_deposit_amount_on_chain,
            lambda msg: self._add_event_log(f"⚙️ Cập nhật tiền cọc: {dep} ETH"),
            dep
        )

    def withdraw_revenues_action(self):
        # Kiểm tra trước: có doanh thu để rút không?
        revenue = self.blockchain_mgr.get_total_revenue()
        if revenue <= 0:
            QMessageBox.information(self, "Thông báo", "Hiện chưa có doanh thu để rút!\n\nDoanh thu được tạo khi xe check-out sau khi đỗ.")
            return
        
        def on_success(msg):
            self._add_event_log(f"💰 Rút doanh thu {revenue:.6f} ETH thành công!")
        self.run_blockchain_action(
            self.blockchain_mgr.withdraw_revenues_on_chain,
            on_success
        )

    def record_blockchain_event(self, slot_id, event_type, preset_name=""):
        # Chạy thread gửi giao dịch blockchain
        t = threading.Thread(
            target=self._async_record_blockchain_event,
            args=(slot_id, event_type, preset_name),
            daemon=True
        )
        t.start()

    def _async_record_blockchain_event(self, slot_id, event_type, preset_name):
        if not self.blockchain_mgr or not self.blockchain_mgr.is_connected():
            print(f"[WARNING] Blockchain không kết nối — bỏ qua ghi nhận {event_type} cho slot {slot_id}")
            return
        
        # Kiểm tra booking trước khi check-in
        if event_type.upper() == "IN":
            booking = self.db.get_active_booking(slot_id)
            if booking:
                print(f"[BOOKING MATCH] Slot {slot_id} đã được đặt bởi {booking['user_wallet']}")
            
        # Lấy vehicle_id hiện tại của slot từ database
        conn = self.db._get_conn()
        c = conn.cursor()
        c.execute("SELECT vehicle_id FROM slot_status WHERE slot_id = ?", (slot_id,))
        row = c.fetchone()
        vehicle_id = row["vehicle_id"] if row else ""
        conn.close()
        
        tx_hash, success, error_msg = self.blockchain_mgr.record_event_on_chain(
            slot_id, vehicle_id, event_type, preset_name
        )
        
        if success and tx_hash:
            if event_type.upper() == "IN":
                self.db.complete_booking(slot_id)
            self.db.update_latest_event_tx_hash(slot_id, event_type, tx_hash)
            self.update_blockchain_ui_signal.emit()
            
            # Emit event log
            now_str = datetime.now().strftime("%H:%M:%S")
            if event_type.upper() == "IN":
                log_msg = f"[{now_str}] 🚗 Xe VÀO ô #{slot_id} — ID: {vehicle_id} — Tx: {tx_hash[:10]}..."
            else:
                log_msg = f"[{now_str}] 🚙 Xe RA ô #{slot_id} — {error_msg} — Tx: {tx_hash[:10]}..."
            # Thread-safe emit to UI
            try:
                from PyQt6.QtCore import QMetaObject, Q_ARG
                QMetaObject.invokeMethod(self.event_log, "addItem", Qt.ConnectionType.QueuedConnection, Q_ARG(str, log_msg))
            except Exception:
                pass
        else:
            print(f"[BLOCKCHAIN] Lỗi ghi {event_type} cho slot {slot_id}: {error_msg}")

    # ─── Blockchain UI Update (Worker Thread) ───
    
    def _update_blockchain_ui_async(self):
        """Chạy RPC calls trong background thread, emit kết quả về main thread"""
        def _fetch():
            try:
                is_conn = self.blockchain_mgr.is_connected()
                data = {"connected": is_conn}
                if is_conn:
                    data["contract_addr"] = self.blockchain_mgr.get_contract_address()
                    data["wallet_addr"] = self.blockchain_mgr.get_system_wallet_address()
                    data["balance"] = self.blockchain_mgr.get_balance()
                    data["contract_balance"] = self.blockchain_mgr.get_contract_balance()
                    data["revenue"] = self.blockchain_mgr.get_total_revenue()
                    data["held_deposits"] = self.blockchain_mgr.get_total_held_deposits()
                    # Customer balance
                    cust_addr = self.entry_cust_address.text()
                    if cust_addr and cust_addr != "N/A" and not cust_addr.startswith("Khóa"):
                        data["cust_balance"] = self.blockchain_mgr.get_balance(cust_addr)
                    else:
                        data["cust_balance"] = 0.0
                return data
            except Exception as e:
                return {"connected": False, "error": str(e)}
        
        import concurrent.futures
        self._bc_executor = getattr(self, '_bc_executor', concurrent.futures.ThreadPoolExecutor(max_workers=1))
        future = self._bc_executor.submit(_fetch)
        future.add_done_callback(lambda f: self.update_blockchain_ui_signal.emit())
        self._bc_future_data = future

    def update_blockchain_ui(self):
        if not hasattr(self, 'lbl_bc_status'):
            return
        
        # Nếu có data từ background thread, dùng nó
        data = None
        if hasattr(self, '_bc_future_data') and self._bc_future_data.done():
            try:
                data = self._bc_future_data.result()
            except Exception:
                data = None
        
        if data and data.get("connected"):
            self.lbl_bc_status.setText("🟢 Đã kết nối Devnet")
            self.lbl_bc_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #2ecc71;")
            self.lbl_contract.setText(data.get("contract_addr", "N/A"))
            self.lbl_wallet.setText(data.get("wallet_addr", "N/A"))
            self.lbl_balance.setText(f"{data.get('balance', 0):.4f} ETH")
            self.lbl_contract_balance.setText(f"{data.get('contract_balance', 0):.6f} ETH")
            self.lbl_revenue.setText(f"{data.get('revenue', 0):.6f} ETH")
            self.lbl_held_deposits.setText(f"{data.get('held_deposits', 0):.6f} ETH")
            self.lbl_cust_balance.setText(f"{data.get('cust_balance', 0):.4f} ETH")
        elif data is not None:
            self.lbl_bc_status.setText("🔴 Mất kết nối")
            self.lbl_bc_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #e74c3c;")
            self.lbl_contract.setText("N/A")
            self.lbl_wallet.setText("N/A")
            self.lbl_balance.setText("0.0 ETH")
            self.lbl_contract_balance.setText("0.0 ETH")
            self.lbl_revenue.setText("0.0 ETH")
            self.lbl_held_deposits.setText("0.0 ETH")
        else:
            # Fallback: chạy đồng bộ nếu không có data từ async
            is_conn = self.blockchain_mgr.is_connected()
            if is_conn:
                self.lbl_bc_status.setText("🟢 Đã kết nối Devnet")
                self.lbl_bc_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #2ecc71;")
                self.lbl_contract.setText(self.blockchain_mgr.get_contract_address())
                self.lbl_wallet.setText(self.blockchain_mgr.get_system_wallet_address())
            else:
                self.lbl_bc_status.setText("🔴 Mất kết nối")
                self.lbl_bc_status.setStyleSheet("font-weight: bold; font-size: 13px; color: #e74c3c;")
        
        # Refresh slot grid and bookings table
        self._refresh_slot_grid()
        self._refresh_bookings_table()
    
    # ─── Slot Grid & Bookings Table Refresh ───
    
    def _add_event_log(self, msg):
        """Thêm một dòng vào log sự kiện (thread-safe nếu gọi từ main thread)"""
        now_str = datetime.now().strftime("%H:%M:%S")
        if not msg.startswith("["):
            msg = f"[{now_str}] {msg}"
        self.event_log.insertItem(0, msg)
        # Giữ tối đa 50 dòng
        while self.event_log.count() > 50:
            self.event_log.takeItem(self.event_log.count() - 1)
    
    def _refresh_slot_grid(self):
        """Cập nhật bảng trạng thái ô đỗ theo dữ liệu DB"""
        slots = self.db.get_slot_status_with_bookings()
        if not slots:
            return
        
        # Xóa layout cũ
        for i in reversed(range(self.slot_grid_layout.count())):
            w = self.slot_grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        
        cols = 4  # Số cột trong grid
        for i, s in enumerate(slots):
            slot_id = s["slot_id"]
            is_occ = s["is_occupied"]
            vid = s.get("vehicle_id") or ""
            bk_wallet = s.get("booking_wallet")
            bk_status = s.get("booking_status")
            
            frame = QFrame()
            frame.setFixedSize(120, 52)
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(6, 4, 6, 4)
            fl.setSpacing(1)
            
            if is_occ:
                frame.setStyleSheet("background-color: rgba(231, 76, 60, 0.15); border: 2px solid #e74c3c; border-radius: 6px;")
                lbl_slot = QLabel(f"#{slot_id} 🔴")
                lbl_detail = QLabel(vid[:10] if vid else "Có xe")
            elif bk_status == "ACTIVE":
                frame.setStyleSheet("background-color: rgba(241, 196, 15, 0.15); border: 2px solid #f1c40f; border-radius: 6px;")
                lbl_slot = QLabel(f"#{slot_id} 🟡")
                lbl_detail = QLabel(f"Đã đặt")
            else:
                frame.setStyleSheet("background-color: rgba(46, 204, 113, 0.15); border: 2px solid #2ecc71; border-radius: 6px;")
                lbl_slot = QLabel(f"#{slot_id} 🟢")
                lbl_detail = QLabel("Trống")
            
            lbl_slot.setStyleSheet("font-weight: bold; font-size: 13px; border: none; background: transparent;")
            lbl_detail.setStyleSheet("font-size: 10px; color: #888; border: none; background: transparent;")
            lbl_slot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fl.addWidget(lbl_slot)
            fl.addWidget(lbl_detail)
            
            self.slot_grid_layout.addWidget(frame, i // cols, i % cols)
    
    def _refresh_bookings_table(self):
        """Cập nhật bảng booking đang hoạt động"""
        bookings = self.db.get_all_active_bookings()
        self.table_bookings.setRowCount(len(bookings))
        
        for r, b in enumerate(bookings):
            def c_item(text):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                return item
            
            self.table_bookings.setItem(r, 0, c_item(f"Ô {b['slot_id']}"))
            wallet = b.get('user_wallet', '')
            self.table_bookings.setItem(r, 1, c_item(f"{wallet[:8]}..." if len(wallet) > 8 else wallet))
            self.table_bookings.setItem(r, 2, c_item(f"{b['duration_mins']} phút"))
            self.table_bookings.setItem(r, 3, c_item(f"{b['deposit_eth']} ETH"))
        
    def show_checkin_popup(self):
        if not self.detection_active or not self.is_webcam:
            QMessageBox.information(self, "Check In", "Chỉ hoạt động khi đang dùng Camera.")
            return
            
        status = self.last_poly_status
        if not status:
            QMessageBox.information(self, "Check In", "Chưa có dữ liệu. Vui lòng đợi...")
            return
            
        dialog = QDialog() # Independent window
        dialog.setWindowTitle("Check In")
        dialog.resize(420, 500)
        dialog.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(dialog)
        
        lbl = QLabel("TÌNH TRẠNG BÃI ĐỖ XE")
        lbl.setObjectName("HeaderLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        self.lbl_checkin_status = QLabel()
        layout.addWidget(self.lbl_checkin_status)
        
        self.sa_checkin = QScrollArea()
        self.sa_checkin.setWidgetResizable(True)
        layout.addWidget(self.sa_checkin)
        
        self.lbl_checkin_action = QLabel()
        self.lbl_checkin_action.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_checkin_action)
        
        def on_close():
            dialog.accept()
            try:
                cv2.setWindowProperty("Video Detection", cv2.WND_PROP_TOPMOST, 1)
                cv2.setWindowProperty("Video Detection", cv2.WND_PROP_TOPMOST, 0)
            except: pass

        btn = QPushButton("Đóng")
        btn.clicked.connect(on_close)
        layout.addWidget(btn)
        
        self.timer_checkin = QTimer(dialog)
        self.timer_checkin.timeout.connect(self._refresh_checkin)
        self.timer_checkin.start(1000)
        
        self._checkin_dialog = dialog
        self._refresh_checkin()
        set_titlebar_theme(dialog, self.is_dark_mode)
        self.fade_in(dialog)
        dialog.show()

    def _refresh_checkin(self):
        status = self.last_poly_status
        if getattr(self, '_checkin_dialog', None) is None or not self._checkin_dialog.isVisible() or not status:
            return
            
        empty_slots = [i+1 for i, occ in enumerate(status) if not occ]
        occ_slots = [i+1 for i, occ in enumerate(status) if occ]
        tot = len(status)
        
        self.lbl_checkin_status.setText(f"Trống: {len(empty_slots)}/{tot}   |   Đã đỗ: {len(occ_slots)}/{tot}")
        
        w = QWidget()
        wl = QVBoxLayout(w)
        
        for idx in range(tot):
            slot = idx + 1
            is_occ = status[idx]
            
            f = QFrame()
            f.setObjectName("MainFrame") # Reuse border style
            fl = QHBoxLayout(f)
            
            if is_occ:
                txt = f"🔴  Ô {slot}:  Đã có xe"
                col = "#e74c3c"
            else:
                txt = f"🟢  Ô {slot}:  Còn trống"
                col = "#27ae60"
                
            l = QLabel(txt)
            l.setStyleSheet(f"color: {col}; font-weight: bold; font-size: 14px;")
            fl.addWidget(l)
            wl.addWidget(f)
            
        wl.addStretch()
        self.sa_checkin.setWidget(w)
        
        if empty_slots:
            g = f"✅ Vui lòng tiến vào Ô {empty_slots[0]}."
            c = "#27ae60"
        else:
            g = "⛔ Bãi đỗ đã đầy."
            c = "#e74c3c"
            
        self.lbl_checkin_action.setText(g)
        self.lbl_checkin_action.setStyleSheet(f"color: {c}; font-weight: bold; font-size: 14px;")

    def show_dashboard(self):
        self.dash = QDialog()
        self.dash.setWindowTitle("📊 Báo Cáo & Thống Kê")
        self.dash.resize(650, 650)
        self.dash.setStyleSheet(self.styleSheet())
        layout = QVBoxLayout(self.dash)
        
        lbl = QLabel("BÁO CÁO & THỐNG KÊ")
        lbl.setObjectName("HeaderLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        # Thống kê hôm nay
        self.f_stats = QFrame()
        self.f_stats.setObjectName("MainFrame")
        sl = QHBoxLayout(self.f_stats)
        
        self.lbl_in = QLabel("Lượt vào: 0")
        self.lbl_out = QLabel("Lượt ra: 0")
        self.lbl_occ = QLabel("Đang đỗ: 0")
        for l in [self.lbl_in, self.lbl_out, self.lbl_occ]:
            l.setStyleSheet("font-size: 14px; font-weight: bold; color: #2980b9;" if not self.is_dark_mode else "font-size: 14px; font-weight: bold; color: #00a8ff;")
            sl.addWidget(l)
            
        current_date_str = datetime.now().strftime('%d/%m/%Y')
        layout.addWidget(QLabel(f"Thống kê hôm nay ({current_date_str})"))
        layout.addWidget(self.f_stats)
        
        # Thống kê Booking
        self.f_booking_stats = QFrame()
        self.f_booking_stats.setObjectName("MainFrame")
        bsl = QHBoxLayout(self.f_booking_stats)
        
        self.lbl_bk_total = QLabel("Tổng ĐC: 0")
        self.lbl_bk_active = QLabel("Đang giữ: 0")
        self.lbl_bk_completed = QLabel("Hoàn tất: 0")
        self.lbl_bk_cancelled = QLabel("Đã hủy: 0")
        for l in [self.lbl_bk_total, self.lbl_bk_active, self.lbl_bk_completed, self.lbl_bk_cancelled]:
            l.setStyleSheet("font-size: 12px; font-weight: bold; color: #8e44ad;" if not self.is_dark_mode else "font-size: 12px; font-weight: bold; color: #a29bfe;")
            bsl.addWidget(l)
        
        layout.addWidget(QLabel("Thống kê Đặt chỗ"))
        layout.addWidget(self.f_booking_stats)
        
        # Thống kê theo ô
        layout.addWidget(QLabel("Thống kê theo Ô đỗ"))
        self.table_slot = QTableWidget()
        self.table_slot.verticalHeader().setVisible(False)
        self.table_slot.setMinimumHeight(120)
        layout.addWidget(self.table_slot)
        
        # Lịch sử
        layout.addWidget(QLabel("Lịch sử gần nhất"))
        self.table_hist = QTableWidget()
        self.table_hist.verticalHeader().setVisible(False)
        self.table_hist.setMinimumHeight(150)
        layout.addWidget(self.table_hist)
        
        btn_clear = QPushButton("🗑️ Xóa Báo Cáo")
        btn_clear.setObjectName("DangerBtn")
        btn_clear.clicked.connect(self._clear_dashboard)
        layout.addWidget(btn_clear)
        
        self.timer = QTimer(self.dash)
        self.timer.timeout.connect(self._refresh_dashboard)
        self.timer.start(2000)
        
        self._refresh_dashboard()
        set_titlebar_theme(self.dash, self.is_dark_mode)
        self.fade_in(self.dash)
        self.dash.show()
        
    def _clear_dashboard(self):
        rep = QMessageBox.question(self.dash, "Xác nhận", "Xóa toàn bộ dữ liệu báo cáo?")
        if rep == QMessageBox.StandardButton.Yes:
            self.db.clear_all_data()
            self._refresh_dashboard()
            
    def _refresh_dashboard(self):
        try:
            stats = self.db.get_today_stats()
            self.lbl_in.setText(f"🚗 Lượt vào: {stats['total_in']}")
            self.lbl_out.setText(f"🚙 Lượt ra: {stats['total_out']}")
            self.lbl_occ.setText(f"🅿️ Đang đỗ: {stats['currently_occupied']}")
            
            # Booking stats
            bk_stats = self.db.get_booking_stats()
            self.lbl_bk_total.setText(f"📋 Tổng: {bk_stats['total']}")
            self.lbl_bk_active.setText(f"🟡 Giữ chỗ: {bk_stats['active']}")
            self.lbl_bk_completed.setText(f"✅ Hoàn tất: {bk_stats['completed']}")
            self.lbl_bk_cancelled.setText(f"❌ Đã hủy: {bk_stats['cancelled']}")
            
            def centered_item(text):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                return item
                
            summary = self.db.get_slot_summary()
            self.table_slot.setRowCount(len(summary))
            self.table_slot.setColumnCount(3)
            self.table_slot.setHorizontalHeaderLabels(["Ô đỗ", "Lượt vào", "Lượt ra"])
            self.table_slot.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            
            for r, row in enumerate(summary):
                self.table_slot.setItem(r, 0, centered_item(f"Ô {row['slot_id']}"))
                self.table_slot.setItem(r, 1, centered_item(str(row['total_in'])))
                self.table_slot.setItem(r, 2, centered_item(str(row['total_out'])))
            
            hist = self.db.get_history(15)
            self.table_hist.setRowCount(len(hist))
            self.table_hist.setColumnCount(7)
            self.table_hist.setHorizontalHeaderLabels(["Ngày", "Giờ", "Ô đỗ", "Xe", "Preset", "Sự kiện", "Blockchain Tx"])
            self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.table_hist.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            
            for r, ev in enumerate(hist):
                try:
                    dt = datetime.strptime(ev["timestamp"], "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%d/%m")
                    time_str = dt.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    date_str = ""
                    time_str = ev.get("timestamp", "")
                txt = "VÀO" if ev["event_type"] == "IN" else "RA"
                
                self.table_hist.setItem(r, 0, centered_item(date_str))
                self.table_hist.setItem(r, 1, centered_item(time_str))
                self.table_hist.setItem(r, 2, centered_item(f"Ô {ev['slot_id']}"))
                self.table_hist.setItem(r, 3, centered_item(ev.get("vehicle_id") or ""))
                self.table_hist.setItem(r, 4, centered_item(ev.get("preset_name") or ""))
                
                item_event = centered_item(txt)
                item_event.setForeground(QColor("#27ae60" if ev["event_type"] == "IN" else "#e67e22"))
                font = item_event.font()
                font.setBold(True)
                item_event.setFont(font)
                self.table_hist.setItem(r, 5, item_event)
                
                tx_hash_short = ""
                tx_full = ev.get("tx_hash") or ""
                if tx_full:
                    tx_hash_short = tx_full[:10] + "..."
                
                item_tx = centered_item(tx_hash_short)
                if tx_full:
                    item_tx.setToolTip(tx_full)
                    item_tx.setForeground(QColor("#3498db" if not self.is_dark_mode else "#00a8ff"))
                self.table_hist.setItem(r, 6, item_tx)
            
        except Exception as e:
            print(f"[Dashboard] Refresh error: {e}")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    # Fix for Windows Taskbar Icon
    myappid = 'vtio.parkingdetect.app.1'
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
    window = ParkingAppUI()
    window.show()
    sys.exit(app.exec())
