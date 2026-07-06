import os
import argparse
import yfinance as yf
from datetime import datetime

def download_stock_data(symbol: str, period: str = "5y", start: str = None, end: str = None):
    """
    Yahoo Finance API를 사용하여 특정 해외 주식/ETF의 일봉 데이터를 다운로드합니다.
    """
    print(f"\n[데이터 수집] {symbol} 데이터 다운로드 시작 (기간: {period}, 시작: {start}, 종료: {end})...")
    
    # 데이터 폴더 생성
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        # Ticker 객체 생성
        ticker = yf.Ticker(symbol)
        
        # 데이터 다운로드
        if start and end:
            df = ticker.history(start=start, end=end, interval="1d")
        else:
            df = ticker.history(period=period, interval="1d")
            
        if df.empty:
            print(f"❌ {symbol}에 대한 데이터를 찾을 수 없습니다.")
            return False
            
        # 인덱스(Datetime)를 컬럼으로 변환하고 날짜 포맷 정리
        df = df.reset_index()
        # 시계열 데이터 가공 (Date 형식 포맷 변경 YYYY-MM-DD)
        if 'Date' in df.columns:
            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
        elif 'Datetime' in df.columns:
            df['Date'] = df['Datetime'].dt.strftime('%Y-%m-%d')
            df.drop(columns=['Datetime'], inplace=True)
            
        # 필요한 컬럼만 추출 및 이름 통일
        # yfinance history 결과는 Date, Open, High, Low, Close, Volume, Dividends, Stock Splits
        cols_to_keep = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = df[cols_to_keep]
        
        # CSV 파일 저장 경로
        file_path = os.path.join(data_dir, f"{symbol}.csv")
        df.to_csv(file_path, index=False)
        
        print(f"✅ {symbol} 데이터 저장 완료! 경로: {file_path}")
        print(f"   - 데이터 기간: {df['Date'].iloc[0]} ~ {df['Date'].iloc[-1]} (총 {len(df)} 영업일)")
        return True
        
    except Exception as e:
        print(f"❌ {symbol} 데이터 다운로드 중 오류 발생: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="무한매수법 백테스팅용 주가 데이터 다운로더")
    parser.add_argument("--symbols", type=str, default="TQQQ,SOXL,UPRO", help="다운로드할 종목 기호 (쉼표로 구분)")
    parser.add_argument("--period", type=str, default="5y", help="다운로드 기간 (예: 1y, 3y, 5y, max)")
    parser.add_argument("--start", type=str, default=None, help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="종료 날짜 (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    symbols_list = [s.strip().upper() for s in args.symbols.split(",")]
    
    success_count = 0
    for symbol in symbols_list:
        if download_stock_data(symbol, period=args.period, start=args.start, end=args.end):
            success_count += 1
            
    print(f"\n🎉 전체 작업 완료: {success_count}/{len(symbols_list)} 종목 다운로드 성공.")

if __name__ == "__main__":
    main()
