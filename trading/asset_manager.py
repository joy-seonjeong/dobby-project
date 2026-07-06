import os
import requests
from dotenv import load_dotenv

class TossAssetManager:
    """
    토스증권 OpenAPI를 활용하여 계좌의 보유 자산 및 예수금 현황을 관리하는 클래스입니다.
    """
    def __init__(self, client_id=None, client_secret=None, account_seq=None):
        load_dotenv()
        self.client_id = client_id or os.getenv("TOSS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("TOSS_CLIENT_SECRET")
        self.account_seq = account_seq or os.getenv("TOSS_ACCOUNT_SEQ")
        self.base_url = "https://openapi.tossinvest.com"
        self._access_token = None
        
        if not self.client_id or not self.client_secret:
            raise ValueError("TOSS_CLIENT_ID 및 TOSS_CLIENT_SECRET 설정이 누락되었습니다.")
        if not self.account_seq:
            raise ValueError("TOSS_ACCOUNT_SEQ 설정이 누락되었습니다.")

    def get_access_token(self, force_refresh=False):
        """
        인증용 액세스 토큰을 가져옵니다. (기존 토큰이 있으면 재사용)
        """
        if self._access_token and not force_refresh:
            return self._access_token
            
        url = f"{self.base_url}/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(url, data=payload, headers=headers)
        if response.status_code == 200:
            self._access_token = response.json().get("access_token")
            return self._access_token
        else:
            raise Exception(f"인증 토큰 발급 실패 (Status: {response.status_code}): {response.text}")

    def _get_headers(self):
        """
        API 호출에 공통으로 사용되는 헤더를 반환합니다.
        """
        token = self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": str(self.account_seq)
        }

    def get_buying_power(self, currency="KRW"):
        """
        매수 가능 금액(예수금)을 조회합니다.
        - currency: 'KRW' (원화) 또는 'USD' (달러)
        """
        url = f"{self.base_url}/api/v1/buying-power"
        params = {"currency": currency.upper()}
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code == 200:
            return response.json().get("result", {})
        else:
            raise Exception(f"매수 가능 금액 조회 실패 (Status: {response.status_code}): {response.text}")

    def get_holdings(self, symbol=None):
        """
        보유 주식 현황을 조회합니다.
        - symbol: 특정 종목 코드 필터링 (선택 사항)
        """
        url = f"{self.base_url}/api/v1/holdings"
        params = {}
        if symbol:
            params["symbol"] = symbol
            
        response = requests.get(url, headers=self._get_headers(), params=params)
        if response.status_code == 200:
            return response.json().get("result", {})
        else:
            raise Exception(f"보유 주식 조회 실패 (Status: {response.status_code}): {response.text}")

    def get_asset_summary(self):
        """
        예수금과 보유 주식 현황을 요약한 종합 자산 보고서를 생성합니다.
        """
        # 1. 예수금 조회
        buying_power_krw = self.get_buying_power("KRW")
        buying_power_usd = self.get_buying_power("USD")
        
        # 2. 보유 자산 조회
        holdings = self.get_holdings()
        
        # 요약 데이터 정제
        summary = {
            "cash": {
                "krw": float(buying_power_krw.get("cashBuyingPower", 0)),
                "usd": float(buying_power_usd.get("cashBuyingPower", 0))
            },
            "stock_totals": {
                "total_purchase_krw": float(holdings.get("totalPurchaseAmount", {}).get("krw") or 0),
                "total_purchase_usd": float(holdings.get("totalPurchaseAmount", {}).get("usd") or 0),
                "market_value_krw": float(holdings.get("marketValue", {}).get("amount", {}).get("krw") or 0),
                "market_value_usd": float(holdings.get("marketValue", {}).get("amount", {}).get("usd") or 0),
                "profit_loss_krw": float(holdings.get("profitLoss", {}).get("amount", {}).get("krw") or 0),
                "profit_loss_usd": float(holdings.get("profitLoss", {}).get("amount", {}).get("usd") or 0),
                "profit_rate": float(holdings.get("profitLoss", {}).get("rate" or 0))
            },
            "items": []
        }
        
        # 보유 종목 상세 파싱
        for item in holdings.get("items", []):
            parsed_item = {
                "symbol": item.get("symbol"),
                "name": item.get("name"),
                "country": item.get("marketCountry"),  # 'KR' or 'US'
                "currency": item.get("currency"),      # 'KRW' or 'USD'
                "quantity": float(item.get("quantity", 0)),
                "last_price": float(item.get("lastPrice", 0)),
                "purchase_price": float(item.get("averagePurchasePrice", 0)),
                "purchase_amount": float(item.get("marketValue", {}).get("purchaseAmount", 0)),
                "market_value": float(item.get("marketValue", {}).get("amount", 0)),
                "profit_loss": float(item.get("profitLoss", {}).get("amount", 0)),
                "profit_rate": float(item.get("profitLoss", {}).get("rate", 0))
            }
            summary["items"].append(parsed_item)
            
        return summary
