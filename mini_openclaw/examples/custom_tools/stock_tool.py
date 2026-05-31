"""自定义工具示例：股票查询工具"""
from backend.core.registry import tool

@tool(
    name="stock_price",
    description="查询股票价格（使用 Yahoo Finance）",
    parameters={
        "symbol": {"type": "string", "description": "股票代码，如 'AAPL', 'TSLA', '0700.HK'"}
    },
    required=["symbol"]
)
def stock_price_tool(args: dict) -> dict:
    """查询股票价格"""
    symbol = args.get("symbol", "").upper()

    if not symbol:
        return {"success": False, "error": "请提供股票代码"}

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")

        if hist.empty:
            return {"success": False, "error": f"未找到股票 {symbol} 的数据"}

        latest = hist.iloc[-1]
        return {
            "success": True,
            "symbol": symbol,
            "name": info.get("longName", symbol),
            "price": round(latest["Close"], 2),
            "open": round(latest["Open"], 2),
            "high": round(latest["High"], 2),
            "low": round(latest["Low"], 2),
            "volume": int(latest["Volume"]),
            "currency": info.get("currency", "USD"),
            "source": "yahoo_finance"
        }
    except ImportError:
        return {"success": False, "error": "请先安装 yfinance: pip install yfinance"}
    except Exception as e:
        return {"success": False, "error": f"查询失败: {str(e)}"}


@tool(
    name="crypto_price",
    description="查询加密货币价格",
    parameters={
        "coin": {"type": "string", "description": "加密货币代码，如 'bitcoin', 'ethereum'"}
    },
    required=["coin"]
)
def crypto_price_tool(args: dict) -> dict:
    """查询加密货币价格"""
    coin = args.get("coin", "bitcoin").lower()

    try:
        import requests
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin,
            "vs_currencies": "usd,cny",
            "include_24hr_change": "true"
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if coin not in data:
            return {"success": False, "error": f"未找到 {coin} 的价格数据"}

        price_data = data[coin]
        return {
            "success": True,
            "coin": coin,
            "price_usd": price_data["usd"],
            "price_cny": price_data.get("cny", "N/A"),
            "change_24h": f"{price_data.get('usd_24h_change', 0):.2f}%",
            "source": "coingecko"
        }
    except Exception as e:
        return {"success": False, "error": f"查询失败: {str(e)}"}
