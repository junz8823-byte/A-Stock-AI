import os
import json
import requests
import datetime

# ---------------------------------------------------------
# 1. 数据抓取模块（直接调用东方财富官方 REST 接口，保证稳定）
# ---------------------------------------------------------
def fetch_market_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # 获取上证指数行情
    sh_index_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f43,f169,f170,f60,f44,f45,f46,f47,f48"
    try:
        sh_res = requests.get(sh_index_url, headers=headers, timeout=10).json()
        sh_data = sh_res.get("data", {})
    except Exception:
        sh_data = {}
    
    market_summary = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "sh_index": {
            "price": sh_data.get("f43", 0) / 100 if sh_data else "N/A",
            "change_pct": sh_data.get("f170", 0) / 100 if sh_data else "N/A",
            "turnover": f"{round(sh_data.get('f48', 0) / 100000000, 2)}亿" if sh_data else "N/A"
        },
        "raw_notice": "数据来源于东方财富原生实时数据接口"
    }
    
    return market_summary

# ---------------------------------------------------------
# 2. AI 提示词与分析模块（输出 6 大模块 JSON）
# ---------------------------------------------------------
def generate_ai_analysis(market_data):
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or "your_api_key" in api_key:
        print("\n【提示】未检测到有效 API Key，请在终端设置或在代码中填入真实 Key。")
        return None

    prompt = f"""
你是一名专业的 A 股短线顶级游资与量化交易专家。请根据今日 market_data: {json.dumps(market_data, ensure_ascii=False)} 结合你对今日真实 A 股盘面的了解，对今日市场进行深度复盘。

【严格要求】
必须且仅输出标准的合法 JSON，绝对不要包含 ```json 等 Markdown 标记，JSON 结构必须严格包含以下 6 个模块：

{{
  "1_market_overview": {{
    "index_summary": "指数涨跌细节与点位",
    "turnover_total": "两市总成交额及增减量",
    "up_down_count": "上涨/下跌家数比",
    "limit_up_down": "涨停/跌停/炸板家数",
    "market_strength": "强势/震荡/弱势/退潮"
  }},
  "2_emotion_cycle": {{
    "yesterday_top_height": "昨日最高板表现",
    "today_continuous_board": "今日连板梯队（如 4板, 3板, 2板）",
    "bomb_rate": "炸板率 %",
    "core_high_board": "核心高标龙头股票名称与代码",
    "emotion_stage": "发酵/高潮/分歧/修复/退潮"
  }},
  "3_hot_sectors": [
    {{
      "sector_name": "板块名称",
      "today_gain": "涨幅 %",
      "turnover": "成交额",
      "net_inflow": "资金净流入",
      "dragon_leader": "龙头股",
      "core_mid_army": "中军股",
      "follow_up_tier": "补装/梯队股"
    }}
  ],
  "4_stock_selection": {{
    "strong_trend": ["强趋势股1", "强趋势股2"],
    "volume_breakthrough": ["放量突破股1"],
    "first_second_board": ["首板/二板潜力股"],
    "pullback_low_buy": ["回踩低吸标的"],
    "oversold_rebound": ["超跌反弹标的"]
  }},
  "5_news_events": {{
    "policy": ["重要政策1"],
    "company_announcements": ["公司重磅公告"],
    "earnings": ["业绩预告/财报炒作"],
    "industry_news": ["行业利好消息"],
    "overseas_market": ["隔夜美股/外盘动态"]
  }},
  "6_next_day_strategy": {{
    "strongest_direction": "次日最强主线方向",
    "watch_stocks": ["重点观察股票代码/名称"],
    "buy_conditions": "介入必须满足的确认条件",
    "stop_loss": "止损位参考",
    "take_profit": "止盈位参考",
    "risk_warning": "明确风险提示"
  }}
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个严格输出纯 JSON 格式的专业 A 股量化复盘助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        url = "[https://api.deepseek.com/chat/completions](https://api.deepseek.com/chat/completions)"
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        res_json = res.json()
        
        if "choices" not in res_json:
            print("\