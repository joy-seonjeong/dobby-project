import { useState, useEffect } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import { 
  TrendingUp, Wallet, DollarSign, BarChart3, AlertCircle, RefreshCw, Layers
} from 'lucide-react';


interface AssetSummary {
  cash: {
    krw: number;
    usd: number;
  };
  stock_totals: {
    total_purchase_krw: number;
    total_purchase_usd: number;
    market_value_krw: number;
    market_value_usd: number;
    profit_loss_krw: number;
    profit_loss_usd: number;
    profit_rate: number;
  };
  items: Array<{
    symbol: string;
    name: string;
    country: string;
    currency: string;
    quantity: number;
    last_price: number;
    purchase_price: number;
    purchase_amount: number;
    market_value: number;
    profit_loss: number;
    profit_rate: number;
  }>;
}

interface HistoryItem {
  timestamp: string;
  cash_krw: number;
  cash_usd: number;
  stock_eval_krw: number;
  stock_eval_usd: number;
  total_eval_krw: number;
}

const API_BASE_URL = 'http://localhost:8000';
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#14b8a6', '#f43f5e'];

// 📡 오프라인/정적배포 환경을 위한 고품질 가상 데모 자산 데이터셋
const OFFLINE_DEMO_DATA: AssetSummary = {
  cash: { krw: 5200000, usd: 3450.0 },
  stock_totals: {
    total_purchase_krw: 12400000,
    total_purchase_usd: 8900.0,
    market_value_krw: 14850000,
    market_value_usd: 10650.0,
    profit_loss_krw: 2450000,
    profit_loss_usd: 1750.0,
    profit_rate: 0.1975
  },
  items: [
    { symbol: 'TQQQ', name: 'ProShares UltraPro QQQ', country: 'US', currency: 'USD', quantity: 80, last_price: 76.80, purchase_price: 70.00, purchase_amount: 5600, market_value: 6144, profit_loss: 544, profit_rate: 0.0971 },
    { symbol: 'SOXL', name: 'Direxion Daily Semiconductor Bull 3X', country: 'US', currency: 'USD', quantity: 20, last_price: 165.28, purchase_price: 150.00, purchase_amount: 3000, market_value: 3305.6, profit_loss: 305.6, profit_rate: 0.1019 },
    { symbol: 'UPRO', name: 'ProShares UltraPro S&P500', country: 'US', currency: 'USD', quantity: 50, last_price: 78.50, purchase_price: 75.00, purchase_amount: 3750, market_value: 3925, profit_loss: 175, profit_rate: 0.0466 }
  ]
};

const OFFLINE_HISTORY_DATA: HistoryItem[] = Array.from({ length: 30 }).map((_, i) => {
  const date = new Date();
  date.setDate(date.getDate() - (30 - i));
  const baseVal = 17500000;
  const variance = Math.sin(i * 0.5) * 600000 + (i * 80000); // 점진적 성장 모사
  return {
    timestamp: date.toISOString().split('T')[0],
    cash_krw: 5200000,
    cash_usd: 3450.0,
    stock_eval_krw: 12400000 + variance,
    stock_eval_usd: 8900.0,
    total_eval_krw: baseVal + variance
  };
});

