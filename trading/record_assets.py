import sys
import argparse
import random
from datetime import datetime, timedelta
from asset_manager import TossAssetManager
from db_manager import TossDBManager

def generate_dummy_data(db, days=30):
    """
    30일치의 우상향하는 자산 성장 추이 더미 데이터를 생성하여 DB에 적재합니다.
    """
    print(f"\n⚙️  {days}일치 자산 성장 더미 데이터 생성 중...")
    
    # 1. 초기 기준값 설정 (실제 유저의 현재 포트폴리오 수준을 반영)
    # 현재 유저 자산: 예수금 약 200만 KRW / 25 USD
    # 주식 매입금액: 934,500 KRW / 148,844 USD
    # 주식 평가금액: 1,017,000 KRW / 168,901 USD
    
    cash_krw = 2000000.0
    cash_usd = 25.25
    
    stock_purchase_krw = 934500.0
    stock_purchase_usd = 148844.44
    
    # 평가액은 매입액 근처에서 시작해 우상향하도록 설정
    base_eval_krw = 850000.0
    base_eval_usd = 135000.0
    
    start_date = datetime.now() - timedelta(days=days)
    
    # 보유 종목 템플릿
    stock_templates = [
        {"symbol": "005930", "name": "삼성전자", "country": "KR", "currency": "KRW", "quantity": 3, "avg_price": 311500},
        {"symbol": "QQQ", "name": "QQQ", "country": "US", "currency": "USD", "quantity": 145, "avg_price": 619.06},
        {"symbol": "SPY", "name": "SPY", "country": "US", "currency": "USD", "quantity": 61, "avg_price": 645.51},
        {"symbol": "AAPL", "name": "애플", "country": "US", "currency": "USD", "quantity": 8, "avg_price": 227.57}
    ]
    
    for i in range(days + 1):
        current_date = start_date + timedelta(days=i)
        timestamp = current_date.isoformat()
        
        # 날이 갈수록 우상향 추세(Trend) + 무작위 노이즈(Noise) 추가
        progress_ratio = i / days  # 0.0 ~ 1.0
        
        # 30일 동안 약 10~15% 성장하는 시나리오
        growth_trend = 1.0 + (progress_ratio * 0.15)
        noise = 1.0 + (random.uniform(-0.03, 0.03))  # 일별 ±3% 변동성
        
        eval_krw = base_eval_krw * growth_trend * noise
        eval_usd = base_eval_usd * growth_trend * noise
        
        # 더미 summary 구조화
        summary = {
            "cash": {
                "krw": cash_krw,
                "usd": cash_usd
            },
            "stock_totals": {
                "total_purchase_krw": stock_purchase_krw,
                "total_purchase_usd": stock_purchase_usd,
                "market_value_krw": eval_krw,
                "market_value_usd": eval_usd,
                "profit_loss_krw": eval_krw - stock_purchase_krw,
                "profit_loss_usd": eval_usd - stock_purchase_usd,
                # 가중 평균 수익률 계산
                "profit_rate": ((eval_krw - stock_purchase_krw) / stock_purchase_krw) if stock_purchase_krw > 0 else 0
            },
            "items": []
        }
        
        # 종목별 변동성 추가
        for stock in stock_templates:
            # 개별 종목도 시장 변동에 연동
            item_growth = growth_trend * (1.0 + random.uniform(-0.05, 0.05))
            current_price = stock["avg_price"] * item_growth
            
            purchase_amount = stock["quantity"] * stock["avg_price"]
            market_value = stock["quantity"] * current_price
            
            summary["items"].append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "country": stock["country"],
                "currency": stock["currency"],
                "quantity": stock["quantity"],
                "last_price": current_price,
                "purchase_price": stock["avg_price"],
                "market_value": market_value,
                "profit_loss": market_value - purchase_amount,
                "profit_rate": (market_value - purchase_amount) / purchase_amount
            })
            
        # DB 적재
        db.save_asset_snapshot(summary, custom_timestamp=timestamp)
        
    print(f"✅ {days}일치 더미 자산 데이터 적재가 완료되었습니다.")

def main():
    parser = argparse.ArgumentParser(description="토스증권 실시간 자산 데이터를 DB에 적재하는 스크립트")
    parser.add_argument("--dummy", action="store_true", help="연동 확인용 30일치 더미 데이터 생성 여부")
    args = parser.parse_args()
    
    db = TossDBManager()
    
    if args.dummy:
        generate_dummy_data(db)
        return
        
    print("🚀 실시간 토스증권 자산 데이터 수집 중...")
    try:
        manager = TossAssetManager()
        summary = manager.get_asset_summary()
        
        # DB에 현재 스냅샷 저장
        timestamp = db.save_asset_snapshot(summary)
        print(f"✅ 현재 자산 데이터 적재 완료! (타임스탬프: {timestamp})")
        print(f"   - 총 원화 환산액(예수금+주식): {summary['cash']['krw'] + summary['stock_totals']['market_value_krw'] + (summary['cash']['usd'] * 1380.0):,.0f} KRW")
        
    except ValueError as ve:
        print(f"❌ 설정 에러: {ve}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 데이터 수집 및 적재 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
