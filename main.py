import os
import json
import requests
import datetime

# ---------------------------------------------------------
# 1. 全量数据抓取模块（东方财富原生 REST 接口）
# ---------------------------------------------------------
def fetch_market_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    market_summary = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "sh_index": {},
        "market_stats": {},
        "hot_sectors": []
    }

    try:
        # 1. 抓取主要指数（上证、深证、创业板）
        index_url = "https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f48&secids=1.000001,0.399001,0.399006"
        res = requests.get(index_url, headers=headers, timeout=10).json()
        diff = res.get("data", {}).get("diff", [])
        indices = {}
        for item in diff:
            name = item.get("f14")
            indices[name] = {
                "latest": item.get("f2", 0) / 100,
                "change_pct": f"{item.get('f3', 0) / 100}%",
                "turnover": f"{round(item.get('f48', 0) / 100000000, 2)}亿"
            }
        market_summary["sh_index"] = indices

        # 2. 抓取全市场涨跌统计（涨家数、跌家数、平盘）
        stat_url = "https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&fields=f104,f105,f106&secids=1.000001"
        stat_res = requests.get(stat_url, headers=headers, timeout=10).json()
        stat_data = stat_res.get("data", {}).get("diff", [{}])[0]
        market_summary["market_stats"] = {
            "up_count": stat_data.get("f104", 0),
            "down_count": stat_data.get("f105", 0),
            "flat_count": stat_data.get("f106", 0)
        }

        # 3. 抓取今日行业板块涨幅 Top 5（行业热点）
        sector_url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&ut=bd1d9beb23081e7d01a3556f8f7eb48d&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f3,f12,f14,f62,f184"
        sector_res = requests.get(sector_url, headers=headers, timeout=10).json()
        sector_diff = sector_res.get("data", {}).get("diff", [])
        for sec in sector_diff:
            market_summary["hot_sectors"].append({
                "sector_name": sec.get("f14"),
                "today_gain": f"{sec.get('f3', 0) / 100}%",
                "net_inflow": f"{round(sec.get('f62', 0) / 100000000, 2)}亿"
            })

    except Exception as e:
        print(f"数据抓取出现部分异常（降级处理）: {e}")

    return market_summary

# ---------------------------------------------------------
# 2. AI 提示词与分析模块（输出 6 大模块 JSON）
# ---------------------------------------------------------
def generate_ai_analysis(market_data):
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key or "your_api_key" in api_key:
        print("未检测到有效的 DEEPSEEK_API_KEY！")
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
            print("API 报错返回:", res_json)
            return None
            
        content = res_json['choices'][0]['message']['content']
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"代码运行报错: {e}")
        return None

# ---------------------------------------------------------
# 3. 主流程与文件写入
# ---------------------------------------------------------
def main():
    print("1. 开始抓取市场基础行情数据...")
    raw_data = fetch_market_data()
    
    print("2. 正在调用 DeepSeek 进行 6 大模块复盘分析...")
    ai_result = generate_ai_analysis(raw_data)
    
    if not ai_result:
        print("分析生成失败！")
        return

    os.makedirs("data", exist_ok=True)
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    with open(f"data/{today_str}.json", "w", encoding="utf-8") as f:
        json.dump(ai_result, f, ensure_ascii=False, indent=2)
        
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(ai_result, f, ensure_ascii=False, indent=2)
        
    print(f"成功保存至 data/{today_str}.json")

if __name__ == "__main__":
    main()
