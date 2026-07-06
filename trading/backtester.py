import os
import argparse
import json
import pandas as pd
import numpy as np
from datetime import datetime

def run_backtest(symbol: str, total_capital: float = 10000.0, divisions: int = 40, target_profit_rate: float = 0.10):
    """
    무한매수법 백테스팅을 실행합니다. (원래의 단순 세전 백테스터로 원복)
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "data", f"{symbol.split('_')[0]}.csv")
    
    if not os.path.exists(file_path):
        alt_path = os.path.join(current_dir, "data", f"{symbol}.csv")
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            print(f"❌ {symbol}의 데이터 파일이 존재하지 않습니다. 먼저 data_downloader.py를 실행하세요.")
            return None
        
    df = pd.read_csv(file_path)
    if df.empty:
        print(f"❌ {symbol} 데이터가 비어 있습니다.")
        return None

    df = df.sort_values(by="Date").reset_index(drop=True)
    
    # 1회차 매수 한도액
    one_time_limit = total_capital / divisions
    
    # 상태 변수
    cash = total_capital
    holdings = 0.0
    total_purchase_amount = 0.0
    average_price = 0.0
    cycle_count = 0
    current_division_step = 0
    
    # 벤치마크 1: 거치식 (Buy & Hold)
    first_close = float(df["Close"].iloc[0])
    bh_holdings = total_capital / first_close
    
    # 벤치마크 2: 주 1회 DCA
    dca_cash = total_capital
    dca_holdings = 0.0
    dca_buy_count = 0
    total_weeks = len(df) // 5
    weekly_dca_amount = total_capital / total_weeks if total_weeks > 0 else 0.0
    
    history = []
    cycles = []
    current_cycle = None
    is_active = False
    
    for i, row in df.iterrows():
        date_str = row["Date"]
        close_p = float(row["Close"])
        high_p = float(row["High"])
        
        # [A] 무한매수법
        is_sold = False
        if is_active and holdings > 0:
            target_sell_price = average_price * (1.0 + target_profit_rate)
            if high_p >= target_sell_price:
                revenue = holdings * target_sell_price
                cash += revenue
                is_sold = True
                is_active = False
                
                # 사이클 종료 기록
                if current_cycle:
                    current_cycle["end_date"] = date_str
                    current_cycle["revenue"] = round(revenue, 2)
                    current_cycle["profit"] = round(revenue - current_cycle["purchase_amount"], 2)
                    current_cycle["profit_rate"] = round(target_profit_rate * 100, 2)
                    current_cycle["status"] = "PROFIT"
                    cycles.append(current_cycle)
                    current_cycle = None
                
                holdings = 0.0
                total_purchase_amount = 0.0
                average_price = 0.0
                current_division_step = 0
                
        if not is_active:
            is_active = True
            cycle_count += 1
            current_division_step = 1
            buy_qty = 1.0
            buy_amt = buy_qty * close_p
            cash -= buy_amt
            holdings += buy_qty
            total_purchase_amount += buy_amt
            average_price = close_p
            
            current_cycle = {
                "cycle_no": cycle_count,
                "start_date": date_str,
                "max_step": 1,
                "purchase_amount": round(buy_amt, 2),
                "status": "RUNNING"
            }
        else:
            if current_division_step < divisions and cash >= one_time_limit:
                current_division_step += 1
                
                if symbol.endswith("_10") or divisions == 10:
                    # SOXL 10분할 하루 최대 1주 가변 룰
                    total_bought_qty = 1.0
                else:
                    # 40분할
                    avg_bought_qty = round((one_time_limit * 0.5) / close_p, 4) if close_p <= average_price else 0.0
                    high_bought_qty = round((one_time_limit * 0.5) / close_p, 4)
                    total_bought_qty = avg_bought_qty + high_bought_qty
                
                total_bought_amt = total_bought_qty * close_p
                cash -= total_bought_amt
                holdings += total_bought_qty
                total_purchase_amount += total_bought_amt
                average_price = total_purchase_amount / holdings
                
                if current_cycle:
                    current_cycle["max_step"] = current_division_step
                    current_cycle["purchase_amount"] = round(total_purchase_amount, 2)

        # [B] 벤치마크 2: 주 1회 DCA
        if i % 5 == 0 and dca_buy_count < divisions and dca_cash >= weekly_dca_amount:
            dca_buy_count += 1
            dca_bought_qty = weekly_dca_amount / close_p
            dca_cash -= weekly_dca_amount
            dca_holdings += dca_bought_qty

        # 일자별 가치 정산
        port_val = holdings * close_p
        tot_assets = cash + port_val
        bh_assets = bh_holdings * close_p
        dca_assets = dca_cash + (dca_holdings * close_p)
        
        history.append({
            "date": date_str,
            "close": close_p,
            "total_assets": round(tot_assets, 2),
            "profit_rate_pct": round(((tot_assets - total_capital) / total_capital) * 100, 2),
            "bh_assets": round(bh_assets, 2),
            "dca_assets": round(dca_assets, 2)
        })

    # 미종료 사이클 정리
    if current_cycle:
        current_cycle["status"] = "RUNNING"
        cycles.append(current_cycle)

    # 최종 결과 마감 산출
    final_raw_assets = history[-1]["total_assets"]
    final_bh_assets = history[-1]["bh_assets"]
    final_dca_assets = history[-1]["dca_assets"]
    
    raw_return = ((final_raw_assets - total_capital) / total_capital) * 100
    bh_return = ((final_bh_assets - total_capital) / total_capital) * 100
    dca_return = ((final_dca_assets - total_capital) / total_capital) * 100
    
    history_df = pd.DataFrame(history)
    start_date = datetime.strptime(history_df["date"].iloc[0], "%Y-%m-%d")
    end_date = datetime.strptime(history_df["date"].iloc[-1], "%Y-%m-%d")
    years = (end_date - start_date).days / 365.25
    
    # CAGR & MDD
    def calculate_metrics(col_name):
        peak = history_df[col_name].cummax()
        drawdown = (history_df[col_name] - peak) / peak
        mdd = drawdown.min() * 100
        cagr = (((history_df[col_name].iloc[-1] / total_capital) ** (1 / years) - 1) * 100) if years > 0 else 0.0
        return round(cagr, 2), round(mdd, 2)
        
    raw_cagr, raw_mdd = calculate_metrics("total_assets")
    bh_cagr, bh_mdd = calculate_metrics("bh_assets")
    dca_cagr, dca_mdd = calculate_metrics("dca_assets")
    
    success_cycles_count = sum(1 for c in cycles if c.get("status") == "PROFIT")
    exhausted_cycles_count = sum(1 for c in cycles if c.get("max_step", 0) >= divisions)
    max_step_reached = max(c.get("max_step", 0) for c in cycles) if cycles else divisions
    
    # 사이클 일수 계산
    cycle_days = []
    for c in cycles:
        if "end_date" in c:
            diff = (datetime.strptime(c["end_date"], "%Y-%m-%d") - datetime.strptime(c["start_date"], "%Y-%m-%d")).days
            cycle_days.append(diff)
    avg_cycle_days = np.mean(cycle_days) if cycle_days else 70.0
    
    report = {
        "symbol": symbol,
        "total_capital": total_capital,
        "final_assets": round(final_raw_assets, 2),
        "total_return_pct": round(raw_return, 2),
        "cagr_pct": raw_cagr,
        "mdd_pct": raw_mdd,
        "bh_return_pct": round(bh_return, 2),
        "bh_cagr_pct": bh_cagr,
        "bh_mdd_pct": bh_mdd,
        "dca_return_pct": round(dca_return, 2),
        "dca_cagr_pct": dca_cagr,
        "dca_mdd_pct": dca_mdd,
        "total_cycles": cycle_count,
        "success_cycles": success_cycles_count,
        "avg_cycle_days": round(avg_cycle_days, 1),
        "max_step_reached": max_step_reached,
        "exhausted_cycles_count": exhausted_cycles_count,
        "cycles": cycles,
        "daily_history": history
    }
    
    output_dir = os.path.join(current_dir, "data")
    output_file = os.path.join(output_dir, f"{symbol}_backtest_result.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
        
    print(f"📊 {symbol} 백테스팅 완료! (세전 원복)")
    return report

def main():
    parser = argparse.ArgumentParser(description="백테스팅 원복 스크립트")
    parser.add_argument("--symbol", type=str, default="TQQQ")
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--divisions", type=int, default=40)
    parser.add_argument("--target_rate", type=float, default=0.10)
    args = parser.parse_args()
    
    run_backtest(
        symbol=args.symbol.upper(),
        total_capital=args.capital,
        divisions=args.divisions,
        target_profit_rate=args.target_rate
    )

if __name__ == "__main__":
    main()
