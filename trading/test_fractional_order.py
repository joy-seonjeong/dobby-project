import os
import sys
import time
import requests
from dotenv import load_dotenv
from asset_manager import TossAssetManager

# .env 로드
load_dotenv()

def test_qqq_fractional_trading():
    """
    토스증권 OpenAPI를 사용하여 미국 주식 QQQ를 외화 1달러어치 시장가 매수한 뒤,
    기존 보유 주식 수량에 영향이 없도록 정확히 1달러어치만 다시 시장가 매도하는 소액 테스트 스크립트입니다.
    """
    print("🚀 [소액 거래 테스트] QQQ 1달러(USD) 매수 및 1달러(USD) 매도 테스트를 시작합니다.")
    
    # 1. API 매니저 초기화 및 계좌 체크
    try:
        manager = TossAssetManager()
        # 토큰 발급 테스트
        token = manager.get_access_token()
        print("🔑 API 인증 토큰 발급 성공!")
    except Exception as e:
        print(f"❌ API 매니저 초기화 또는 인증 실패: {e}")
        sys.exit(1)
        
    url = f"{manager.base_url}/api/v1/orders"
    headers = manager._get_headers()
    symbol = "SOXL"

    
    # 2. QQQ 1달러 시장가 매수 주문 전송
    buy_payload = {
        "symbol": symbol,
        "side": "BUY",
        "orderType": "MARKET",
        "orderAmount": "1",    # 1달러어치 매수
        "currency": "USD"      # 달러(USD) 기준
    }
    
    print(f"\n[STEP 1] {symbol} 시장가 1달러 매수 주문을 전송합니다...")
    try:
        response = requests.post(url, headers=headers, json=buy_payload)
        if response.status_code == 200:
            order_res = response.json()
            print("✅ 매수 주문 전송 성공!")
            print(f"   - 주문 응답: {order_res}")
        else:
            print(f"❌ 매수 주문 전송 실패. 상태코드: {response.status_code}, 내용: {response.text}")
            return
    except Exception as e:
        print(f"❌ 매수 API 호출 중 에러 발생: {e}")
        return

    # 3. 체결 대기 (시장가 주문 매수가 완전히 체결되고 처리될 수 있도록 3초 대기)
    print("\n⏳ 3초간 체결 처리를 대기합니다...")
    time.sleep(3)
    
    # 4. QQQ 1달러 시장가 매도 주문 전송 (기존 QQQ 잔고 전량 매도 방지)
    sell_payload = {
        "symbol": symbol,
        "side": "SELL",
        "orderType": "MARKET",
        "orderAmount": "1",    # 1달러어치 매도
        "currency": "USD"      # 달러(USD) 기준
    }
    
    print(f"\n[STEP 2] {symbol} 시장가 1달러 매도 주문을 전송합니다...")
    try:
        response = requests.post(url, headers=headers, json=sell_payload)
        if response.status_code == 200:
            print("✅ 매도 주문 전송 성공!")
            print(f"   - 주문 응답: {response.json()}")
        else:
            print(f"❌ 매도 주문 전송 실패. 상태코드: {response.status_code}, 내용: {response.text}")
    except Exception as e:
        print(f"❌ 매도 API 호출 중 에러 발생: {e}")

if __name__ == "__main__":
    test_qqq_fractional_trading()
