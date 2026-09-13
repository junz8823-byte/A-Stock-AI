import json
import os
from datetime import datetime, timedelta
import akshare as ak
from openai import OpenAI

# 初始化 OpenAI 客户端 (适配 DeepSeek API)
import os
from openai import OpenAI

# 明确读取 DEEPSEEK_API_KEY，并设置 DeepSeek 官方的 base_url
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 1. 抓取大盘及热点数据（具备休市自动追溯逻辑）
def fetch_market_data():
    print("开始抓取大盘及市场行情数据...")
    
    today = datetime.now()
    trade_date = None
    df_sh = None

    # 最多向前追溯 10 天，寻找最近的一个有效交易日数据
    for i in range(10):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y%m%d")
        try:
            # 尝试抓取指定日期的上证指数日 K 线
            df_sh = ak.stock_zh_index_daily_em(symbol="sh000001", start_date=date_str, end_date=date_str)
            if not df_sh.empty:
                trade_date = date_str
                print(f"成功获取到交易日 ({trade_date}) 的行情数据")
                break
        except Exception as e:
            continue

    if df_sh is None or df_sh.empty:
        print("警告：未能获取到近期有效的交易日大盘数据")
        return {"date": today.strftime("%Y-%m-%d"), "index_summary": {}}

    # 解析最新交易日上证指数的核心指标
    latest_row = df_sh.iloc[-1]
    close_price = float(latest_row['close'])
    open_price = float(latest_row['open'])
    change_pct = round(((close_price - open_price) / open_price) * 100, 2)
    volume = float(latest_row['volume'])

    market_data = {
        "date": today.strftime("%Y-%m-%d"),
        "trade_date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}",
        "index_summary": {
            "name": "上证指数",
            "close": close_price,
            "change_pct": change_pct,
            "volume": volume
        }
    }
    
    return market_data


# 2. 调用 DeepSeek 进行 AI 复盘分析
def generate_ai_analysis(market_data):
    today_str = market_data["date"]
    prompt = f"""
    你是一个客观专业的 A 股数据分析助手。请根据以下大盘数据进行复盘分析，并输出纯 JSON 格式数据。
    
    传入的数据：{json.dumps(market_data, ensure_ascii=False)}

    严格要求：
    1. 必须包含免责声明和合规表述（不得涉及具体个股买卖建议或承诺收益）。
    2. 如果传入的数据包含指数最新价和涨跌幅，请直接基于该真实数据进行精准总结，严禁在 market_summary 中输出“指数摘要为空”或“无法获取数据”等字眼！
    3. 输出格式必须为合法的 JSON，严格按照如下结构：
    {{
      "date": "{today_str}",
      "disclaimer": "免责声明：本小程序所有数据及 AI 分析内容均基于公开市场数据自动生成，仅供技术研究与信息交流参考，不构成任何投资建议或依据。股市有风险，入市需谨慎。",
      "market_summary": "这里直接填写大盘复盘总结（根据传入的真实点位和涨跌幅分析）",
      "hot_spots": [
        {{
          "name": "板块/指数名称",
          "code": "代码",
          "tag": "指数/板块/股票",
          "range": "观察区区间",
          "resistance": "压力位",
          "support": "支撑位",
          "tech_feature": "技术特征描述",
          "fundamental": "基本面/消息面描述"
        }}
      ]
    }}
    """

    print("正在请求 DeepSeek AI 进行分析...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3
    )

    return response.choices[0].message.content


# 3. 主函数：抓取数据 -> 调用 AI -> 写入 JSON 文件
def main():
    try:
        # 抓取数据
        market_data = fetch_market_data()
        
        # AI 分析
        ai_result_json = generate_ai_analysis(market_data)
        
        # 校验 JSON 格式
        parsed_data = json.loads(ai_result_json)
        
        # 保存为 daily_data.json
        output_path = "daily_data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
        print(f"数据更新完成，已成功写入 {output_path}")

    except Exception as e:
        print(f"运行出现异常: {e}")


if __name__ == "__main__":
    main()