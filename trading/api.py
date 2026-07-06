from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from db_manager import TossDBManager
from asset_manager import TossAssetManager
import uvicorn

app = FastAPI(title="토스증권 자동매매 대시보드 API", version="1.0.0")

# 프론트엔드 대시보드(Vite React)와의 연동을 위해 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 로컬 개발 단계이므로 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = TossDBManager()

@app.get("/")
def read_root():
    return {"message": "Dobby Project API Server is running!"}

@app.get("/api/assets/history")
def get_assets_history(limit: int = 30):
    """
    최근 N일간의 자산 변동 히스토리를 반환합니다. (성장 곡선 차트용)
    """
    try:
        history = db.get_asset_history(limit=limit)
        return {"status": "success", "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 에러: {str(e)}")

@app.get("/api/assets/current")
def get_current_assets():
    """
    실시간 현재 자산 현황 및 보유 주식 목록을 반환합니다. (실패 시 DB 백업 데이터 로드)
    """
    # 1. 먼저 API로 실시간 데이터를 조회를 시도
    try:
        manager = TossAssetManager()
        summary = manager.get_asset_summary()
        # 실시간 데이터를 받았을 때 DB에도 스냅샷을 백그라운드로 자동 적재
        db.save_asset_snapshot(summary)
        return {"status": "success", "source": "realtime", "data": summary}
    except Exception as e:
        print(f"⚠️ 실시간 자산 조회 실패 (DB 백업 데이터를 로드합니다): {e}")
        
    # 2. 실패 시 DB에 적재된 최신 스냅샷 데이터 조회
    try:
        history = db.get_asset_history(limit=1)
        holdings = db.get_latest_holdings()
        
        if not history:
            raise HTTPException(status_code=404, detail="DB에 저장된 자산 기록이 없습니다.")
            
        latest_history = history[0]
        
        # summary 구조 복원
        summary = {
            "cash": {
                "krw": latest_history["cash_krw"],
                "usd": latest_history["cash_usd"]
            },
            "stock_totals": {
                "total_purchase_krw": latest_history["stock_eval_krw"], # DB 구조상 평가액
                "total_purchase_usd": latest_history["stock_eval_usd"],
                "market_value_krw": latest_history["stock_eval_krw"],
                "market_value_usd": latest_history["stock_eval_usd"],
                "profit_loss_krw": 0,
                "profit_loss_usd": 0,
                "profit_rate": 0
            },
            "items": holdings
        }
        return {"status": "success", "source": "db_backup", "data": summary}
        
    except Exception as db_err:
        raise HTTPException(status_code=500, detail=f"자산 정보 로드 실패: {str(db_err)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
