import os
import json
import time
import requests
import datetime
from flask import Flask, jsonify

# 初始化 Flask 应用（Render 需要找到这个 app 对象）
app = Flask(__name__)

# ---------------------------------------------------------
# 1. 全量数据抓取模块
# ---------------------------------------------------------
def fetch_market_data():
    now_ts = int(time.time() * 1000)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Cache-Control": "no-cache"
    }
    
    market_summary = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sh_index": {},
        "market_stats": {},
        "hot_sectors": [],
        "rebound_candidates": []
    }

    try:
        # 抓取主要指数
        index_url = f"https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f48,f124&secids=1.000001,0.399001,0.399006&_={now_ts}"
        res = requests.get(index_url, headers=headers, timeout=10).json()
        diff = res.get("data", {}).get("diff", [])
        indices = {}
        for item in diff:
            name = item.get("f14")
            indices[name] = {
                "latest": item.get("f2", 0) / 100 if item.get("f2") != "-" else 0,
                "change_pct": f"{item.get('f3', 0) / 100}%",
                "turnover": f"{round(item.get('f48', 0) / 100000000, 2)}亿"
            }
        market_summary["sh_index"] = indices

        # 抓取全市场实时涨跌家数
        stat_url = f"https://push2.eastmoney.com/api/qt/ulist/get?fltt=2&invt=2&fields=f104,f105,f106&secids=1.000001&_={now_ts}"
        stat_res = requests.get(stat_url, headers=headers, timeout=10).json()
        stat_data = stat_res.get("data", {}).get("diff", [{}])[0]
        market_summary["market_stats"] = {
            "up_count": stat_data.get("f104", 0),
            "down_count": stat_data.get("f105", 0),
            "flat_count": stat_data.get("f106", 0)
        }

        # 抓取今日行业板块涨幅 Top 5
        sector_url = f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&ut=bd1d9beb23081e7d01a3556f8f7eb48d&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f3,f12,f14,f62&_={now_ts}"
        sector_res = requests.get(sector_url, headers=headers, timeout=10).json()
        sector_diff = sector_res.get("data", {}).get("diff", [])
        for sec in sector_diff:
            market_summary["hot_sectors"].append({
                "sector_name": sec.get("f14"),
                "today_gain": f"{sec.get('f3', 0) / 100}%",
                "net_inflow": f"{round(sec.get('f62', 0) / 100000000, 2)}亿"
            })

        # 抓取筑底反弹备选标的
        rebound_url = f"https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&ut=bd1d9beb23081e7d01a3556f8f7eb48d&fltt=2&invt=2&fid=f62&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14,f2,f3,f8,f62,f184&_={now_ts}"
        rebound_res = requests.get(rebound_url, headers=headers, timeout=10).json()
        rebound_diff = rebound_res.get("data", {}).get("diff", [])
        for stock in rebound_diff:
            market_summary["rebound_candidates"].append({
                "code": stock.get("f12"),
                "name": stock.get("f14"),
                "price": stock.get("f2", 0) / 100 if stock.get("f2") != "-" else 0,
                "change_pct": round(stock.get("f3", 0) / 100, 2),
                "turnover_rate": f"{stock.get('f8', 0) / 100}%",
                "net_inflow": f"{round(stock.get('f62', 0) / 100000000, 2)}亿"
            })

    except Exception as e:
        print(f"数据抓取出现异常: {e}")

    return market_summary

# ---------------------------------------------------------
# 2. AI 提示词与分析模块
# ---------------------------------------------------------
def generate_ai_analysis(market_data):
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("未检测到有效的 DEEPSEEK_API_KEY！")
        return None

    prompt = f"""
你是一名专业的 A 股短线顶级游资与量化交易专家。请根据今日 market_data: {json.dumps(market_data, ensure_ascii=False)} 结合你对今日真实 A 股盘面的了解，对今日市场进行深度复盘。

【特别指示】
请重点参考 rebound_candidates 候选池数据，精选出 **10 个具备筑底/超跌反弹/主力突破特征** 的重点标的，填入 `bottom_rebound_10` 数组中。

【严格要求】
必须且仅输出标准的合法 JSON，绝对不要包含 ```json 等 Markdown 标记，JSON 结构必须严格包含以下模块：

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
      "dragon_leader": "龙头股"
    }}
  ],
  "bottom_rebound_10": [
    {{
      "name": "股票名称",
      "code": "代码(如600519.SH)",
      "change": 2.45,
      "reason": "简短AI反弹逻辑观点(20字以内)"
    }}
  ],
  "6_next_day_strategy": {{
    "strongest_direction": "次日最强主线方向",
    "watch_stocks": ["重点观察股票代码/名称"],
    "buy_conditions": "介入必须满足的确认条件",
    "stop_loss": "止损位参考",
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
# 3. 提供给微信小程序调用的 API 路由接口
# ---------------------------------------------------------
@app.route('/')
def home():
    return "A-Stock-AI 服务正在运行中！"

@app.route('/api/get-stocks', methods=['GET'])
def get_stocks_api():
    raw_data = fetch_market_data()
    ai_result = generate_ai_analysis(raw_data)
    
    if ai_result:
        return jsonify(ai_result)
    else:
        return jsonify({"error": "生成数据失败，请检查配置或 API Key"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
