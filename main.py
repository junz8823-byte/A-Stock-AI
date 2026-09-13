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
    
    请严格按照以下 JSON 格式输出（外层包含 summary 和 details），绝对不要带有任何 Markdown 代码块标记（不要写 ```json ）：
    {{
      "summary": "简短的大盘复盘与整体操作建议总结",
      "details": [
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
    }}
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
            
            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            file_name = f"{today_str}.json"
            file_path = f"data/{file_name}"
            
            # 1. 解析 AI 返回的 JSON 内容
            try:
                parsed_json = json.loads(scenarios_json_str)
                # 加上 date 字段方便前端直接展示
                if isinstance(parsed_json, dict):
                    parsed_json["date"] = today_str
            except Exception as e:
                print(f"⚠️ JSON 解析失败，将直接保存原始文本: {e}")
                parsed_json = scenarios_json_str
            
            # 2. 保存当日数据 (例如 data/2026-09-13.json)
            with open(file_path, "w", encoding="utf-8") as f:
                if isinstance(parsed_json, dict):
                    json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                else:
                    f.write(scenarios_json_str)
                
            # 3. 兼容保存 daily_analysis.json 与 latest.json
            with open("data/daily_analysis.json", "w", encoding="utf-8") as f:
                if isinstance(parsed_json, dict):
                    json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                else:
                    f.write(scenarios_json_str)

            with open("data/latest.json", "w", encoding="utf-8") as f:
                if isinstance(parsed_json, dict):
                    json.dump(parsed_json, f, ensure_ascii=False, indent=2)
                else:
                    f.write(scenarios_json_str)

            # 4. 自动维护历史索引 index.json（供微信小程序横向滑动菜单使用）
            index_path = "data/index.json"
            history_list = []

            if os.path.exists(index_path):
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        history_list = json.load(f)
                except Exception:
                    history_list = []

            new_entry = {"date": today_str, "file": file_name}
            # 如果今天的数据不在索引里，插入到最新位置
            if not any(item.get("date") == today_str for item in history_list):
                history_list.insert(0, new_entry)

            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(history_list, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 成功保存当日数据及索引 index.json 至 data/ 目录！")