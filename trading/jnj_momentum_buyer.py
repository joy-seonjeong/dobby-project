import os
import sys
import json
import time
import argparse
import datetime
import requests
import pytz
from dotenv import load_dotenv
from asset_manager import TossAssetManager

# 1. 환경변수 및 기본 설정 로드
load_dotenv()

STATE_FILE = "data/jnj_buyer_state.json"
BASE_URL = "https://openapi.tossinvest.com"

# 수수료 설정 (토스증권 실거래 기준 수수료 0.1% 및 제세금 SEC Fee 0.00206% 준수)
TRANSACTION_FEE_RATE = 0.001
TAX_RATE = 0.0000206

class JNJMomentumBuyer:
    """
    존슨앤존슨(JNJ) 주가를 매시간 모니터링하여 당일 시가 대비 5% 이상 상승 시 
    $4.00 어치를 매수하는 자동화 프로그램 클래스입니다.
    """
    def __init__(self, is_dry_run: bool = True):
        self.symbol = "JNJ"
        self.is_dry_run = is_dry_run
        
        # 텔레그램 설정 로드
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # 토스 자산 매니저 초기화
        try:
            self.asset_manager = TossAssetManager()
        except Exception as e:
            msg = f"⚠️ [경고] TossAssetManager 초기화 실패: {e}"
            print(msg)
            self.send_telegram_notification(msg)
            self.asset_manager = None
            
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.state_file_path = os.path.join(self.current_dir, STATE_FILE)
        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        
        # 이전 상태 불러오기
        self.state = self.load_state()

    def send_telegram_notification(self, message: str):
        """
        텔레그램 메신저로 봇의 구동 로그 및 주요 알림을 즉시 발송합니다.
        """
        print(f"📢 [Telegram] {message}")
        if not self.telegram_token or not self.telegram_chat_id:
            return
            
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": f"🤖 [JNJ 모멘텀 매수 봇]\n{message}"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ 텔레그램 알림 발송 실패: {e}")

    def load_state(self):
        """
        영구 파일(JSON)로부터 이전 저장된 상태 데이터를 로드합니다.
        """
        if os.path.exists(self.state_file_path):
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception as e:
                    print(f"⚠️ 상태 파일 로드 오류: {e}")
                    
        return {
            "last_buy_date": None,       # 마지막으로 매수 완료한 날짜 (YYYY-MM-DD)
            "open_price": None,          # 당일 장 시작 시가
            "open_price_date": None,     # 시가를 획득한 날짜 (YYYY-MM-DD)
            "last_checked_hour": 0       # 당일 몇 시간째 감시를 마쳤는지 여부
        }

    def save_state(self):
        """
        현재의 상태 데이터를 영구 파일(JSON)에 동기화합니다.
        """
        with open(self.state_file_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4, ensure_ascii=False)
        print(f"💾 상태 저장 완료: {self.state}")

    def is_us_daylight_saving(self, dt: datetime.datetime) -> bool:
        """
        미국 동부 표준시 기준 썸머타임(Daylight Saving Time) 여부를 판별합니다.
        """
        tz_ny = pytz.timezone("America/New_York")
        dt_ny = dt.astimezone(tz_ny)
        return dt_ny.dst() != datetime.timedelta(0)

    def get_market_hours(self, dt: datetime.datetime):
        """
        오늘 날짜의 미국 정규장 운영 시간(KST) 범위를 구합니다.
        """
        is_dst = self.is_us_daylight_saving(dt)
        if is_dst:
            # 썸머타임 적용 시: 22:30 ~ 익일 05:00
            start_time = dt.replace(hour=22, minute=30, second=0, microsecond=0)
            end_time = (dt + datetime.timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)
        else:
            # 썸머타임 미적용 시: 23:30 ~ 익일 06:00
            start_time = dt.replace(hour=23, minute=30, second=0, microsecond=0)
            end_time = (dt + datetime.timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
            
        return start_time, end_time

    def get_token(self):
        """
        자산 매니저를 통해 유효한 OpenAPI 액세스 토큰을 가져옵니다.
        """
        if not self.asset_manager:
            raise ValueError("자산 매니저가 초기화되지 않았습니다.")
        return self.asset_manager.get_access_token()

    def get_jnj_open_price(self):
        """
        토스증권 OpenAPI를 호출하여 금일 JNJ 정규장 시가(Open Price)를 조회합니다.
        """
        token = self.get_token()
        url = f"{BASE_URL}/api/v1/candles"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {
            "symbol": self.symbol,
            "interval": "1d",
            "count": 1
        }
        
        # 네트워크 오류 대응 재시도 로직
        for attempt in range(1, 4):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    candles = data.get("result", {}).get("candles", [])
                    if candles:
                        open_p = float(candles[0].get("openPrice", 0))
                        if open_p > 0:
                            return open_p
                print(f"⚠️ [재시도 {attempt}/3] 시가 조회 실패: {response.text}")
                time.sleep(2.0)
            except Exception as e:
                print(f"⚠️ [재시도 {attempt}/3] 시가 조회 중 네트워크 오류: {e}")
                time.sleep(2.0)
        return None

    def get_jnj_current_price(self):
        """
        토스증권 OpenAPI를 호출하여 JNJ의 현재가를 조회합니다.
        """
        token = self.get_token()
        url = f"{BASE_URL}/api/v1/prices"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        params = {
            "symbols": self.symbol
        }
        
        # 네트워크 오류 대응 재시도 로직
        for attempt in range(1, 4):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", [])
                    if result:
                        return float(result[0].get("lastPrice", 0))
                print(f"⚠️ [재시도 {attempt}/3] 현재가 조회 실패: {response.text}")
                time.sleep(2.0)
            except Exception as e:
                print(f"⚠️ [재시도 {attempt}/3] 현재가 조회 중 네트워크 오류: {e}")
                time.sleep(2.0)
        return None

    def execute_buy_order(self, current_price: float):
        """
        $4.00 어치의 JNJ 소수점 시장가 매수 주문을 발송합니다.
        """
        buy_amount = 4.00
        
        if self.is_dry_run:
            # 1. 모의투자 모드 (Dry-run)
            approx_qty = buy_amount / current_price
            est_fee = buy_amount * TRANSACTION_FEE_RATE
            net_spent = buy_amount + est_fee
            
            msg = (
                f"🧪 [모의투자 매수 체결 알림]\n"
                f"• 종목: {self.symbol}\n"
                f"• 매수 구분: 금액 지정 시장가 매수 (Dry-run)\n"
                f"• 설정 매수금액: ${buy_amount:.2f}\n"
                f"• 체결가 (현재가): ${current_price:.2f}\n"
                f"• 가상 체결 수량: 약 {approx_qty:.6f}주\n"
                f"• 적용 수수료 (0.1%): ${est_fee:.4f}\n"
                f"• 가상 총 지출금액: ${net_spent:.4f}"
            )
            self.send_telegram_notification(msg)
            return True
            
        else:
            # 2. 실전 투자 모드
            token = self.get_token()
            url = f"{BASE_URL}/api/v1/orders"
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Tossinvest-Account": str(os.getenv("TOSS_ACCOUNT_SEQ"))
            }
            
            # 고유한 clientOrderId 생성 (멱등성 키)
            client_order_id = f"jnj-opt-{int(time.time())}"
            payload = {
                "clientOrderId": client_order_id,
                "symbol": self.symbol,
                "side": "BUY",
                "orderType": "MARKET",
                "orderAmount": buy_amount
            }
            
            for attempt in range(1, 4):
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=15)
                    if response.status_code == 200:
                        order_res = response.json().get("result", {})
                        order_id = order_res.get("orderId")
                        msg = (
                            f"🚀 [실전 매수 주문 접수 완료]\n"
                            f"• 종목: {self.symbol}\n"
                            f"• 주문금액: ${buy_amount:.2f}\n"
                            f"• 주문 ID: {order_id}\n"
                            f"• 멱등키: {client_order_id}\n"
                            f"※ 정규장 체결 후 실계좌 반영을 확인해 주세요."
                        )
                        self.send_telegram_notification(msg)
                        return True
                    else:
                        print(f"⚠️ [재시도 {attempt}/3] 주문 전송 실패: {response.text}")
                        time.sleep(3.0)
                except Exception as e:
                    print(f"⚠️ [재시도 {attempt}/3] 주문 전송 중 에러: {e}")
                    time.sleep(3.0)
            
            # 최종 실패 시 알림
            self.send_telegram_notification(f"❌ [에러] JNJ 실전 매수 주문이 최종 실패하였습니다.")
            return False

    def run_cycle(self):
        """
        정기적으로 구동되며 시간을 판단하고, 시가 획득 및 매수 조건(5% 상승) 감시를 수행합니다.
        """
        now = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. 미국 정규장 운영 시간 판별
        start_time, end_time = self.get_market_hours(now)
        
        # 장 시작 전이거나 종료 후의 대기 국면
        if now < start_time or now > end_time:
            # 상태값 중 당일 관련 정보만 날짜가 바뀌었을 시 리셋
            if self.state["open_price_date"] != today_str:
                self.state["open_price"] = None
                self.state["open_price_date"] = None
                self.state["last_checked_hour"] = 0
                self.save_state()
            
            print(f"💤 장외 대기 중... (현재 KST: {now.strftime('%H:%M:%S')}, 다음 장 시작: {start_time.strftime('%Y-%m-%d %H:%M')})")
            return 60  # 장외엔 60초 대기

        # 2. 정규장 시간 내 구동
        print(f"⏰ 정규장 구동 중... (KST: {now.strftime('%H:%M:%S')})")
        
        # 이번 주(ISO 주차)에 이미 매수를 완료한 경우 패스
        if self.state["last_buy_date"]:
            try:
                last_dt = datetime.datetime.strptime(self.state["last_buy_date"], "%Y-%m-%d")
                last_year, last_week, _ = last_dt.isocalendar()
                now_year, now_week, _ = now.isocalendar()
                if last_year == now_year and last_week == now_week:
                    print(f"✅ 이번 주({now_year}년 {now_week}주차)에는 이미 매수를 완료했습니다. 추가 매수를 보류합니다.")
                    return 1800
            except Exception as e:
                print(f"⚠️ 매수 날짜 비교 중 예외 발생 (기본 오늘 날짜 비교로 대체): {e}")
                if self.state["last_buy_date"] == today_str:
                    return 1800
            
        # 3. 당일 시가(Open Price) 획득
        if self.state["open_price_date"] != today_str or self.state["open_price"] is None:
            print("🔍 금일 시가 획득 시도 중...")
            open_price = self.get_jnj_open_price()
            if open_price:
                self.state["open_price"] = open_price
                self.state["open_price_date"] = today_str
                self.state["last_checked_hour"] = 0
                self.save_state()
                self.send_telegram_notification(f"📈 금일 {self.symbol} 정규장 시가 획득 완료: ${open_price:.2f}")
            else:
                print("⚠️ 시가를 가져오지 못했습니다. 10초 후 재시도합니다.")
                return 10
                
        # 4. 장 시작 후 경과 시간(1시간 단위) 판단
        elapsed_seconds = (now - start_time).total_seconds()
        elapsed_hours = int(elapsed_seconds // 3600)
        
        # 장 시작 후 경과 시각 체크 (1시간~6시간 경과 시점 체크)
        if 0 < elapsed_hours <= 6 and self.state["last_checked_hour"] < elapsed_hours:
            print(f"📊 장 시작 후 {elapsed_hours}시간 경과 감시 작동")
            
            # 현재가 조회
            current_price = self.get_jnj_current_price()
            if not current_price:
                print("⚠️ 현재가 조회 실패로 감시 단계를 다음 주기로 보류합니다.")
                return 10
                
            open_price = self.state["open_price"]
            change_rate = (current_price - open_price) / open_price
            
            log_msg = f"🔍 [{elapsed_hours}시간째 감시] 시가: ${open_price:.2f} | 현재가: ${current_price:.2f} (변동률: {change_rate*100:+.2f}%)"
            print(log_msg)
            
            # 조건 판단: 시가 대비 5% 이상 상승 시 매수
            if change_rate >= 0.05:
                self.send_telegram_notification(f"🔥 [조건 충족] 현재가 ${current_price:.2f}가 시가 ${open_price:.2f} 대비 {change_rate*100:.2f}% 상승하여 매수를 실행합니다.")
                success = self.execute_buy_order(current_price)
                if success:
                    self.state["last_buy_date"] = today_str
                    self.state["last_checked_hour"] = elapsed_hours
                    self.save_state()
                    return 1800  # 매수가 완료되었으므로 길게 대기
            else:
                # 조건 미충족 시 다음 시간 체크를 위해 진행 표시 기록
                self.state["last_checked_hour"] = elapsed_hours
                self.save_state()
                print(f"ℹ️ 상승률({change_rate*100:.2f}%)이 기준치(5.00%)에 미달하여 매수를 보류합니다.")
                
        # 다음 정시 체크를 위해 적절히 대기 (일반적으로 10초 단위로 짧게 루프를 돌며 시간 판단)
        return 10

    def test_force_buy(self):
        """
        테스트 플래그 구동 시, 주가 상승 조건과 관계없이 즉시 $4.00 매수 주문을 강제로 실행해 봅니다.
        """
        print("🧪 [테스트] 강제 매수 테스트 실행")
        current_price = self.get_jnj_current_price()
        if not current_price:
            print("❌ 현재가 획득 실패로 강제 매수를 취소합니다.")
            return
            
        print(f"JNJ 현재가: ${current_price:.2f}")
        self.execute_buy_order(current_price)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JNJ Momentum Buyer Bot")
    parser.add_argument("--real", action="store_true", help="실투자 모드 (지정하지 않을 시 기본 dry-run 모의투자)")
    parser.add_argument("--test-force-buy", action="store_true", help="상승 조건 관계없이 1회 즉시 강제 매수 테스트 실행")
    args = parser.parse_args()

    is_dry_run = not args.real
    
    print("=" * 60)
    print(f" 🤖 JNJ 모멘텀 자동 매수 프로그램 가동 시작")
    print(f"  - 구동 모드: {'🧪 모의투자 (Dry-run)' if is_dry_run else '🚀 실전 투자 (REAL)'}")
    print("=" * 60)
    
    buyer = JNJMomentumBuyer(is_dry_run=is_dry_run)
    
    if args.test_force_buy:
        buyer.test_force_buy()
        sys.exit(0)
        
    # 서비스 메인 무한 루프
    try:
        while True:
            sleep_time = buyer.run_cycle()
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        print("\n👋 JNJ 모멘텀 매수 프로그램을 종료합니다.")
