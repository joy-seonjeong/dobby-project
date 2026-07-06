import os
import sys
import json
import argparse
import requests
from datetime import datetime
from dotenv import load_dotenv
from asset_manager import TossAssetManager

# .env 로드
load_dotenv()

STATUS_FILE_NAME = "infinite_buying_status.json"

class TossInfiniteBuyingBot:
    """
    토스증권 OpenAPI를 연동하여 라오어의 무한매수법에 따른 자동 매매를 수행하는 봇입니다.
    (종목별 동적 가상 대시보드 및 수수료 정산 기능 지원)
    """
    def __init__(self, symbol: str, is_dry_run: bool = True, gemini_monthly_fee: float = 20.0, transaction_fee_rate: float = 0.0007, tax_rate: float = 0.0000278):
        self.symbol = symbol.upper()
        self.is_dry_run = is_dry_run
        
        # 비용 및 수수료 설정
        self.gemini_monthly_fee = gemini_monthly_fee
        self.transaction_fee_rate = transaction_fee_rate
        self.tax_rate = tax_rate
        
        try:
            self.asset_manager = TossAssetManager()
        except Exception as e:
            if not self.is_dry_run:
                print(f"⚠️ TossAssetManager 초기화 실패: {e}")
            self.asset_manager = None
            
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.status_file_path = os.path.join(self.current_dir, "data", STATUS_FILE_NAME)
        
        # 동적 파일명 결정 (예: TQQQ_10_virtual_history.json)
        self.virtual_history_path = os.path.join(self.current_dir, "data", f"{self.symbol}_10_virtual_history.json")
        self.dashboard_path = os.path.join(self.current_dir, "data", f"{self.symbol}_virtual_trading_report.html")
        
        os.makedirs(os.path.join(self.current_dir, "data"), exist_ok=True)
        self.status = self.load_status()
        
    def load_status(self):
        """
        로컬 상태 파일에서 진행 상태를 불러옵니다.
        """
        if os.path.exists(self.status_file_path):
            with open(self.status_file_path, "r", encoding="utf-8") as f:
                try:
                    all_status = json.load(f)
                    if self.symbol in all_status:
                        return all_status[self.symbol]
                except Exception as e:
                    print(f"⚠️ 상태 파일 로드 오류: {e}")
                    
        # 기본 TQQQ 10분할 모의투자 디폴트값 (원금 $1,600, 1회 한도 $160, 하루 최대 1주 매수)
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
        """
        현재 진행 상태를 저장합니다.
        """
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
        print(f"💾 {self.symbol} 상태 저장: step={self.status['step']}, holdings={self.status['holdings']}주, 평단가=${self.status['average_price']:.2f}")

    def sync_state_with_broker(self):
        """
        실계좌 동기화
        """
        if self.is_dry_run or not self.asset_manager:
            return
        try:
            holdings_info = self.asset_manager.get_holdings(symbol=self.symbol)
            items = holdings_info.get("items", [])
            target_item = None
            for item in items:
                if item.get("symbol") == self.symbol:
                    target_item = item
                    break
            if not target_item:
                if self.status["holdings"] > 0:
                    self.reset_cycle()
            else:
                broker_qty = float(target_item.get("quantity", 0))
                broker_avg_price = float(target_item.get("averagePurchasePrice", 0))
                if broker_qty != self.status["holdings"]:
                    if self.status["step"] == 0:
                        self.status["step"] = 1
                    else:
                        self.status["step"] += 1
                self.status["holdings"] = broker_qty
                self.status["average_price"] = broker_avg_price
                self.status["total_purchase_amount"] = broker_qty * broker_avg_price
            self.save_status()
        except Exception as e:
            print(f"❌ 계좌 동기화 실패: {e}")

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
        try:
            import yfinance as yf
            ticker = yf.Ticker(self.symbol)
            price = ticker.fast_info.last_price
            if price:
                return price
        except Exception:
            pass
        return 76.76

    def place_toss_order(self, quantity: float, price: float, side: str, order_type: str = "LIMIT", time_in_force: str = "DAY"):
        if self.is_dry_run:
            print(f"🛡️ [DRY RUN 가상 주문] {side} {self.symbol} {quantity}주 @ ${price:.2f} (TIF: {time_in_force})")
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
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    def update_virtual_history(self, current_price: float, is_bought: bool, is_sold: bool, buy_qty: float = 0, sell_qty: float = 0, sell_price: float = 0):
        """
        가상 투자 기록 누적 저장 (Gemini 요금 및 수수료 반영)
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        
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
            today_obj = datetime.now()
            if today_obj.month != last_date_obj.month:
                print(f"💸 [비용 청구] Gemini 월 구독료 ${self.gemini_monthly_fee:.2f}가 가상 차감되었습니다.")
                self.status["net_cash"] -= self.gemini_monthly_fee
                
        if is_bought and buy_qty > 0:
            buy_amt = buy_qty * current_price
            fee = buy_amt * self.transaction_fee_rate
            self.status["net_cash"] -= (buy_amt + fee)
            self.status["net_holdings"] += buy_qty
            self.status["net_total_purchase"] += (buy_amt + fee)
            self.status["net_average_price"] = self.status["net_total_purchase"] / self.status["net_holdings"]
            print(f"📈 [가상 매수 정산] {buy_qty}주 매수 (수수료 ${fee:.4f} 차감 반영)")
            
        if is_sold and sell_qty > 0:
            gross_revenue = sell_qty * sell_price
            fee = gross_revenue * self.transaction_fee_rate
            tax = gross_revenue * self.tax_rate
            net_revenue = gross_revenue - fee - tax
            self.status["net_cash"] += net_revenue
            print(f"🎉 [가상 익절 정산] {sell_qty}주 매도 완료 (수수료/세금 ${fee+tax:.4f} 차감 반영)")
            self.status["net_holdings"] = 0.0
            self.status["net_total_purchase"] = 0.0
            self.status["net_average_price"] = 0.0
            
        portfolio_value = self.status["holdings"] * current_price
        total_assets = (self.status["capital"] - self.status["total_purchase_amount"]) + portfolio_value
        
        net_portfolio_value = self.status["net_holdings"] * current_price
        net_total_assets = self.status["net_cash"] + net_portfolio_value
        
        today_record = {
            "date": today_str,
            "close": current_price,
            "step": self.status["step"],
            "holdings": self.status["holdings"],
            "average_price": round(self.status["average_price"], 2),
            "total_assets": round(total_assets, 2),
            "net_assets": round(net_total_assets, 2),
            "profit_rate_pct": round(((total_assets - self.status["capital"]) / self.status["capital"]) * 100, 2),
            "net_profit_rate_pct": round(((net_total_assets - self.status["capital"]) / self.status["capital"]) * 100, 2)
        }
        
        history_list.append(today_record)
        
        with open(self.virtual_history_path, "w", encoding="utf-8") as f:
            json.dump(history_list, f, indent=4, ensure_ascii=False)
            
        print(f"📊 [{self.symbol} 가상자산 현황] 세전: ${today_record['total_assets']:.2f} ({today_record['profit_rate_pct']:+}%)\n"
              f"                     비용차감 후 순자산: ${today_record['net_assets']:.2f} ({today_record['net_profit_rate_pct']:+}%)")
              
        self.generate_virtual_dashboard(history_list)

    def generate_virtual_dashboard(self, history):
        """
        가상 모의투자 대시보드 HTML 파일 생성 (종목명 대응 및 미적 리뉴얼)
        """
        today_rec = history[-1]
        raw_pct = today_rec["profit_rate_pct"]
        net_pct = today_rec["net_profit_rate_pct"]
        
        dates_json = json.dumps([h["date"] for h in history])
        raw_assets_json = json.dumps([h["total_assets"] for h in history])
        net_assets_json = json.dumps([h["net_assets"] for h in history])
        prices_json = json.dumps([h["close"] for h in history])
        
        html_template = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.symbol} 10분할 실시간 모의투자 대시보드</title>
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
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}

        header h1 {{
            font-size: 2.2rem;
            background: linear-gradient(to right, #60a5fa, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        header p {{ color: var(--text-secondary); font-size: 1.05rem; margin-top: 0.25rem; }}
        
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
        }}

        .kpi-title {{ font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 0.5rem; }}
        .kpi-value {{ font-size: 1.8rem; font-weight: 700; }}
        .kpi-value.positive {{ color: var(--accent-green); }}
        .kpi-value.negative {{ color: var(--accent-red); }}

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
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{self.symbol} 10분할 실시간 모의투자 대시보드</h1>
            <p>오늘부터 시작하는 {self.symbol} 10분할 (하루 최대 1주) 무한매수 모의투자 가짜 계좌</p>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">총 설정 원금</div>
                <div class="kpi-value">${self.status['capital']:,}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">세전 가상자산</div>
                <div class="kpi-value" style="color: #60a5fa">${today_rec['total_assets']:,} ({raw_pct:+,}%)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">순자산 (비용 차감 후)</div>
                <div class="kpi-value {'positive' if net_pct >= 0 else 'negative'}">
                    ${today_rec['net_assets']:,} ({net_pct:+,}%)
                </div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">{self.symbol} 현재가</div>
                <div class="kpi-value" style="color: var(--accent-purple)">${today_rec['close']:,}</div>
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
                        <span class="stat-val">{self.status['step']} / 10회차</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">가상 보유량</span>
                        <span class="stat-val">{self.status['holdings']}주</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">가상 보유 평단가</span>
                        <span class="stat-val">${self.status['average_price']:.2f}</span>
                    </li>
                    <li class="stat-item">
                        <span class="stat-label">순현금 보유액</span>
                        <span class="stat-val">${self.status['net_cash']:.2f}</span>
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
    </div>

    <script>
        const dates = {dates_json};
        const rawAssets = {raw_assets_json};
        const netAssets = {net_assets_json};
        const prices = {prices_json};

        const ctx = document.getElementById('virtualChart').getContext('2d');
        new Chart(ctx, {{
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
                        label: '{self.symbol} 주가 ($)',
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
    </script>
</body>
</html>
        """
        
        with open(self.dashboard_path, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"✨ 실시간 가상 대시보드 업데이트 완료! 파일 경로:\n   {self.dashboard_path}")

    def execute_daily_trade(self):
        """
        매일 실행되는 무한매수법 거래 로직을 수행합니다.
        (가변형 1주 LOC 매수 룰 적용)
        """
        print(f"\n🚀 === [무한매수법 실행] 종목: {self.symbol} | 모드: {'DRY-RUN(가상)' if self.is_dry_run else 'REAL(실전)'} ===")
        
        self.sync_state_with_broker()
        current_price = self.get_current_price()
        print(f"📈 {self.symbol} 현재가: ${current_price:.2f}")
        
        is_bought = False
        is_sold = False
        buy_qty = 0
        sell_qty = 0
        sell_price = 0
        
        # 1. 목표 익절 매도 감시
        if self.status["holdings"] > 0:
            target_sell_price = self.status["average_price"] * 1.10
            print(f"🔔 [익절 매도 예약] 목표가(+10%): ${target_sell_price:.2f} | 보유 수량: {self.status['holdings']}주")
            
            if current_price >= target_sell_price:
                print("🚨 [실시간 익절 조건 충족] 전량 매도를 실행합니다!")
                self.place_toss_order(
                    quantity=self.status["holdings"],
                    price=0,
                    side="SELL",
                    order_type="MARKET",
                    time_in_force="DAY"
                )
                is_sold = True
                sell_qty = self.status["holdings"]
                sell_price = current_price
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
                
                self.status["step"] = 1
                self.status["holdings"] = 1.0
                self.status["average_price"] = current_price
                self.status["total_purchase_amount"] = current_price
                self.status["last_trade_date"] = datetime.now().strftime("%Y-%m-%d")
                self.save_status()
            else:
                if step < self.status["divisions"]:
                    avg_price = self.status["average_price"]
                    target_buy_price = 0.0
                    
                    if current_price <= avg_price:
                        target_buy_price = avg_price
                        print(f"📥 [LOC 매수 1회차] 평단가 대비 매수 주문: 1주 @ ${target_buy_price:.2f} (종가 평단 이하 시 체결)")
                    else:
                        target_buy_price = current_price * 1.10
                        print(f"📥 [LOC 매수 1회차] 무체결 방지 매수 주문: 1주 @ ${target_buy_price:.2f} (무조건 종가 체결)")
                        
                    self.place_toss_order(
                        quantity=1.0,
                        price=target_buy_price,
                        side="BUY",
                        order_type="LIMIT",
                        time_in_force="CLS"
                    )
                    
                    # 가상 체결 판정
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
                        self.status["last_trade_date"] = datetime.now().strftime("%Y-%m-%d")
                        self.save_status()
                else:
                    print(f"⚠️ [원금 소진] 현재 {step}회차로 설정된 {self.status['divisions']}회차 한도에 도달했습니다. 대기합니다.")

        # 3. 가상 투자 역사 기록 및 대시보드 갱신
        self.update_virtual_history(
            current_price=current_price,
            is_bought=is_bought,
            is_sold=is_sold,
            buy_qty=buy_qty,
            sell_qty=sell_qty,
            sell_price=sell_price
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
