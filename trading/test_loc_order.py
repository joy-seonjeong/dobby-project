import os
import sys
import requests
from dotenv import load_dotenv
from asset_manager import TossAssetManager

# .env 로드
load_dotenv()

def test_tsla_loc_order():
    """
    토스증권 OpenAPI를 사용하여 테슬라(TSLA) 1주를 극단적으로 낮은 가격($10.00)으로 
    LOC(CLS) 지정가 매수 주문을 전송하여, 실제 돈이 들지 않으면서 LOC 접수 여부를 안전하게 확인하는 테스트입니다.
    """
    print("🚀 [안전한 LOC 주문 테스트] TSLA 1주 초저가 LOC(CLS) 매수 테스트를 시작합니다.")
    
    try:
        manager = TossAssetManager()
        token = manager.get_access_token()
        print("🔑 API 인증 토큰 발급 성공!")
    except Exception as e:
        print(f"❌ API 매니저 초기화 또는 인증 실패: {e}")
        sys.exit(1)
        
    url = f"{manager.base_url}/api/v1/orders"
    headers = manager._get_headers()
    symbol = "TSLA"
    
    # 테슬라 현재가는 약 $432 이지만, $10.00 지정가로 장마감 지정가(CLS) 매수 주문을 넣음
    # (종가가 $10.00 이하일 때만 체결되므로 오늘 장마감 시 100% 체결되지 않고 자동 취소되어 안전합니다.)
    loc_payload = {
        "symbol": symbol,
        "side": "BUY",
        "orderType": "LIMIT",
        "timeInForce": "CLS",   # 토스증권의 LOC 주문 규격
        "quantity": "1",        # 소수점이 아닌 정수 1주로 지정 (소수점 지정가 제한 우회)
        "price": "10.00"        # 안전한 초저가 지정
    }
    
    print(f"\n[EXECUTE] {symbol} 1주 @ $10.00 (TIF: CLS / LOC) 주문을 전송합니다...")
    try:
        response = requests.post(url, headers=headers, json=loc_payload)
        if response.status_code == 200:
            order_res = response.json()
            print("✅ LOC(CLS) 주문 전송 성공!")
            print(f"   - 주문 응답: {order_res}")
            print(f"   - 안내: 테슬라 1주가 $10.00로 접수되었습니다. 종가가 이보다 높을 것이므로 장마감 시 미체결되어 자동 취소됩니다.")
        else:
            print(f"❌ LOC(CLS) 주문 전송 실패. 상태코드: {response.status_code}, 내용: {response.text}")
    except Exception as e:
        print(f"❌ API 호출 중 에러 발생: {e}")

if __name__ == "__main__":
    test_tsla_loc_order()
