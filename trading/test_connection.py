import os
import sys
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

CLIENT_ID = os.getenv("TOSS_CLIENT_ID")
CLIENT_SECRET = os.getenv("TOSS_CLIENT_SECRET")
ACCOUNT_SEQ = os.getenv("TOSS_ACCOUNT_SEQ")

BASE_URL = "https://openapi.tossinvest.com"

def get_access_token():
    """
    OAuth 2.0 Client Credentials Grant 방식을 통해 토스증권 액세스 토큰을 발급받습니다.
    """
    print("\n[1] 토스증권 액세스 토큰 발급 요청 중...")
    url = f"{BASE_URL}/oauth2/token"
    
    # application/x-www-form-urlencoded 포맷으로 요청 전송
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            print(f"✅ 토큰 발급 성공! (유효시간: {expires_in}초)")
            return access_token
        else:
            print(f"❌ 토큰 발급 실패. 상태 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 연결 에러 발생: {e}")
        return None

def test_market_data(token):
    """
    계좌 정보 없이 토큰만으로 호출 가능한 시세 조회 API 테스트 (삼성전자 005930)
    """
    print("\n[2] 시장 시세 조회 테스트 (삼성전자: 005930)...")
    url = f"{BASE_URL}/api/v1/prices"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "symbols": "005930"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            result = data.get("result", [])
            if result:
                stock_info = result[0]
                print("✅ 시세 조회 성공!")
                print(f"   - 종목코드: {stock_info.get('symbol')}")
                print(f"   - 현재가: {stock_info.get('lastPrice')} {stock_info.get('currency')}")
                print(f"   - 조회시간: {stock_info.get('timestamp')}")
            else:
                print("⚠️ 시세 조회는 성공했으나 결과 데이터가 비어 있습니다.")
        else:
            print(f"❌ 시세 조회 실패. 상태 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
    except Exception as e:
        print(f"❌ 시세 조회 중 에러 발생: {e}")

def test_accounts(token):
    """
    계좌 목록 조회 API 테스트
    """
    print("\n[3] 보유 계좌 목록 조회 테스트...")
    url = f"{BASE_URL}/api/v1/accounts"
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("result", [])
            print(f"✅ 계좌 목록 조회 성공! (총 {len(accounts)}개 계좌)")
            for idx, acc in enumerate(accounts, 1):
                print(f"   계좌 {idx}:")
                print(f"   - 계좌번호: {acc.get('accountNo')}")
                print(f"   - 계좌 고유일련번호(accountSeq): {acc.get('accountSeq')}")
                print(f"   - 상태: {acc.get('status')}")
            return accounts
        else:
            print(f"❌ 계좌 목록 조회 실패. 상태 코드: {response.status_code}")
            print(f"응답 내용: {response.text}")
            return []
    except Exception as e:
        print(f"❌ 계좌 목록 조회 중 에러 발생: {e}")
        return []

def main():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ 에러: TOSS_CLIENT_ID 및 TOSS_CLIENT_SECRET 환경변수가 설정되지 않았습니다.")
        print("   trading/.env 파일을 생성하고 발급받은 API 정보를 기입해 주세요.")
        print("   (참고: .env.example 파일을 .env 파일로 복사하여 사용할 수 있습니다.)")
        sys.exit(1)
        
    token = get_access_token()
    if not token:
        print("❌ 토큰 발급에 실패하여 테스트를 중단합니다.")
        sys.exit(1)
        
    # 1. 시세 조회 테스트
    test_market_data(token)
    
    # 2. 계좌 목록 조회 테스트
    accounts = test_accounts(token)
    
    if accounts:
        print("\n💡 [팁] 위에서 확인한 'accountSeq' 값을 trading/.env 파일의 'TOSS_ACCOUNT_SEQ' 항목에 입력해 주세요.")
        print("   이후 주식 주문 및 잔고 조회 시 필수 헤더값으로 사용됩니다.")

if __name__ == "__main__":
    main()
