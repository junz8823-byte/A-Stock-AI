import os
import json
import requests
import akshare as ak
from flask import Flask, jsonify

app = Flask(__name__)

# 获取环境变量中的 DeepSeek API Key
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

def get_stock_data():
    """获取 A 股全市场实时行情并按成交额筛选标的"""
    try:
        # 使用 akshare 获取实时 A 股行情
        df = ak.stock_zh_a_spot_em()
        # 挑选成交额靠前且涨幅较好的 10 只股票作为示例数据
        df_sorted = df.sort_values(by="成交额", ascending=False).head(10)
        
        stocks = []
        for _, row in df_sorted.iterrows():
            stocks.append({
                "name": str(row["名称"]),
                "code": str(row["代码"]),
                "rate": f"{'+' if row['涨跌幅'] >= 0 else ''}{row['涨跌幅']:.2f}%",
                "price": f"{row['最新价']:.2f}",
                "desc": f"成交额 {row['成交额']/1e8:.2f} 亿，换手率 {row['换手率']}%"
            })
        return stocks
    except Exception as e:
        print(f"抓取 akshare 数据异常: {e}")
        # 降级备用数据
        return [
            {"name": "贵州茅台", "code": "600519", "rate": "+1.20%", "price": "1750.00", "desc": "白酒龙头，资金沉淀"},
            {"name": "宁德时代", "code": "300750", "rate": "+2.50%", "price": "180.50", "desc": "锂电龙头，底部放量"},
            {"name": "招商银行", "code": "600036", "rate": "+0.80%", "price": "32.10", "desc": "高股息资产，估值修复"},
            {"name": "比亚迪", "code": "002594", "rate": "+3.10%", "price": "240.00", "desc": "新能源车出海利好"},
            {"name": "中国平安", "code": "601318", "rate": "+1.15%", "price": "45.20", "desc": "保险龙头，险资沉淀"}
        ]

def analyze_with_deepseek(stock_list):
    """调用 DeepSeek API 进行 A 股大盘与标的复盘分析"""
    if not DEEPSEEK_API_KEY:
        print("未配置 DEEPSEEK_API_KEY，使用默认分析文本")
        return {
            "sentiment": "乐观",
            "score": "78",
            "summary": "市场量能充沛，主力资金偏好大消费与科技成长，建议关注估值修复标的。"
        }

    # 规范的 DeepSeek API 接口 URL（去除了多余的括号与字符）
    url = "https://api.deepseek.com/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    prompt = f"""
你是一名资深 A 股量化与基本面分析师。请根据以下热门股票列表，生成一段简短的市场复盘总结：
股票数据：{json.dumps(stock_list, ensure_ascii=False)}

请严格返回如下格式的 JSON 字符串（不要有任何额外说明，不要包裹 markdown 代码块）：
{{"sentiment": "极佳/乐观/中性/谨慎/悲观", "score": "0-100的分数", "summary": "100字以内的复盘总结"}}
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个只输出结构化 JSON 的金融分析助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            # 尝试解析 AI 返回的 JSON 内容
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(content)
            return analysis_data
        else:
            print(f"DeepSeek API 返回异常: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"请求 DeepSeek 接口异常: {e}")

    # 默认兜底分析
    return {
        "sentiment": "中性偏好",
        "score": "75",
        "summary": "今天主力资金围绕核心资产展开试探，高低切换明显，建议逢低关注超跌低估值标的。"
    }

@app.route("/")
def index():
    return "A-Stock-AI 服务正在运行中！"

@app.route("/api/get-stocks", methods=["GET"])
def get_stocks_api():
    try:
        # 1. 抓取数据
        stocks = get_stock_data()
        # 2. AI 分析
        ai_analysis = analyze_with_deepseek(stocks)

        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "sentiment": ai_analysis.get("sentiment", "乐观"),
                "score": ai_analysis.get("score", "80"),
                "summary": ai_analysis.get("summary", ""),
                "stockList": stocks
            }
        })
    except Exception as e:
        print(f"API 运行发生致命错误: {e}")
        return jsonify({
            "code": 500,
            "error": "生成数据失败，请检查配置或 API Key"
        }), 500

if __name__ == "__main__":
    # Render 会通过 PORT 环境变量传入端口号
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
