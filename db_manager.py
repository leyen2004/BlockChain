import sqlite3
import uuid
import os
from datetime import datetime


class ParkingDB:
    def __init__(self, db_path=None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "parking.db")
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS parking_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                vehicle_id TEXT,
                event_type TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now', 'localtime')),
                preset_name TEXT,
                tx_hash TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS slot_status (
                slot_id INTEGER PRIMARY KEY,
                is_occupied INTEGER DEFAULT 0,
                vehicle_id TEXT,
                last_updated TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS parking_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER NOT NULL,
                user_wallet TEXT NOT NULL,
                start_time TEXT DEFAULT (datetime('now', 'localtime')),
                duration_mins INTEGER NOT NULL,
                deposit_eth REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                tx_hash TEXT
            )
        """)
        conn.commit()
        
        # Migration: thêm cột mới nếu bảng đã tồn tại
        for col_query in [
            "ALTER TABLE parking_events ADD COLUMN tx_hash TEXT",
            "ALTER TABLE parking_bookings ADD COLUMN tx_hash TEXT",
        ]:
            try:
                c.execute(col_query)
                conn.commit()
            except sqlite3.OperationalError:
                pass
            
        conn.close()

    def _gen_vehicle_id(self):
        return "V-" + uuid.uuid4().hex[:4]

    def record_vehicle_in(self, slot_id, preset_name="", tx_hash=None, vehicle_id=None):
        """Ghi nhận xe vào ô đỗ. vehicle_id có thể truyền từ ngoài hoặc tự tạo UUID."""
        conn = self._get_conn()
        c = conn.cursor()
        vid = vehicle_id if vehicle_id else self._gen_vehicle_id()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO parking_events (slot_id, vehicle_id, event_type, timestamp, preset_name, tx_hash) VALUES (?, ?, 'IN', ?, ?, ?)",
            (slot_id, vid, now, preset_name, tx_hash)
        )
        c.execute(
            "INSERT OR REPLACE INTO slot_status (slot_id, is_occupied, vehicle_id, last_updated) VALUES (?, 1, ?, ?)",
            (slot_id, vid, now)
        )
        conn.commit()
        conn.close()
        return vid

    def record_vehicle_out(self, slot_id, preset_name="", tx_hash=None):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT vehicle_id FROM slot_status WHERE slot_id = ? AND is_occupied = 1", (slot_id,))
        row = c.fetchone()
        vid = row["vehicle_id"] if row else "unknown"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO parking_events (slot_id, vehicle_id, event_type, timestamp, preset_name, tx_hash) VALUES (?, ?, 'OUT', ?, ?, ?)",
            (slot_id, vid, now, preset_name, tx_hash)
        )
        c.execute(
            "INSERT OR REPLACE INTO slot_status (slot_id, is_occupied, vehicle_id, last_updated) VALUES (?, 0, NULL, ?)",
            (slot_id, now)
        )
        conn.commit()
        conn.close()
        return vid

    def update_latest_event_tx_hash(self, slot_id, event_type, tx_hash):
        """Cập nhật tx_hash cho sự kiện gần nhất của slot"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            UPDATE parking_events 
            SET tx_hash = ? 
            WHERE id = (
                SELECT id FROM parking_events 
                WHERE slot_id = ? AND event_type = ? 
                ORDER BY id DESC LIMIT 1
            )
        """, (tx_hash, slot_id, event_type))
        conn.commit()
        conn.close()

    def get_today_stats(self):
        conn = self._get_conn()
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*) as cnt FROM parking_events WHERE event_type='IN' AND timestamp LIKE ?", (today + "%",))
        total_in = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM parking_events WHERE event_type='OUT' AND timestamp LIKE ?", (today + "%",))
        total_out = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM slot_status WHERE is_occupied = 1")
        currently_occupied = c.fetchone()["cnt"]
        conn.close()
        return {
            "total_in": total_in,
            "total_out": total_out,
            "currently_occupied": currently_occupied
        }

    def get_history(self, limit=20):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM parking_events ORDER BY id DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_slot_summary(self):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT slot_id, 
                   SUM(CASE WHEN event_type='IN' THEN 1 ELSE 0 END) as total_in,
                   SUM(CASE WHEN event_type='OUT' THEN 1 ELSE 0 END) as total_out
            FROM parking_events
            GROUP BY slot_id
            ORDER BY slot_id
        """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def reset_slot_status(self, total_slots):
        """Reset toàn bộ slot_status khi bắt đầu session mới"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM slot_status")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i in range(1, total_slots + 1):
            c.execute(
                "INSERT INTO slot_status (slot_id, is_occupied, vehicle_id, last_updated) VALUES (?, 0, NULL, ?)",
                (i, now)
            )
        conn.commit()
        conn.close()

    def clear_all_data(self):
        """Xóa toàn bộ dữ liệu báo cáo"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM parking_events")
        c.execute("DELETE FROM slot_status")
        c.execute("DELETE FROM parking_bookings")
        conn.commit()
        conn.close()

    # ─── Booking Management ────────────────────────

    def record_booking(self, slot_id, user_wallet, duration_mins, deposit_eth, tx_hash=None):
        """Ghi nhận lượt đặt chỗ"""
        conn = self._get_conn()
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            INSERT INTO parking_bookings (slot_id, user_wallet, start_time, duration_mins, deposit_eth, status, tx_hash)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?)
        """, (slot_id, user_wallet, now, duration_mins, deposit_eth, tx_hash))
        conn.commit()
        conn.close()

    def cancel_booking(self, slot_id):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            UPDATE parking_bookings
            SET status = 'CANCELLED'
            WHERE slot_id = ? AND status = 'ACTIVE'
        """, (slot_id,))
        conn.commit()
        conn.close()

    def complete_booking(self, slot_id):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            UPDATE parking_bookings
            SET status = 'COMPLETED'
            WHERE slot_id = ? AND status = 'ACTIVE'
        """, (slot_id,))
        conn.commit()
        conn.close()

    def get_active_booking(self, slot_id):
        """Lấy booking active của ô đỗ"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT * FROM parking_bookings
            WHERE slot_id = ? AND status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1
        """, (slot_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_all_active_bookings(self):
        """Lấy tất cả booking đang hoạt động"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT * FROM parking_bookings
            WHERE status = 'ACTIVE'
            ORDER BY start_time DESC
        """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_booking_stats(self):
        """Thống kê booking: total/active/cancelled/completed"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM parking_bookings")
        total = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM parking_bookings WHERE status='ACTIVE'")
        active = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM parking_bookings WHERE status='CANCELLED'")
        cancelled = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM parking_bookings WHERE status='COMPLETED'")
        completed = c.fetchone()["cnt"]
        conn.close()
        return {
            "total": total,
            "active": active,
            "cancelled": cancelled,
            "completed": completed
        }

    def get_slot_status_with_bookings(self):
        """Kết hợp slot_status + parking_bookings cho bản đồ ô đỗ"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("""
            SELECT s.slot_id, s.is_occupied, s.vehicle_id, s.last_updated,
                   b.user_wallet as booking_wallet, b.duration_mins as booking_duration,
                   b.status as booking_status
            FROM slot_status s
            LEFT JOIN parking_bookings b ON s.slot_id = b.slot_id AND b.status = 'ACTIVE'
            ORDER BY s.slot_id
        """)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows
