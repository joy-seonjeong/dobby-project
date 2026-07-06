import os
import json
import argparse

def generate_combined_report(symbols_str: str = "TQQQ,SOXL,UPRO"):
    """
    여러 종목의 백테스팅 JSON 결과를 읽어 하나의 탭(Tab) 구분 형식의 통합 HTML 리포트를 생성합니다.
    (원래의 순수한 세전 백테스팅 대시보드로 원복)
    """
    symbols = [s.strip().upper() for s in symbols_str.split(",")]
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 각 종목 데이터 로드
    report_data = {}
    for sym in symbols:
        json_path = os.path.join(current_dir, "data", f"{sym}_backtest_result.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                report_data[sym] = json.load(f)
        else:
            print(f"⚠️ {sym} 백테스트 결과 JSON 파일이 없습니다. (건너뜀)")
            
    if not report_data:
        print("❌ 로드된 백테스트 데이터가 없습니다. 먼저 백테스터를 실행해 주세요.")
        return False

    # HTML 템플릿 시작
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>무한매수법 통합 백테스팅 대시보드</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;700&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #151d30;
            --border-color: #223049;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
            --gradient-blue: linear-gradient(135deg, #2563eb, #3b82f6);
            --gradient-green: linear-gradient(135deg, #059669, #10b981);
            --gradient-red: linear-gradient(135deg, #dc2626, #ef4444);
            --tab-active-bg: rgba(59, 130, 246, 0.15);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Outfit', 'Noto Sans KR', sans-serif;
            padding: 2rem;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* Header */
        header {{
            display: flex;
            flex-direction: column;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .header-title h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            background: linear-gradient(to right, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .header-title p {{
            color: var(--text-secondary);
            font-size: 1.05rem;
            margin-top: 0.25rem;
        }}

        /* Navigation Tabs */
        .tab-menu {{
            display: flex;
            gap: 0.75rem;
            margin-top: 1.5rem;
            flex-wrap: wrap;
        }}

        .tab-button {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.75rem 2rem;
            border-radius: 0.75rem;
            cursor: pointer;
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
            font-size: 1.05rem;
            transition: all 0.2s ease-in-out;
        }}

        .tab-button:hover {{
            color: var(--text-primary);
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }}

        .tab-button.active {{
            color: var(--accent-blue);
            background-color: var(--tab-active-bg);
            border-color: var(--accent-blue);
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
        }}

        /* Panels Container */
        .tab-panel {{
            display: none;
            animation: fadeIn 0.4s ease-in-out;
        }}

        .tab-panel.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
            margin-top: 1rem;
        }}

        .kpi-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
        }}

        .kpi-title {{
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}

        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        .kpi-value.positive {{
            color: var(--accent-green);
        }}

        .kpi-value.negative {{
            color: var(--accent-red);
        }}

        /* Dashboard Body Layout */
        .layout-grid {{
            display: grid;
            grid-template-columns: 2.2fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}

        @media (max-width: 1024px) {{
            .layout-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}

        .panel-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            border-left: 4px solid var(--accent-blue);
            padding-left: 0.75rem;
            color: var(--text-primary);
        }}

        .chart-container {{
            position: relative;
            height: 480px;
            width: 100%;
        }}

        /* Tables styling */
        .comp-table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            margin-bottom: 1rem;
        }}

        .comp-table th, .comp-table td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}

        .comp-table th {{
            font-size: 0.85rem;
            text-transform: uppercase;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .comp-table td {{
            font-size: 0.95rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-top">
                <div class="header-title">
                    <h1>무한매수법 통합 백테스팅 대시보드</h1>
                    <p>정량적 알고리즘 전략 분석 (TQQQ, SOXL, UPRO, QQQI, MSFT)</p>
                </div>
            </div>
            
            <!-- Navigation Tabs -->
            <div class="tab-menu">
        """
        
    # 탭 메뉴 구성
    for idx, sym in enumerate(symbols):
        active_class = "active" if idx == 0 else ""
        display_name = "SOXL (10분할)" if sym == "SOXL_10" else sym
        html_content += f"""
                <button class="tab-button {active_class}" onclick="switchTab(this, '{sym}')">{display_name}</button>
        """
        
    html_content += """
            </div>
        </header>

        <!-- Tab Panels -->
    """
    
    # 각 종목 패널 렌더링
    for idx, (sym, data) in enumerate(report_data.items()):
        panel_active_class = "active" if idx == 0 else ""
        
        # 성과 지표 가공
        success_rate = round(data['success_cycles']/data['total_cycles'] * 100, 1) if data['total_cycles'] > 0 else 0
        total_return_pct = data['total_return_pct']
        cagr_pct = data['cagr_pct']
        mdd_pct = data['mdd_pct']
        
        # 벤치마크 데이터
        dca_return_pct = data.get('dca_return_pct', 0.0)
        dca_mdd_pct = data.get('dca_mdd_pct', 0.0)
        bh_return_pct = data.get('bh_return_pct', 0.0)
        bh_mdd_pct = data.get('bh_mdd_pct', 0.0)
        
        display_sym = "SOXL (10분할)" if sym == "SOXL_10" else sym
        
        html_content += f"""
        <div id="panel-{sym}" class="tab-panel {panel_active_class}">
            <!-- KPI Grid -->
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-title">초기 자본금</div>
                    <div class="kpi-value">${data['total_capital']:,}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">무한매수 최종자산</div>
                    <div class="kpi-value" style="color: #60a5fa">${data['final_assets']:,}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">무한매수 수익률</div>
                    <div class="kpi-value {'positive' if total_return_pct >= 0 else 'negative'}">
                        {total_return_pct:+,}%
                    </div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">무한매수 MDD</div>
                    <div class="kpi-value negative">{mdd_pct}%</div>
                </div>
            </div>

            <!-- Dashboard Body -->
            <div class="layout-grid">
                <!-- Asset Growth Chart Panel -->
                <div class="panel">
                    <div class="panel-title">{display_sym} 전략 vs 벤치마크 자산 성장 & 종가 추이</div>
                    <div class="chart-container">
                        <canvas id="chart-{sym}"></canvas>
                    </div>
                </div>

                <!-- Detail Statistics / Benchmark Panel -->
                <div class="panel" style="display: flex; flex-direction: column; gap: 1.5rem;">
                    <div>
                        <div class="panel-title">전략 간 성과 비교</div>
                        <table class="comp-table">
                            <thead>
                                <tr>
                                    <th>투자 전략</th>
                                    <th>수익률</th>
                                    <th>MDD</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr style="color: #60a5fa; font-weight: 600;">
                                    <td>무한매수법</td>
                                    <td>{total_return_pct:+,}%</td>
                                    <td>{mdd_pct}%</td>
                                </tr>
                                <tr style="color: #10b981;">
                                    <td>주 1회 DCA (적립식)</td>
                                    <td>{dca_return_pct:+,}%</td>
                                    <td>{dca_mdd_pct}%</td>
                                </tr>
                                <tr style="color: #ef4444;">
                                    <td>거치식 (Buy & Hold)</td>
                                    <td>{bh_return_pct:+,}%</td>
                                    <td>{bh_mdd_pct}%</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <div>
                        <div class="panel-title">무한매수법 세부 지표</div>
                        <table class="comp-table">
                            <tbody>
                                <tr>
                                    <td>총 진행 사이클</td>
                                    <td class="stat-val" style="text-align: right; font-weight: 600;">{data['total_cycles']} 회</td>
                                </tr>
                                <tr>
                                    <td>성공(익절) 사이클</td>
                                    <td class="stat-val" style="text-align: right; font-weight: 600; color: var(--accent-green);">{data['success_cycles']} 회 ({success_rate}%)</td>
                                </tr>
                                <tr>
                                    <td>평균 사이클 소요 일수</td>
                                    <td class="stat-val" style="text-align: right; font-weight: 600;">{data['avg_cycle_days']} 일</td>
                                </tr>
                                <tr>
                                    <td>원금 소진 회수 도달</td>
                                    <td class="stat-val" style="text-align: right; font-weight: 600; color: var(--accent-red);">{data['exhausted_cycles_count']} 회</td>
                                </tr>
                                <tr>
                                    <td>역대 최대 도달 회차</td>
                                    <td class="stat-val" style="text-align: right; font-weight: 600;">{data['max_step_reached']} 회차</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """
        
    html_content += """
    </div>

    <script>
        function switchTab(element, symbol) {
            const panels = document.querySelectorAll('.tab-panel');
            panels.forEach(panel => {
                panel.classList.remove('active');
            });
            
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(btn => {
                btn.classList.remove('active');
            });
            
            document.getElementById('panel-' + symbol).classList.add('active');
            element.classList.add('active');
        }
    </script>
    
    <script>
    """
    
    # 각 종목 차트 렌더링 스크립트 개별 작성
    for sym, data in report_data.items():
        dates_json = json.dumps([day["date"] for day in data["daily_history"]])
        assets_json = json.dumps([day["total_assets"] for day in data["daily_history"]])
        dca_assets_json = json.dumps([day.get("dca_assets", 10000.0) for day in data["daily_history"]])
        bh_assets_json = json.dumps([day.get("bh_assets", 10000.0) for day in data["daily_history"]])
        price_json = json.dumps([day["close"] for day in data["daily_history"]])
        
        html_content += f"""
        (function() {{
            const dates = {dates_json};
            const assets = {assets_json};
            const dca_assets = {dca_assets_json};
            const bh_assets = {bh_assets_json};
            const prices = {price_json};

            const ctx = document.getElementById('chart-{sym}').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [
                        {{
                            label: '무한매수법 총자산 ($)',
                            data: assets,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.02)',
                            borderWidth: 2.5,
                            fill: true,
                            yAxisID: 'y-assets',
                            pointRadius: 0,
                            pointHoverRadius: 5
                        }},
                        {{
                            label: '주 1회 DCA 적립식 ($)',
                            data: dca_assets,
                            borderColor: '#10b981',
                            borderWidth: 1.8,
                            fill: false,
                            yAxisID: 'y-assets',
                            pointRadius: 0,
                            pointHoverRadius: 4
                        }},
                        {{
                            label: '거치식 Buy & Hold ($)',
                            data: bh_assets,
                            borderColor: '#ef4444',
                            borderWidth: 1.5,
                            borderDash: [3, 3],
                            fill: false,
                            yAxisID: 'y-assets',
                            pointRadius: 0,
                            pointHoverRadius: 4
                        }},
                        {{
                            label: '{sym} 종가 ($)',
                            data: prices,
                            borderColor: 'rgba(139, 92, 246, 0.45)',
                            borderWidth: 1.5,
                            borderDash: [5, 5],
                            fill: false,
                            yAxisID: 'y-price',
                            pointRadius: 0,
                            pointHoverRadius: 3
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{
                                color: '#9ca3af',
                                font: {{ family: 'Outfit', size: 12 }}
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#151d30',
                            titleColor: '#f3f4f6',
                            bodyColor: '#9ca3af',
                            borderColor: '#223049',
                            borderWidth: 1,
                            titleFont: {{ family: 'Outfit', size: 13 }},
                            bodyFont: {{ family: 'Outfit', size: 12 }}
                        }}
                    }},
                    scales: {{
                        'y-assets': {{
                            type: 'linear',
                            position: 'left',
                            ticks: {{
                                color: '#9ca3af',
                                callback: function(value) {{ return '$' + value.toLocaleString(); }}
                            }},
                            grid: {{ color: '#1e293b' }},
                            title: {{ display: true, text: '자산 가치 ($)', color: '#9ca3af', font: {{ family: 'Outfit' }} }}
                        }},
                        'y-price': {{
                            type: 'linear',
                            position: 'right',
                            ticks: {{ color: '#9ca3af' }},
                            grid: {{ drawOnChartArea: false }},
                            title: {{ display: true, text: '주가 ($)', color: '#9ca3af', font: {{ family: 'Outfit' }} }}
                        }},
                        x: {{
                            ticks: {{ color: '#9ca3af', font: {{ family: 'Outfit', size: 10 }} }},
                            grid: {{ display: false }}
                        }}
                    }}
                }}
            }});
        }})();
        """
        
    html_content += """
    </script>
</body>
</html>
    """
    
    output_path = os.path.join(current_dir, "data", "infinite_buying_backtest_report.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✨ 통합 HTML 백테스트 리포트 생성 완료: {output_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="통합 HTML 리포트 생성기")
    parser.add_argument("--symbols", type=str, default="TQQQ,SOXL,UPRO", help="리포트에 포함할 종목 기호 (콤마 구분)")
    args = parser.parse_args()
    generate_combined_report(args.symbols)
