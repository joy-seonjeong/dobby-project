import os
import sys
import json
import argparse
import requests
import pytz
import time
from datetime import datetime
from dotenv import load_dotenv
from asset_manager import TossAssetManager

# .env 로드
load_dotenv()

STATUS_FILE_NAME = "infinite_buying_status.json"

class TossInfiniteBuyingBot:
    """
    토스증권 OpenAPI를 연동하여 라오어의 무한매수법에 따른 자동 매매를 수행하는 봇입니다.
    (다중 종목 통합 탭 지원 단일 대시보드 리포터 연동)
    """
    def __init__(self, symbol: str, is_dry_run: bool = True, gemini_monthly_fee: float = 20.0, transaction_fee_rate: float = 0.001, tax_rate: float = 0.0000278):
        self.symbol = symbol.upper()
        self.is_dry_run = is_dry_run
        
        # 비용 및 수수료 설정
        self.gemini_monthly_fee = gemini_monthly_fee
        self.transaction_fee_rate = transaction_fee_rate
        self.tax_rate = tax_rate
        
        # 텔레그램 설정 로드
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        try:
            self.asset_manager = TossAssetManager()
        except Exception as e:
            if not self.is_dry_run:
                self.send_telegram_notification(f"⚠️ [경고] TossAssetManager 초기화 실패: {e}")
            self.asset_manager = None
            
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.status_file_path = os.path.join(self.current_dir, "data", STATUS_FILE_NAME)
        
        self.virtual_history_path = os.path.join(self.current_dir, "data", f"{self.symbol}_10_virtual_history.json")
        self.dashboard_path = os.path.join(self.current_dir, "data", "virtual_trading_report.html")
        
        os.makedirs(os.path.join(self.current_dir, "data"), exist_ok=True)
        self.status = self.load_status()
        
    def send_telegram_notification(self, message: str):
        """
        텔레그램 메신저로 봇의 구동 로그 및 긴급 상황 알림을 즉시 발송합니다.
        """
        print(f"📢 [Telegram 알림 전송 시도] {message}")
        if not self.telegram_token or not self.telegram_chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": f"🤖 [무한매수법 봇 - {self.symbol}]\n{message}"
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ 텔레그램 알림 API 오류: {e}")
            
    def load_status(self):
        if os.path.exists(self.status_file_path):
            with open(self.status_file_path, "r", encoding="utf-8") as f:
                try:
                    all_status = json.load(f)
                    if self.symbol in all_status:
                        return all_status[self.symbol]
                except Exception as e:
                    print(f"⚠️ 상태 파일 로드 오류: {e}")
                    
        default_status = {
            "capital": 1600.0,
            "divisions": 10,
            "one_time_limit": 160.0,
            "step": 0,
            "holdings": 0.0,
            "average_price": 0.0,
            "total_purchase_amount": 0.0,
            
            # 순자산 계정
            "net_cash": 1600.0,
            "net_holdings": 0.0,
            "net_average_price": 0.0,
            "net_total_purchase": 0.0,
            
            "last_trade_date": None
        }
        return default_status
        
    def save_status(self):
        all_status = {}
        if os.path.exists(self.status_file_path):
            with open(self.status_file_path, "r", encoding="utf-8") as f:
                try:
                    all_status = json.load(f)
                except Exception:
                    pass
                    
        all_status[self.symbol] = self.status
        
        with open(self.status_file_path, "w", encoding="utf-8") as f:
            json.dump(all_status, f, indent=4, ensure_ascii=False)
        print(f"💾 {self.symbol} 상태 저장: step={self.status['step']}, holdings={self.status['holdings']:.2f}주, 평단가=${self.status['average_price']:.2f}")

    def sync_state_with_broker(self):
        print(f"\n🔄 [싱크] {self.symbol} 계좌 잔고 동기화 중...")
        if self.is_dry_run or not self.asset_manager:
            return
            
        try:
            holdings_info = None
            for attempt in range(1, 4):
                try:
                    holdings_info = self.asset_manager.get_holdings(symbol=self.symbol)
                    if holdings_info:
                        break
                except Exception as e:
                    print(f"⚠️ [재시도 {attempt}/3] 계좌 잔고 조회 실패: {e}")
                    if attempt < 3:
                        time.sleep(2.0)
                    else:
                        raise e
            
            items = holdings_info.get("items", [])
            target_item = None
            for item in items:
                if item.get("symbol") == self.symbol:
                    target_item = item
                    break
            
            if not target_item:
                if self.status["holdings"] > 0:
                    msg = f"🎉 [실전 익절 성공!] 보유량이 0입니다. 익절 지정가 매도 완료 판정 및 사이클을 자동 리셋합니다."
                    print(msg)
                    self.send_telegram_notification(msg)
                    self.reset_cycle()
                else:
                    self.status["step"] = 0
                    self.status["holdings"] = 0.0
                    self.status["average_price"] = 0.0
                    self.status["total_purchase_amount"] = 0.0
            else:
                broker_qty = float(target_item.get("quantity", 0))
                broker_avg_price = float(target_item.get("averagePurchasePrice", 0))
                
                print(f"📊 [실계좌 확인] 보유 잔고: {broker_qty:.2f}주, 평단가: ${broker_avg_price:.2f}")
                
                if broker_qty > self.status["holdings"]:
                    print(f"📈 [추가 체결] 수량 증가 감지: {self.status['holdings']:.2f}주 -> {broker_qty:.2f}주")
                    if self.status["step"] == 0:
                        self.status["step"] = 1
                    else:
                        self.status["step"] += 1
                        
                self.status["holdings"] = broker_qty
                self.status["average_price"] = broker_avg_price
                self.status["total_purchase_amount"] = broker_qty * broker_avg_price
            self.save_status()
        except Exception as e:
            err_msg = f"❌ 계좌 동기화 실패: {e}. 로컬 데이터를 사용해 가상 구동을 유지합니다."
            print(err_msg)
            self.send_telegram_notification(err_msg)

    def reset_cycle(self):
        print(f"🔄 [리셋] {self.symbol} 무한매수법 사이클 리셋")
        self.status["step"] = 0
        self.status["holdings"] = 0.0
        self.status["average_price"] = 0.0
        self.status["total_purchase_amount"] = 0.0
        self.status["net_holdings"] = 0.0
        self.status["net_average_price"] = 0.0
        self.status["net_total_purchase"] = 0.0
        self.save_status()

    def get_current_price(self):
        for attempt in range(1, 4):
            try:
                import yfinance as yf
                ticker = yf.Ticker(self.symbol)
                price = ticker.fast_info.last_price
                if price:
                    return float(price)
            except Exception as e:
                print(f"⚠️ [재시도 {attempt}/3] yfinance 현재가 조회 실패: {e}")
                if attempt < 3:
                    time.sleep(2.0)
        return 76.76 if self.symbol == "TQQQ" else 29.47

    def get_exchange_rate(self):
        for attempt in range(1, 4):
            try:
                import yfinance as yf
                rate = yf.Ticker("USDKRW=X").fast_info.last_price
                if rate:
                    return float(rate)
            except Exception as e:
                print(f"⚠️ [재시도 {attempt}/3] yfinance 환율 조회 실패: {e}")
                if attempt < 3:
                    time.sleep(2.0)
        return 1380.0

    def place_toss_order(self, quantity: float, price: float, side: str, order_type: str = "LIMIT", time_in_force: str = "DAY"):
        if self.is_dry_run:
            print(f"🛡️ [DRY RUN 가상 주문] {side} {self.symbol} {quantity:.2f}주 @ ${price:.2f} (TIF: {time_in_force})")
            return {"status": "success", "orderId": "mock_order_id"}
            
        url = f"{self.asset_manager.base_url}/api/v1/orders"
        headers = self.asset_manager._get_headers()
        tif_param = "CLS" if time_in_force.upper() == "LOC" else time_in_force.upper()
        payload = {
            "symbol": self.symbol,
            "side": side.upper(),
            "orderType": order_type.upper(),
            "timeInForce": tif_param,
            "quantity": str(quantity),
            "price": str(round(price, 2))
        }
        
        for attempt in range(1, 4):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                if response.status_code == 200:
                    msg = f"✅ [주문 성공] {side} {self.symbol} {quantity:.2f}주 @ ${price:.2f} 주문 접수 완료!"
                    print(msg)
                    self.send_telegram_notification(msg)
                    return response.json()
                else:
                    print(f"⚠️ [주문 실패 시도 {attempt}/3] 상태코드 {response.status_code}: {response.text}")
            except Exception as e:
                print(f"⚠️ [주문 API 에러 시도 {attempt}/3]: {e}")
                
            if attempt < 3:
                time.sleep(3.0 * attempt)
                
        err_msg = f"❌ [주문 최종 실패] {side} {self.symbol} {quantity:.2f}주 주문이 3회 재시도에도 불구하고 실패했습니다."
        print(err_msg)
        self.send_telegram_notification(err_msg)
        return None

    def update_virtual_history(self, current_price: float, is_bought: bool, is_sold: bool, buy_qty: float = 0, sell_qty: float = 0, sell_price: float = 0, action_type: str = "대기"):
        ny_tz = pytz.timezone("America/New_York")
        today_str = datetime.now(ny_tz).strftime("%Y-%m-%d")
        exchange_rate = self.get_exchange_rate()
        
        history_list = []
        if os.path.exists(self.virtual_history_path):
            with open(self.virtual_history_path, "r", encoding="utf-8") as f:
                try:
                    history_list = json.load(f)
                except Exception:
                    pass
                    
        history_list = [h for h in history_list if h["date"] != today_str]
        
        if history_list:
            last_date_str = history_list[-1]["date"]
            last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d")
            today_ny_obj = datetime.now(ny_tz)
            if today_ny_obj.month != last_date_obj.month:
                print(f"💸 [비용 청구] Gemini 월 구독료 ${self.gemini_monthly_fee:.2f}가 가상 차감되었습니다.")
                self.status["net_cash"] -= self.gemini_monthly_fee
                
        if is_bought and buy_qty > 0:
            buy_amt = buy_qty * current_price
            fee = buy_amt * self.transaction_fee_rate
            self.status["net_cash"] -= (buy_amt + fee)
            self.status["net_holdings"] += buy_qty
            self.status["net_total_purchase"] += (buy_amt + fee)
            self.status["net_average_price"] = self.status["net_total_purchase"] / self.status["net_holdings"]
            print(f"📈 [가상 매수 정산] {buy_qty:.2f}주 매수 (수수료 ${fee:.2f} 차감 반영)")
            
        if is_sold and sell_qty > 0:
            gross_revenue = sell_qty * sell_price
            fee = gross_revenue * self.transaction_fee_rate
            tax = gross_revenue * self.tax_rate
            net_revenue = gross_revenue - fee - tax
            self.status["net_cash"] += net_revenue
            print(f"🎉 [가상 익절 정산] {sell_qty:.2f}주 매도 완료 (수수료/세금 ${fee+tax:.2f} 차감 반영)")
            self.status["net_holdings"] = 0.0
            self.status["net_total_purchase"] = 0.0
            self.status["net_average_price"] = 0.0
            
        portfolio_value = self.status["holdings"] * current_price
        total_assets = (self.status["capital"] - self.status["total_purchase_amount"]) + portfolio_value
        
        net_portfolio_value = self.status["net_holdings"] * current_price
        net_total_assets = self.status["net_cash"] + net_portfolio_value
        
        total_assets_krw = total_assets * exchange_rate
        net_assets_krw = net_total_assets * exchange_rate
        
        action_qty = buy_qty if is_bought else (sell_qty if is_sold else 0.0)
        action_price = current_price if is_bought else (sell_price if is_sold else 0.0)
        action_amount = (buy_qty * current_price) if is_bought else ((sell_qty * sell_price) if is_sold else 0.0)
        
        today_record = {
            "date": today_str,
            "close": round(current_price, 2),
            "exchange_rate": round(exchange_rate, 2),
            "step": self.status["step"],
            "holdings": round(self.status["holdings"], 2),
            "average_price": round(self.status["average_price"], 2),
            "total_assets": round(total_assets, 2),
            "net_assets": round(net_total_assets, 2),
            "total_assets_krw": round(total_assets_krw),
            "net_assets_krw": round(net_assets_krw),
            "profit_rate_pct": round(((total_assets - self.status["capital"]) / self.status["capital"]) * 100, 2),
            "net_profit_rate_pct": round(((net_total_assets - self.status["capital"]) / self.status["capital"]) * 100, 2),
            
            "action_type": action_type,
            "action_qty": round(action_qty, 2),
            "action_price": round(action_price, 2),
            "action_amount": round(action_amount, 2)
        }
        
        history_list.append(today_record)
        
        with open(self.virtual_history_path, "w", encoding="utf-8") as f:
            json.dump(history_list, f, indent=4, ensure_ascii=False)
            
        print(f"📊 [{self.symbol} 가상자산 현황] 세전: ${today_record['total_assets']:.2f} (약 {today_record['total_assets_krw']:,}원 | {today_record['profit_rate_pct']:+}%)\n"
              f"                     비용차감 후 순자산: ${today_record['net_assets']:.2f} (약 {today_record['net_assets_krw']:,}원 | {today_record['net_profit_rate_pct']:+}%)")
              
        self.generate_virtual_dashboard()

    def generate_virtual_dashboard(self):
        """
        활성화된 모든 종목(TQQQ, SOXL)의 기록을 파싱하여 단일 다중 탭 HTML 대시보드를 생성합니다.
        """
        all_status = {}
        if os.path.exists(self.status_file_path):
            with open(self.status_file_path, "r", encoding="utf-8") as f:
                try:
                    all_status = json.load(f)
                except Exception:
                    pass
                    
        dashboard_data = {}
        for sym in all_status.keys():
            history_path = os.path.join(self.current_dir, "data", f"{sym}_10_virtual_history.json")
            if os.path.exists(history_path):
                with open(history_path, "r", encoding="utf-8") as f:
                    try:
                        hist = json.load(f)
                        dashboard_data[sym] = {
                            "status": all_status[sym],
                            "history": hist
                        }
                    except Exception:
                        pass
                        
        if not dashboard_data:
            return
            
        # 첫 번째 로드할 디폴트 탭 지정 (실행된 symbol 우선)
        default_symbol = self.symbol if self.symbol in dashboard_data else list(dashboard_data.keys())[0]
        
        dashboard_data_json = json.dumps(dashboard_data, ensure_ascii=False)
        
        html_template = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>무한매수법 실시간 모의투자 대시보드</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+KR:wght@300;400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #151d30;
            --border-color: #223049;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Outfit', 'Noto Sans KR', sans-serif;
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        @media (max-width: 768px) {{
            header {{ flex-direction: column; align-items: flex-start; gap: 1rem; }}
        }}

        header h1 {{
            font-size: 2rem;
            background: linear-gradient(to right, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        header p {{ color: var(--text-secondary); font-size: 1rem; margin-top: 0.25rem; }}

        /* 탭 스타일 */
        .tabs {{
            display: flex;
            gap: 0.75rem;
        }}

        .tab-btn {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.6rem 1.5rem;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 0.75rem;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
        }}

        .tab-btn:hover {{
            border-color: var(--accent-blue);
            color: var(--text-primary);
        }}

        .tab-btn.active {{
            background-color: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }}
        
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .kpi-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .kpi-title {{ font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 0.5rem; }}
        .kpi-value {{ font-size: 1.8rem; font-weight: 700; }}
        .kpi-value.positive {{ color: var(--accent-green); }}
        .kpi-value.negative {{ color: var(--accent-red); }}
        .kpi-sub {{ font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.35rem; font-weight: 500; }}

        .layout {{ display: grid; grid-template-columns: 2.5fr 1fr; gap: 2rem; }}
        @media (max-width: 900px) {{ .layout {{ grid-template-columns: 1fr; }} }}

        .panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 2rem;
            margin-bottom: 2rem;
        }}

        .panel-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--accent-blue);
            padding-left: 0.75rem;
        }}

        .chart-container {{ position: relative; height: 380px; width: 100%; }}
        .stat-list {{ list-style: none; }}
        .stat-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.85rem 0;
            border-bottom: 1px solid var(--border-color);
        }}

        .stat-item:last-child {{ border-bottom: none; }}
        .stat-label {{ color: var(--text-secondary); }}
        .stat-val {{ font-weight: 600; }}

        .notice-card {{
            background-color: rgba(96, 165, 250, 0.05);
            border: 1px dashed var(--accent-blue);
            border-radius: 0.75rem;
            padding: 1.25rem;
            margin-top: 1.5rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}

        .log-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            margin-top: 1rem;
        }}

        .log-table th, .log-table td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .log-table th {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            font-weight: 600;
        }}

        .log-table td {{
            font-size: 0.95rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>무한매수법 실시간 모의투자 대시보드</h1>
                <p>하루 최대 1주 매수 룰 적용 (달러/원화 실시간 병기 및 거래 일지 제공)</p>
            </div>
            
            <!-- 탭 영역 -->
            <div class="tabs" id="tabContainer"></div>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">총 설정 원금</div>
                <div class="kpi-value" id="kpiCapital">$0.00</div>
                <div class="kpi-sub" id="kpiCapitalKrw">≈ 0 원</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">세전 가상자산</div>
                <div class="kpi-value" id="kpiRawAssets" style="color: #60a5fa">$0.00 (+0%)</div>
                <div class="kpi-sub" id="kpiRawAssetsKrw">≈ 0 원</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">순자산 (비용 차감 후)</div>
                <div class="kpi-value" id="kpiNetAssets">$0.00 (+0%)</div>
                <div class="kpi-sub" id="kpiNetAssetsKrw" style="color: var(--accent-green)">≈ 0 원</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">현재가 / 환율</div>
                <div class="kpi-value" id="kpiClose" style="color: var(--accent-purple)">$0.00</div>
                <div class="kpi-sub" id="kpiRate">0.00 원/$</div>
            </div>
        </div>

        <div class="layout">
            <div class="panel">
                <div class="panel-title">실시간 가상 자산 변화 곡선</div>
                <div class="chart-container">
                    <canvas id="virtualChart"></canvas>
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">현재 가상 투자 통계</div>
                <ul class="stat-list">
                    <li class="stat-item">
                        <span class="stat-label">현재 가상 진행 회차</span>
                        <span class="stat-val" id="statStep">0 / 10회차</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">가상 보유량</span>
                        <span class="stat-val" id="statHoldings">0.00주</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">가상 보유 평단가</span>
                        <span class="stat-val" id="statAveragePrice">$0.00 (약 0원)</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">순현금 보유액</span>
                        <span class="stat-val" id="statNetCash">$0.00 (약 0원)</span>
                    </li>
                </ul>
                <div class="notice-card">
                    💡 <b>비용 반영 기준 안내:</b><br>
                    * 거래 수수료: 매수/매도 시 0.07% 차감<br>
                    * 매도 제세금: 0.00278% 차감<br>
                    * Gemini 구독 요금: 매월 첫 영업일 $20.00 고정 차감
                </div>
            </div>
        </div>

        <div class="panel" style="margin-top: 1rem;">
            <div class="panel-title">실시간 가상 거래 일지 (Mock Trading Log)</div>
            <table class="log-table">
                <thead>
                    <tr>
                        <th>날짜</th>
                        <th>거래 구분</th>
                        <th>체결 수량</th>
                        <th>체결 단가</th>
                        <th>총 거래금액</th>
                        <th>적용 환율</th>
                    </tr>
                </thead>
                <tbody id="logTableBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        const dashboardData = {dashboard_data_json};
        let currentChart = null;

        // 동적으로 탭 생성
        const tabContainer = document.getElementById('tabContainer');
        Object.keys(dashboardData).forEach((symbol, index) => {{
            const btn = document.createElement('button');
            btn.className = `tab-btn ${{symbol === '{default_symbol}' ? 'active' : ''}}`;
            btn.innerText = symbol;
            btn.onclick = () => switchTab(symbol, btn);
            tabContainer.appendChild(btn);
        }});

        // 초기 화면 렌더링
        switchTab('{default_symbol}');

        function switchTab(symbol, targetBtn = null) {{
            // 탭 버튼 active 클래스 제어
            if (targetBtn) {{
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                targetBtn.classList.add('active');
            }}

            const data = dashboardData[symbol];
            const status = data.status;
            const history = data.history;
            const latest = history[history.length - 1];

            const exRate = latest.exchange_rate;

            // KPI 값 갱신
            document.getElementById('kpiCapital').innerText = `$${{status.capital.toFixed(2)}}`;
            document.getElementById('kpiCapitalKrw').innerText = `≈ ${{Math.round(status.capital * exRate).toLocaleString()}} 원`;

            const rawPct = latest.profit_rate_pct;
            document.getElementById('kpiRawAssets').innerText = `$${{latest.total_assets.toFixed(2)}} (${{rawPct >= 0 ? '+' : ''}}${{rawPct}}%)`;
            document.getElementById('kpiRawAssetsKrw').innerText = `≈ ${{latest.total_assets_krw.toLocaleString()}} 원`;

            const netPct = latest.net_profit_rate_pct;
            const netKpi = document.getElementById('kpiNetAssets');
            netKpi.innerText = `$${{latest.net_assets.toFixed(2)}} (${{netPct >= 0 ? '+' : ''}}${{netPct}}%)`;
            if (netPct >= 0) {{
                netKpi.className = 'kpi-value positive';
            }} else {{
                netKpi.className = 'kpi-value negative';
            }}
            document.getElementById('kpiNetAssetsKrw').innerText = `≈ ${{latest.net_assets_krw.toLocaleString()}} 원`;

            document.getElementById('kpiClose').innerText = `$${{latest.close.toFixed(2)}}`;
            document.getElementById('kpiRate').innerText = `${{exRate.toFixed(2)}} 원/$`;

            // 통계 표 갱신
            document.getElementById('statStep').innerText = `${{status.step}} / 10회차`;
            document.getElementById('statHoldings').innerText = `${{status.holdings.toFixed(2)}}주`;
            document.getElementById('statAveragePrice').innerText = `$${{status.average_price.toFixed(2)}} (약 ${{Math.round(status.average_price * exRate).toLocaleString()}}원)`;
            document.getElementById('statNetCash').innerText = `$${{status.net_cash.toFixed(2)}} (약 ${{Math.round(status.net_cash * exRate).toLocaleString()}}원)`;

            // 거래 일지 갱신
            const tbody = document.getElementById('logTableBody');
            tbody.innerHTML = '';
            
            // 최신순 정렬
            const reversedHist = [...history].reverse();
            reversedHist.forEach(h => {{
                const actType = h.action_type || '대기';
                let badgeColor = 'var(--accent-blue)';
                if (actType.includes('매수')) badgeColor = 'var(--accent-green)';
                else if (actType.includes('매도') || actType.includes('익절')) badgeColor = 'var(--accent-red)';
                else if (actType.includes('대기')) badgeColor = 'var(--text-secondary)';

                const qtyStr = h.action_qty > 0 ? `${{h.action_qty.toFixed(2)}}주` : '-';
                const priceStr = h.action_price > 0 ? `$${{h.action_price.toFixed(2)}}` : '-';
                const amtStr = h.action_amount > 0 ? `$${{h.action_amount.toFixed(2)}}` : '-';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="font-family: 'Outfit', sans-serif;">${{h.date}}</td>
                    <td><span style="background-color: ${{badgeColor}}33; color: ${{badgeColor}}; padding: 0.25rem 0.6rem; border-radius: 0.5rem; font-size: 0.85rem; font-weight: 700;">${{actType}}</span></td>
                    <td style="font-family: 'Outfit', sans-serif;">${{qtyStr}}</td>
                    <td style="font-family: 'Outfit', sans-serif;">${{priceStr}}</td>
                    <td style="font-family: 'Outfit', sans-serif;">${{amtStr}}</td>
                    <td style="font-family: 'Outfit', sans-serif; color: var(--text-secondary);">${{h.exchange_rate.toFixed(2)}} 원</td>
                `;
                tbody.appendChild(tr);
            }});

            // 차트 갱신
            renderChart(symbol, history);
        }}

        function renderChart(symbol, history) {{
            const dates = history.map(h => h.date);
            const rawAssets = history.map(h => h.total_assets);
            const netAssets = history.map(h => h.net_assets);
            const prices = history.map(h => h.close);
            const rates = history.map(h => h.exchange_rate || 1380.0);

            if (currentChart) {{
                currentChart.destroy();
            }}

            const ctx = document.getElementById('virtualChart').getContext('2d');
            currentChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [
                        {{
                            label: '세전 가상자산 ($)',
                            data: rawAssets,
                            borderColor: '#60a5fa',
                            borderWidth: 2,
                            fill: false,
                            yAxisID: 'y-assets',
                            pointRadius: 3
                        }},
                        {{
                            label: '비용 차감 후 순자산 ($)',
                            data: netAssets,
                            borderColor: '#34d399',
                            borderWidth: 2.5,
                            fill: false,
                            yAxisID: 'y-assets',
                            pointRadius: 3
                        }},
                        {{
                            label: `${{symbol}} 주가 ($)`,
                            data: prices,
                            borderColor: 'rgba(139, 92, 246, 0.4)',
                            borderWidth: 1.5,
                            borderDash: [4, 4],
                            fill: false,
                            yAxisID: 'y-price',
                            pointRadius: 0
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{ mode: 'index', intersect: false }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    let label = context.dataset.label || '';
                                    if (label) label += ': ';
                                    if (context.parsed.y !== null) {{
                                        const val = context.parsed.y;
                                        label += '$' + val.toFixed(2);
                                        
                                        if (context.datasetIndex === 0 || context.datasetIndex === 1) {{
                                            const rate = rates[context.dataIndex];
                                            const krwVal = Math.round(val * rate);
                                            label += ' (약 ' + krwVal.toLocaleString() + '원)';
                                        }}
                                    }}
                                    return label;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        'y-assets': {{
                            type: 'linear',
                            position: 'left',
                            ticks: {{ color: '#9ca3af' }},
                            title: {{ display: true, text: '자산 가치 ($)', color: '#9ca3af' }}
                        }},
                        'y-price': {{
                            type: 'linear',
                            position: 'right',
                            grid: {{ drawOnChartArea: false }},
                            ticks: {{ color: '#9ca3af' }},
                            title: {{ display: true, text: '주가 ($)', color: '#9ca3af' }}
                        }},
                        x: {{ ticks: {{ color: '#9ca3af' }} }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
        """
        
        with open(self.dashboard_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"✨ 통합 다중 탭 실시간 가상 대시보드 업데이트 완료! 파일 경로:\n   {self.dashboard_path}")

    def execute_daily_trade(self):
        """
        매일 실행되는 무한매수법 거래 로직을 수행합니다.
        """
        ny_tz = pytz.timezone("America/New_York")
        print(f"\n🚀 === [무한매수법 실행] 종목: {self.symbol} | 모드: {'DRY-RUN(가상)' if self.is_dry_run else 'REAL(실전)'} | 뉴욕시간: {datetime.now(ny_tz).strftime('%Y-%m-%d %H:%M:%S')} ===")
        
        self.sync_state_with_broker()
        current_price = self.get_current_price()
        print(f"📈 {self.symbol} 현재가: ${current_price:.2f}")
        
        is_bought = False
        is_sold = False
        buy_qty = 0
        sell_qty = 0
        sell_price = 0
        action_type = "대기"
        
        # 1. 목표 익절 매도 감시
        if self.status["holdings"] > 0:
            target_sell_price = self.status["average_price"] * 1.10
            print(f"🔔 [익절 매도 예약] 목표가(+10%): ${target_sell_price:.2f} | 보유 수량: {self.status['holdings']:.2f}주")
            
            self.place_toss_order(
                quantity=self.status["holdings"],
                price=target_sell_price,
                side="SELL",
                order_type="LIMIT",
                time_in_force="DAY"
            )
            
            if self.is_dry_run and current_price >= target_sell_price:
                msg = f"🚨 [가상 익절 조건 충족] 가상 전량 익절 매도 정산을 실행합니다! 매도가: ${target_sell_price:.2f}"
                print(msg)
                self.send_telegram_notification(msg)
                is_sold = True
                sell_qty = self.status["holdings"]
                sell_price = target_sell_price
                action_type = "익절 전량 매도"
                self.reset_cycle()
                
        # 2. 당일 매수 주문 전송
        if not is_sold:
            step = self.status["step"]
            
            if step == 0:
                print("🆕 [1회차 진입] 최초 1주 매수 주문을 전송합니다.")
                self.place_toss_order(
                    quantity=1.0,
                    price=current_price,
                    side="BUY",
                    order_type="LIMIT",
                    time_in_force="DAY"
                )
                is_bought = True
                buy_qty = 1.0
                action_type = "최초 진입 매수"
                
                self.status["step"] = 1
                self.status["holdings"] = 1.0
                self.status["average_price"] = current_price
                self.status["total_purchase_amount"] = current_price
                self.status["last_trade_date"] = datetime.now(ny_tz).strftime("%Y-%m-%d")
                self.save_status()
            else:
                if step < self.status["divisions"]:
                    avg_price = self.status["average_price"]
                    target_buy_price = 0.0
                    
                    if current_price <= avg_price:
                        target_buy_price = avg_price
                        action_type = "지정가 LOC 매수"
                        print(f"📥 [LOC 매수 1회차] 평단가 대비 매수 주문: 1주 @ ${target_buy_price:.2f} (TIF: LOC)")
                    else:
                        target_buy_price = current_price * 1.10
                        action_type = "무체결 방지 LOC 매수"
                        print(f"📥 [LOC 매수 1회차] 무체결 방지 매수 주문: 1주 @ ${target_buy_price:.2f} (TIF: LOC)")
                        
                    self.place_toss_order(
                        quantity=1.0,
                        price=target_buy_price,
                        side="BUY",
                        order_type="LIMIT",
                        time_in_force="CLS"
                    )
                    
                    virtual_bought = False
                    if current_price <= avg_price:
                        virtual_bought = True
                    elif current_price > avg_price:
                        virtual_bought = True
                        
                    if virtual_bought:
                        is_bought = True
                        buy_qty = 1.0
                        
                        self.status["step"] += 1
                        self.status["holdings"] += 1.0
                        self.status["total_purchase_amount"] += current_price
                        self.status["average_price"] = self.status["total_purchase_amount"] / self.status["holdings"]
                        self.status["last_trade_date"] = datetime.now(ny_tz).strftime("%Y-%m-%d")
                        self.save_status()
                else:
                    action_type = "원금 소진 대기"
                    print(f"⚠️ [원금 소진] 현재 {step}회차로 설정된 {self.status['divisions']}회차 한도에 도달했습니다. 대기합니다.")

        # 3. 가상 투자 역사 기록 및 대시보드 갱신
        self.update_virtual_history(
            current_price=current_price,
            is_bought=is_bought,
            is_sold=is_sold,
            buy_qty=buy_qty,
            sell_qty=sell_qty,
            sell_price=sell_price,
            action_type=action_type
        )

def main():
    parser = argparse.ArgumentParser(description="TQQQ/SOXL 10분할 하루 1주 무한매수법 자동매매 봇")
    parser.add_argument("--symbol", type=str, default="TQQQ", help="자동매매할 종목 기호")
    parser.add_argument("--real", action="store_true", help="실전 투자 모드로 실행")
    args = parser.parse_args()
    
    is_dry_run = not args.real
    bot = TossInfiniteBuyingBot(symbol=args.symbol, is_dry_run=is_dry_run)
    bot.execute_daily_trade()

if __name__ == "__main__":
    main()
