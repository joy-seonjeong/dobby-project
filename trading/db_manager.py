import os
import sqlite3
from datetime import datetime

class TossDBManager:
    """
    SQLite DB를 활용하여 자산 기록을 영구 저장하고 쿼리하는 클래스입니다.
    """
    def __init__(self, db_path=None):
        if db_path is None:
            # 기본 경로는 trading/data/asset_history.db 입니다.
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_dir = os.path.join(current_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "asset_history.db")
        else:
            self.db_path = db_path
            
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """
        자산 이력 및 종목 이력 테이블을 초기화합니다.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 자산 변동 내역 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cash_krw REAL NOT NULL,
                    cash_usd REAL NOT NULL,
                    stock_purchase_krw REAL NOT NULL,
                    stock_purchase_usd REAL NOT NULL,
                    stock_eval_krw REAL NOT NULL,
                    stock_eval_usd REAL NOT NULL,
                    total_eval_krw REAL NOT NULL
                )
            """)
            
            # 2. 보유 종목 변동 내역 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS holding_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    market_country TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    purchase_price REAL NOT NULL,
                    last_price REAL NOT NULL,
                    eval_amount REAL NOT NULL,
                    profit_loss REAL NOT NULL,
                    profit_rate REAL NOT NULL
                )
            """)
            conn.commit()

    def save_asset_snapshot(self, summary, custom_timestamp=None):
        """
        TossAssetManager의 요약 정보를 DB에 저장합니다.
        """
        timestamp = custom_timestamp or datetime.now().isoformat()
        
        cash = summary.get("cash", {})
        totals = summary.get("stock_totals", {})
        items = summary.get("items", [])
        
        # 총 원화 환산 자산 계산 (자체 계산: 예수금_원화 + 주식평가_원화. 달러는 환율을 대강 적용하거나, 
        # 토스증권 API가 환율 정보를 주므로 이를 쓸 수도 있으나, 여기서는 단순히 평가액 정보를 활용)
        # holdings에 이미 total_purchase_krw, market_value_krw 등이 들어있음.
        # total_eval_krw = cash_krw + stock_eval_krw (달러 자산은 api가 알아서 krw로 환산한 것을 누적해준 값을 사용하거나
        # 혹은 임의 환율 1380을 임시로 곱해서 더해준다. holdings.get("marketValue") 안의 krw 합산을 사용하는 것이 가장 정확함)
        cash_krw = cash.get("krw", 0)
        cash_usd = cash.get("usd", 0)
        stock_purchase_krw = totals.get("total_purchase_krw", 0)
        stock_purchase_usd = totals.get("total_purchase_usd", 0)
        stock_eval_krw = totals.get("market_value_krw", 0)
        stock_eval_usd = totals.get("market_value_usd", 0)
        
        # 전체 자산 평가액 = 예수금_원화 + 주식평가_원화 (여기에 달러 예수금을 임시로 1380원 곱해서 가산)
        total_eval_krw = cash_krw + stock_eval_krw + (cash_usd * 1380.0)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. asset_history 적재
            cursor.execute("""
                INSERT INTO asset_history (
                    timestamp, cash_krw, cash_usd, 
                    stock_purchase_krw, stock_purchase_usd, 
                    stock_eval_krw, stock_eval_usd, total_eval_krw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, cash_krw, cash_usd, 
                stock_purchase_krw, stock_purchase_usd, 
                stock_eval_krw, stock_eval_usd, total_eval_krw
            ))
            
            # 2. holding_history 적재
            for item in items:
                cursor.execute("""
                    INSERT INTO holding_history (
                        timestamp, symbol, name, market_country, currency,
                        quantity, purchase_price, last_price, eval_amount,
                        profit_loss, profit_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    item.get("symbol"),
                    item.get("name"),
                    item.get("country"),
                    item.get("currency"),
                    item.get("quantity"),
                    item.get("purchase_price"),
                    item.get("last_price"),
                    item.get("market_value"),
                    item.get("profit_loss"),
                    item.get("profit_rate")
                ))
            
            conn.commit()
        return timestamp

    def get_asset_history(self, limit=30):
        """
        최근 자산 추이를 조회합니다. (차트 시각화용)
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, cash_krw, cash_usd, stock_eval_krw, stock_eval_usd, total_eval_krw
                FROM asset_history
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_latest_holdings(self):
        """
        가장 최근 적재된 보유 종목들을 조회합니다.
        """
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. 가장 최신의 타임스탬프 구하기
            cursor.execute("SELECT MAX(timestamp) FROM holding_history")
            latest_time = cursor.fetchone()[0]
            
            if not latest_time:
                return []
                
            # 2. 해당 타임스탬프의 종목들 조회
            cursor.execute("""
                SELECT symbol, name, market_country, currency, quantity, 
                       purchase_price, last_price, eval_amount, profit_loss, profit_rate
                FROM holding_history
                WHERE timestamp = ?
            """, (latest_time,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
