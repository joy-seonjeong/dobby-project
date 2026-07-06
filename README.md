# 경제적 자유 프로젝트 (Dobby Project) 🚀

이 프로젝트는 경제적 자유를 달성하기 위한 두 가지 핵심 시스템을 개발합니다.

## 🎯 주요 목표

1. **자산 시뮬레이션 및 자산 현황 대시보드 (`dashboard/`)**
   - 현재 자산 현황 시각화 (예적금, 주식, 부동산 등 포트폴리오 비중)
   - 은퇴 시점, 투자 수익률, 인플레이션 등을 고려한 자산 성장 시뮬레이터 제공
   
2. **주식 자동매매 프로그램 (`trading/`)**
   - 증권사 API 연동을 통한 자동 거래 루프 구현
   - 투자 전략 백테스팅 엔진 개발 및 실전 매매 자동 수행

---

## 📂 폴더 구조

```text
dobby-project/
├── dashboard/          # 자산 시뮬레이션 및 현황 대시보드 (React/Vite 프론트엔드)
├── trading/            # 주식 자동매매 및 백테스팅 (Python 백엔드)
│   ├── config/         # API 키 및 기본 설정
│   ├── strategy/       # 매매 전략 및 로직
│   ├── backtest/       # 과거 데이터를 활용한 전략 검증
│   ├── execution/      # 실제 주문 집행 및 API 연동
│   └── data/           # 로컬 시세 데이터 및 거래 로그 저장소
├── .agents/            # Antigravity 에이전트 설정
│   ├── AGENTS.md       # 에이전트 개발 규칙
│   └── skills/         # 에이전트용 특화 스킬
├── .gitignore          # Git 제외 파일 목록 설정
└── README.md           # 프로젝트 전체 안내서 (현재 파일)
```

---

## 🛠️ 개발 시작하기

### 1. Dashboard (Front-end)
*상세 내용은 대시보드 내부 README를 참고하세요.*
```bash
cd dashboard
npm install
npm run dev
```

### 2. Trading (Back-end)
*상세 내용은 트레이딩 내부 README를 참고하세요.*
```bash
cd trading
python -m venv .venv
source .venv/bin/activate  # macOS
pip install -r requirements.txt
python main.py
```