export default function App() {
  const [activeMenu, setActiveMenu] = useState<'assets' | 'mock' | 'backtest'>('assets');
  const [current, setCurrent] = useState<AssetSummary | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string>('offline');

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. 실시간 자산 로드
      const currentRes = await fetch(`${API_BASE_URL}/api/assets/current`);
      if (!currentRes.ok) throw new Error('실시간 자산 조회 실패');
      const currentJson = await currentRes.json();
      setCurrent(currentJson.data);
      setSource(currentJson.source);

      // 2. 히스토리 로드
      const historyRes = await fetch(`${API_BASE_URL}/api/assets/history`);
      if (!historyRes.ok) throw new Error('자산 추이 조회 실패');
      const historyJson = await historyRes.json();
      setHistory(historyJson.data);
      
    } catch (err: any) {
      // 📡 깃허브 Pages 등 정적 오프라인 환경일 경우 안전하게 가상/샘플 데이터셋으로 롤백하여 UI 제공
      console.log("💡 로컬 API 서버 미연결로 데모 가상 자산 데이터를 출력합니다.");
      setCurrent(OFFLINE_DEMO_DATA);
      setHistory(OFFLINE_HISTORY_DATA);
      setSource('offline_demo');
      setError(null); // 사용자가 불안해하지 않도록 정적 모드에서는 연결장애 경고 카드를 띄우지 않습니다.
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading && !current) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '1rem', backgroundColor: '#0b0f19', color: '#f3f4f6' }}>
        <RefreshCw size={40} className="pulse-dot" style={{ animation: 'spin 2s linear infinite', background: 'transparent' }} />
        <p style={{ color: 'var(--text-secondary)' }}>자산 포털 데이터를 불러오는 중...</p>
      </div>
    );
  }

  const cashKrw = current?.cash.krw || 0;
  const cashUsd = current?.cash.usd || 0;
  const stockEvalKrw = current?.stock_totals.market_value_krw || 0;
  
  const exchangeRate = 1380; 
  const totalAssetsKrw = cashKrw + (cashUsd * exchangeRate) + stockEvalKrw;
  const profitLossKrw = current?.stock_totals.profit_loss_krw || 0;
  const profitRate = current?.stock_totals.profit_rate || 0;

  const pieData = current?.items.map(item => ({
    name: item.name,
    value: item.country === 'KR' ? item.market_value : item.market_value * exchangeRate
  })) || [];

  const formatXAxis = (tickItem: string) => {
    try {
      const date = new Date(tickItem);
      return `${date.getMonth() + 1}/${date.getDate()}`;
    } catch {
      return tickItem;
    }
  };

  return (
    <div className="container">
      {/* 헤더 */}
      <header className="header">
        <div className="header-title">
          <h1>Dobby Portal 🚀</h1>
          <p>경제적 자유를 향한 개인 자산 관리 및 자동매매 통합 허브</p>
        </div>
        
        {/* 상단 통합 탭 네비게이션 메뉴바 추가 */}
        <nav className="nav-tabs">
          <button 
            className={`nav-tab-btn ${activeMenu === 'assets' ? 'active' : ''}`}
            onClick={() => setActiveMenu('assets')}
          >
            <Wallet size={16} />
            내 자산 포트폴리오
          </button>
          <button 
            className={`nav-tab-btn ${activeMenu === 'mock' ? 'active' : ''}`}
            onClick={() => setActiveMenu('mock')}
          >
            <Layers size={16} />
            무한매수 모의투자
          </button>
          <button 
            className={`nav-tab-btn ${activeMenu === 'backtest' ? 'active' : ''}`}
            onClick={() => setActiveMenu('backtest')}
          >
            <BarChart3 size={16} />
            백테스팅 리포트
          </button>
        </nav>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {activeMenu === 'assets' && (
            <button 
              onClick={fetchData} 
              style={{ 
                background: 'rgba(255,255,255,0.05)', 
                border: '1px solid var(--border-color)', 
                color: 'var(--text-primary)', 
                padding: '0.5rem', 
                borderRadius: '8px', 
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <RefreshCw size={18} />
            </button>
          )}
          <div className={`status-badge ${error ? 'error' : ''}`}>
            <span className={`pulse-dot ${error ? 'error' : ''}`}></span>
            {error ? '서버 연결 실패' : source === 'realtime' ? '실시간 연동 중' : source === 'offline_demo' ? '데모(정적) 모드' : '로컬 DB 로드'}
          </div>
        </div>
      </header>

      {error && activeMenu === 'assets' && (
        <div className="card" style={{ border: '1px solid var(--color-danger)', background: 'rgba(239, 68, 68, 0.05)', marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <AlertCircle color="var(--color-danger)" />
          <div>
            <h4 style={{ color: 'var(--text-primary)' }}>연결 장애 안내</h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.125rem' }}>{error}. 터미널에서 FastAPI 서버(api.py)가 켜져 있는지 확인해 주세요.</p>
          </div>
        </div>
      )}

      {/* 1. 내 자산 포트폴리오 탭 렌더링 */}
      {activeMenu === 'assets' && (
        <>
          <section className="summary-container">
            <div className="card summary-card">
              <div className="summary-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Wallet size={16} color="var(--color-accent)" />
                총 자산 (원화 환산)
              </div>
              <div className="summary-value">{totalAssetsKrw.toLocaleString('ko-KR')}원</div>
              <div className="summary-change change-up" style={{ fontSize: '0.8125rem' }}>
                ※ 적용 환율: 1 USD = 1,380 KRW
              </div>
            </div>

            <div className="card summary-card">
              <div className="summary-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <DollarSign size={16} color="var(--color-success)" />
                보유 예수금
              </div>
              <div className="summary-value" style={{ fontSize: '1.5rem' }}>
                {cashKrw.toLocaleString('ko-KR')}원
              </div>
              <div className="summary-change" style={{ color: 'var(--text-secondary)' }}>
                외화: ${cashUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
              </div>
            </div>

            <div className="card summary-card">
              <div className="summary-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TrendingUp size={16} color={profitLossKrw >= 0 ? "var(--color-success)" : "var(--color-danger)"} />

                주식 평가 손익
              </div>
              <div className="summary-value" style={{ color: profitLossKrw >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                {profitLossKrw >= 0 ? '+' : ''}{profitLossKrw.toLocaleString('ko-KR')}원
              </div>
              <div className={`summary-change ${profitRate >= 0 ? 'change-up' : 'change-down'}`}>
                수익률: {profitRate >= 0 ? '+' : ''}{(profitRate * 100).toFixed(2)}%
              </div>
            </div>
          </section>

          <section className="dashboard-grid" style={{ marginBottom: '1.5rem' }}>
            <div className="card col-8">
              <h3 className="card-title">
                <BarChart3 size={18} color="var(--color-accent)" />
                자산 성장 추이 (최근 30일)
              </h3>
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer>
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--color-accent)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="var(--color-accent)" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis 
                      dataKey="timestamp" 
                      tickFormatter={formatXAxis} 
                      stroke="var(--text-muted)"
                      style={{ fontSize: '0.75rem' }}
                    />
                    <YAxis 
                      stroke="var(--text-muted)" 
                      style={{ fontSize: '0.75rem' }}
                      tickFormatter={(v) => `${(v / 10000).toLocaleString()}만`}
                    />
                    <Tooltip 
                      contentStyle={{ 
                        background: 'var(--bg-secondary)', 
                        border: '1px solid var(--border-color)', 
                        borderRadius: '8px',
                        color: 'var(--text-primary)'
                      }}
                      labelFormatter={(label) => new Date(label).toLocaleDateString()}
                      formatter={(value: any) => [`${Number(value).toLocaleString()}원`, '총 자산']}
                    />
                    <Area 
                      type="monotone" 
                      dataKey="total_eval_krw" 
                      stroke="var(--color-accent)" 
                      fillOpacity={1} 
                      fill="url(#colorTotal)" 
                      strokeWidth={2}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="card col-4">
              <h3 className="card-title">
                <TrendingUp size={18} color="var(--color-success)" />
                자산 포트폴리오 비중
              </h3>
              <div style={{ width: '100%', height: 200, display: 'flex', justifyContent: 'center' }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}

                    </Pie>
                    <Tooltip formatter={(value: any) => `${Number(value).toLocaleString()}원`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center', marginTop: '1rem' }}>
                {pieData.map((entry, index) => (
                  <div key={entry.name} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: COLORS[index % COLORS.length] }}></span>
                    {entry.name}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="card">
            <h3 className="card-title">보유 주식 상세 현황</h3>
            <div style={{ overflowX: 'auto' }}>
              <table className="asset-table">
                <thead>
                  <tr>
                    <th>종목코드</th>
                    <th>종목명</th>
                    <th>보유수량</th>
                    <th>평균매수가</th>
                    <th>현재가</th>
                    <th>평가금액 (달러/원화)</th>
                    <th>평가손익</th>
                    <th>수익률</th>
                  </tr>
                </thead>
                <tbody>
                  {current?.items.map(item => {
                    const isUs = item.country === 'US';
                    const currencySymbol = isUs ? '$' : '₩';
                    const evalUsd = isUs ? item.market_value : item.market_value / exchangeRate;
                    const evalKrw = isUs ? item.market_value * exchangeRate : item.market_value;
                    const profitLossColor = item.profit_loss >= 0 ? 'var(--color-success)' : 'var(--color-danger)';
                    return (
                      <tr key={item.symbol}>
                        <td style={{ fontWeight: 600 }}>{item.symbol}</td>
                        <td style={{ color: 'var(--text-secondary)' }}>{item.name}</td>
                        <td>{item.quantity.toFixed(2)}주</td>
                        <td>{currencySymbol}{item.purchase_price.toLocaleString()}</td>
                        <td>{currencySymbol}{item.last_price.toLocaleString()}</td>
                        <td>
                          <div>${evalUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>≈ {Math.round(evalKrw).toLocaleString()}원</div>
                        </td>
                        <td style={{ color: profitLossColor, fontWeight: 600 }}>
                          {item.profit_loss >= 0 ? '+' : ''}{item.profit_loss.toLocaleString()}
                        </td>
                        <td style={{ color: profitLossColor, fontWeight: 600 }}>
                          {item.profit_rate >= 0 ? '+' : ''}{(item.profit_rate * 100).toFixed(2)}%
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* 2. 무한매수 모의투자 iframe 임베드 */}
      {activeMenu === 'mock' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden', height: 'calc(100vh - 140px)', border: '1px solid var(--border-color)' }}>
          <iframe 
            src="./trading/data/virtual_trading_report.html" 
            style={{ width: '100%', height: '100%', border: 'none', background: 'transparent' }} 
            title="Dobby Project 무한매수 모의투자 대시보드"
          />
        </div>
      )}

      {/* 3. 백테스팅 결과 보고서 iframe 임베드 */}
      {activeMenu === 'backtest' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden', height: 'calc(100vh - 140px)', border: '1px solid var(--border-color)' }}>
          <iframe 
            src="./trading/data/infinite_buying_backtest_report.html" 
            style={{ width: '100%', height: '100%', border: 'none', background: 'transparent' }} 
            title="Dobby Project 무한매수 백테스팅 성과 분석 보고서"
          />
        </div>
      )}
    </div>
  );
}
