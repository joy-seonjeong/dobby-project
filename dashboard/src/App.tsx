import { useState, useEffect } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { 
  TrendingUp, Wallet, DollarSign, BarChart3, AlertCircle, RefreshCw 
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

// 파이 차트 색상 목록
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#06b6d4', '#14b8a6', '#f43f5e'];

export default function App() {
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
      setError(err.message || 'API 연결 에러가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading && !current) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '1rem' }}>
        <RefreshCw size={40} className="pulse-dot" style={{ animation: 'spin 2s linear infinite', background: 'transparent' }} />
        <p style={{ color: 'var(--text-secondary)' }}>자산 데이터를 불러오는 중...</p>
      </div>
    );
  }

  // 총 원화 자산 계산 (자체 계산: 원화 예수금 + 달러 예수금 환산액 + 주식 평가 원화 환산액)
  // 여기서는 단순히 예수금 + 주식 평가액으로 합산
  const cashKrw = current?.cash.krw || 0;
  const cashUsd = current?.cash.usd || 0;
  const stockEvalKrw = current?.stock_totals.market_value_krw || 0;
  
  // 환율은 API 결과상 유추하거나 1380원 기본 적용
  const exchangeRate = 1380; 
  const totalAssetsKrw = cashKrw + (cashUsd * exchangeRate) + stockEvalKrw;
  const profitLossKrw = current?.stock_totals.profit_loss_krw || 0;
  const profitRate = current?.stock_totals.profit_rate || 0;

  // 차트용 보유 주식 데이터 정제
  const pieData = current?.items.map(item => ({
    name: item.name,
    // 원화 환산액으로 비중 파악
    value: item.country === 'KR' ? item.market_value : item.market_value * exchangeRate
  })) || [];

  // 날짜 형식 포맷팅용 헬퍼
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
          <h1>Dobby Asset Dashboard 🚀</h1>
          <p>경제적 자유를 위한 토스증권 포트폴리오 모니터링</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
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
          <div className={`status-badge ${error ? 'error' : ''}`}>
            <span className={`pulse-dot ${error ? 'error' : ''}`}></span>
            {error ? '서버 연결 실패' : source === 'realtime' ? '실시간 연동 중' : '로컬 DB 데이터 로드'}
          </div>
        </div>
      </header>

      {error && (
        <div className="card" style={{ border: '1px solid var(--color-danger)', background: 'rgba(239, 68, 68, 0.05)', marginBottom: '1.5rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <AlertCircle color="var(--color-danger)" />
          <div>
            <h4 style={{ color: 'var(--text-primary)' }}>연결 장애 안내</h4>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.125rem' }}>{error}. 터미널에서 FastAPI 서버(api.py)가 켜져 있는지 확인해 주세요.</p>
          </div>
        </div>
      )}

      {/* 요약 카드 섹션 */}
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
            외화: ${cashUsd.toFixed(2)} USD
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

      {/* 차트 그리드 */}
      <section className="dashboard-grid" style={{ marginBottom: '1.5rem' }}>
        {/* 자산 성장 곡선 차트 (Line/Area) */}
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
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorTotal)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 자산 비중 원형 차트 (Pie) */}
        <div className="card col-4">
          <h3 className="card-title">포트폴리오 비중</h3>
          <div style={{ width: '100%', height: 220 }}>
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
                <Tooltip 
                  contentStyle={{ 
                    background: 'var(--bg-secondary)', 
                    border: '1px solid var(--border-color)', 
                    borderRadius: '8px' 
                  }}
                  formatter={(value: any) => [`${Number(value).toLocaleString()}원`, '평가액']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'center', marginTop: '0.5rem', fontSize: '0.75rem' }}>
            {pieData.map((entry, index) => (
              <span key={entry.name} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', color: 'var(--text-secondary)' }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: COLORS[index % COLORS.length] }}></span>
                {entry.name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* 보유 종목 상세 테이블 */}
      <section className="card col-12">
        <h3 className="card-title">보유 종목 상세 현황</h3>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>종목명</th>
                <th>시장</th>
                <th>보유수량</th>
                <th>매입단가</th>
                <th>현재가</th>
                <th>평가금액</th>
                <th>평가손익</th>
                <th>수익률</th>
              </tr>
            </thead>
            <tbody>
              {current?.items.map((item) => {
                const currency = item.currency;
                const isKr = item.country === 'KR';
                const formatPrice = (v: number) => isKr ? `${v.toLocaleString('ko-KR')}원` : `$${v.toFixed(2)}`;
                
                return (
                  <tr key={item.symbol}>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <span style={{ fontWeight: 600 }}>{item.name}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{item.symbol}</span>
                      </div>
                    </td>
                    <td>
                      <span className="symbol-badge">{item.country}</span>
                    </td>
                    <td>{item.quantity}주</td>
                    <td>{formatPrice(item.purchase_price)}</td>
                    <td>{formatPrice(item.last_price)}</td>
                    <td>{formatPrice(item.market_value)}</td>
                    <td className="profit-text" style={{ color: item.profit_loss >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                      {item.profit_loss >= 0 ? '+' : ''}{formatPrice(item.profit_loss)}
                    </td>
                    <td className="profit-text" style={{ color: item.profit_rate >= 0 ? 'var(--color-success)' : 'var(--color-danger)' }}>
                      {item.profit_rate >= 0 ? '+' : ''}{(item.profit_rate * 100).toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
