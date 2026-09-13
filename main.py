import os
import json
import datetime
import baostock as bs
import pandas as pd
from openai import OpenAI

def fetch_market_data():
    print("正在通过 BaoStock 获取 A 股核心收盘数据...")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 登录 BaoStock 系统
    lg = bs.login()
    if lg.error_code != '0':
        print(f"❌ BaoStock 登录失败: {lg.error_msg}")
        return None

    # 获取上证指数 (sh.000001) 与 创业板指 (sz.399006) 当日数据
    index_list = ["sh.000001", "sz.399006"]
    index_summary = []
    
    for idx in index_list:
        rs = bs.query_history_k_data_plus(
            idx,
            "date,code,close,pctChg,volume,amount",
            start_date=today, end_date=today,
            frequency="d", adjustflag="3"
        )
        if rs.error_code == '0' and len(rs.data) > 0:
            row = rs.data[0]
            name = "上证指数" if idx == "sh.000001" else "创业板指"
            index_summary.append({
                "代码": row[1],
                "名称": name,
                "最新价": row[2],
                "涨跌幅": f"{row[3]}%"
            })
            
    # 退出登录
    bs.logout()

    return {
        "date": today,
        "index_summary": index_summary
    }

def generate_scenarios(market_data):
    print("正在调用 DeepSeek 分析大盘并生成交易情景...")
    
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        print("❌ 错误: 未检测到环境变量 OPENAI_API_KEY，请先设置。")
        return None
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    prompt = f"""
    你是一名资深的 A 股分析师。结合提供的今日大盘收盘数据：
    {json.dumps(market_data, ensure_ascii=False)}
    
    以及你对近期 A 股最新热点（行业板块、高关注度个股与主要指数）的了解，请选出 5 个最值得关注的 [股票·指数·板块]，并为你选出的标的生成交易情景。
    
    请严格按照以下 JSON 数组格式输出，绝对不要带有任何 Markdown 代码块标记（不要写 ```json ）：
    [
      {{
        "type": "股票/指数/板块",
        "name": "标的名称",
        "code": "代码或标识",
        "entry_price": "入场参考价或区间",
        "target_price": "目标价",
        "stop_loss_price": "止损价",
        "rr_ratio": "盈亏比 (如 1:2.5)",
        "technical_basis": "技术面依据说明",
        "fundamental_basis": "基本面及催化剂依据"
      }}
    ]
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            
        return content
    except Exception as e:
        print(f"❌ DeepSeek API 调用失败: {e}")
        return None

if __name__ == "__main__":
    data = fetch_market_data()
    if data:
        scenarios_json_str = generate_scenarios(data)
        if scenarios_json_str:
            os.makedirs("data", exist_ok=True)
            
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            file_path = f"data/{today_str}.json"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(scenarios_json_str)
                
            with open("data/latest.json", "w", encoding="utf-8") as f:
                f.write(scenarios_json_str)
                
            print(f"✅ 成功生成并保存每日交易情景至 {file_path} 与 data/latest.json")