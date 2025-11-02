"""
测试Lighter数据获取
"""

import asyncio
import os
from decimal import Decimal
from pathlib import Path
import dotenv

# 加载环境变量
env_paths = [Path(".env"), Path("../.env"), Path("/app/.env")]
for env_path in env_paths:
    if env_path.exists():
        dotenv.load_dotenv(env_path, override=True)
        break

from exchanges.lighter import LighterClient
from atomic import Symbol, AtomicQueryer


class Config:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


async def main():
    print("="*60)
    print("Testing Lighter Exchange")
    print("="*60)

    try:
        # 初始化配置
        config = Config(
            ticker="BTC",
            quantity=Decimal("0.1"),
            direction="",
            close_order_side=""
        )

        print("\n1. Initializing Lighter client...")
        client = LighterClient(config)

        print("2. Connecting to Lighter...")
        await client.connect()
        print("   ✓ Connected")

        # 创建AtomicQueryer
        symbol = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        queryer = AtomicQueryer(client, symbol)

        # 获取市场数据
        print("\n3. Fetching market data...")
        market = await queryer.get_market()
        print(f"   Best Bid: {market.best_bid}")
        print(f"   Best Ask: {market.best_ask}")
        print(f"   Mid Price: {market.mid_price}")
        if market.spread:
            print(f"   Spread: {market.spread} ({market.spread_bps:.2f} bps)")

        # 获取资金费率
        print("\n4. Fetching funding rate...")
        funding = await queryer.get_funding_rate()
        print(f"   Raw Rate: {funding.rate} ({funding.rate * 100:.6f}%)")
        print(f"   Interval: {funding.interval_hours} hours")
        print(f"   Annual Rate: {funding.annual_rate * 100:.2f}% APR")
        print(f"   Daily Rate: {funding.daily_rate * 100:.4f}%")

        # 获取仓位
        print("\n5. Fetching position...")
        position = await queryer.get_position()
        print(f"   Side: {position.side}")
        print(f"   Quantity: {position.quantity}")
        print(f"   Signed Quantity: {position.signed_quantity}")

        print("\n6. Disconnecting...")
        await client.disconnect()
        print("   ✓ Disconnected")

        print("\n" + "="*60)
        print("✅ Test completed successfully!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
