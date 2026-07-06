import sys
from asset_manager import TossAssetManager

def print_separator(char="=", length=60):
    print(char * length)

def main():
    print_separator()
    print(" 🏦 토스증권 실시간 계좌 자산 및 예수금 현황 조회")
    print_separator()
    
    try:
        # 자산 관리 클래스 초기화
        manager = TossAssetManager()
        
        # 자산 요약 정보 조회
        summary = manager.get_asset_summary()
        
        # 1. 예수금 (Buying Power) 출력
        print("\n💵 [예수금 현황]")
        print(f"  - 원화 예수금: {summary['cash']['krw']:,.0f} KRW")
        print(f"  - 외화 예수금: {summary['cash']['usd']:,.2f} USD")
        
        # 2. 보유 주식 평가 요약
        totals = summary["stock_totals"]
        print("\n📈 [보유 주식 총괄 평가]")
        
        # 원화 자산 요약
        print("  - 국내 주식 (KRW):")
        print(f"    * 총 매입금액: {totals['total_purchase_krw']:,.0f} KRW")
        print(f"    * 총 평가금액: {totals['market_value_krw']:,.0f} KRW")
        print(f"    * 총 평가손익: {totals['profit_loss_krw']:,.0f} KRW")
        
        # 달러 자산 요약 (보유 시 출력)
        if totals['total_purchase_usd'] > 0 or totals['market_value_usd'] > 0:
            print("  - 해외 주식 (USD):")
            print(f"    * 총 매입금액: {totals['total_purchase_usd']:,.2f} USD")
            print(f"    * total 평가금액: {totals['market_value_usd']:,.2f} USD")
            print(f"    * total 평가손익: {totals['profit_loss_usd']:,.2f} USD")
            
        print(f"  - 전체 수익률: {totals['profit_rate'] * 100:.2f}%")
        
        # 3. 보유 종목 상세 출력
        items = summary["items"]
        print(f"\n📁 [보유 종목 상세 리스트 (총 {len(items)}개 종목)]")
        if not items:
            print("  - 현재 보유 중인 주식이 없습니다.")
        else:
            print_separator("-")
            for idx, item in enumerate(items, 1):
                currency_unit = "KRW" if item["country"] == "KR" else "USD"
                
                # 국가별 포맷팅 처리
                if item["country"] == "KR":
                    last_price_str = f"{item['last_price']:,.0f}"
                    purchase_price_str = f"{item['purchase_price']:,.0f}"
                    market_value_str = f"{item['market_value']:,.0f}"
                    profit_loss_str = f"{item['profit_loss']:,.0f}"
                else:
                    last_price_str = f"{item['last_price']:,.2f}"
                    purchase_price_str = f"{item['purchase_price']:,.2f}"
                    market_value_str = f"{item['market_value']:,.2f}"
                    profit_loss_str = f"{item['profit_loss']:,.2f}"
                
                print(f" {idx}. {item['name']} ({item['symbol']}) | {item['country']}")
                print(f"    * 수량: {item['quantity']:.0f}주")
                print(f"    * 매입가: {purchase_price_str} {currency_unit} | 현재가: {last_price_str} {currency_unit}")
                print(f"    * 평가액: {market_value_str} {currency_unit}")
                print(f"    * 손익: {profit_loss_str} {currency_unit} ({item['profit_rate'] * 100:+.2f}%)")
                print_separator("-")
                
    except ValueError as ve:
        print(f"\n❌ 설정 에러: {ve}")
        print("   trading/.env 파일에 토스증권 API 설정 값이 제대로 기입되어 있는지 확인하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 조회 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
