import os
import json
import time
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

cached_response = None
last_fetch_time = 0
CACHE_DURATION = 1800  # 30 分钟缓存

def analyze_with_deepseek(stock_list):
    if not DEEPSEEK_API_KEY:
        return {
            "sentiment": "乐观",
            "score": "80",
            "summary": "主力资金围绕核心资产展开试探，市场量能维持正常水平。"
        }

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }

    prompt = f"""
你是一名资深 A 股分析师。请根据前端传入的实时股票列表生成简短的市场复盘：
股票数据：{json.dumps(stock_list, ensure_ascii=False)}

请严格返回如下格式 JSON（不要有 markdown 标记）：
{{"sentiment": "乐观", "score": "82", "summary": "100字以内复盘总结"}}
"""

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个只输出 JSON 的金融分析助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
    except Exception as e:
        print(f"DeepSeek 异常: {e}")

    return {
        "sentiment": "中性",
        "score": "75",
        "summary": "大盘维持震荡整理格局，建议关注低估值绩优标的。"
    }

@app.route("/")
def index():
    return "API Running"

@app.route("/api/get-stocks", methods=["POST", "GET"])
def get_stocks_api():
    global cached_response, last_fetch_time
    current_time = time.time()

    # 命中 30 分钟缓存，直接返回历史生成数据，不耗额度
    if cached_response and (current_time - last_fetch_time < CACHE_DURATION):
        return jsonify(cached_response)

    req_data = request.get_json(silent=True) or {}
    stocks = req_data.get("stocks", [])

    ai_analysis = analyze_with_deepseek(stocks)

    response_payload = {
        "code": 200,
        "msg": "success",
        "data": {
            "sentiment": ai_analysis.get("sentiment", "乐观"),
            "score": ai_analysis.get("score", "80"),
            "summary": ai_analysis.get("summary", "")
        }
    }

    cached_response = response_payload
    last_fetch_time = current_time

    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
