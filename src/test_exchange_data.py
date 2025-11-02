"""
测试从Backpack和Lighter获取数据
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path
import dotenv

# 加载环境变量
env_paths = [Path(".env"), Path("../.env"), Path("/app/.env")]
for env_path in env_paths:
    if env_path.exists():
        dotenv.load_dotenv(env_path, override=True)
        break

# 导入交易所客户端
from exchanges.backpack import BackpackClient
from exchanges.lighter import LighterClient

# 导入原子化框架
from atomic import Symbol, AtomicQueryer


class Config:
    """配置类"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


async def test_backpack():
    """测试Backpack"""
    print("\n" + "="*60)
    print("Testing Backpack")
    print("="*60)

    try:
        # 初始化Backpack客户端
        config = Config(
            ticker="BTC",
            quantity=Decimal("0.1")
        )

        client = BackpackClient(config)
        await client.connect()
        print("✓ Backpack connected")

        # 创建AtomicQueryer
        symbol = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        queryer = AtomicQueryer(client, symbol)

        # 获取市场数据
        print("\n📊 Market Data:")
        market = await queryer.get_market()
        print(f"  Best Bid: {market.best_bid}")
        print(f"  Best Ask: {market.best_ask}")
        print(f"  Mid Price: {market.mid_price}")
        print(f"  Spread: {market.spread} ({market.spread_bps:.2f} bps)" if market.spread else "  Spread: N/A")

        # 获取资金费率
        print("\n💰 Funding Rate:")
        funding = await queryer.get_funding_rate()
        print(f"  Rate: {funding.rate} ({funding.rate * 100:.4f}%)")
        print(f"  Interval: {funding.interval_hours} hours")
        print(f"  Annual Rate: {funding.annual_rate * 100:.2f}% APR")
        print(f"  Daily Rate: {funding.daily_rate * 100:.4f}%")

        # 获取仓位
        print("\n📈 Position:")
        position = await queryer.get_position()
        print(f"  Side: {position.side}")
        print(f"  Quantity: {position.quantity}")
        print(f"  Signed Quantity: {position.signed_quantity}")

        await client.disconnect()
        print("\n✓ Backpack test completed")
        return True

    except Exception as e:
        print(f"\n❌ Backpack test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_lighter():
    """测试Lighter"""
    print("\n" + "="*60)
    print("Testing Lighter")
    print("="*60)

    try:
        # 初始化Lighter客户端
        config = Config(
            ticker="BTC",
            quantity=Decimal("0.1"),
            direction="",
            close_order_side=""
        )

        client = LighterClient(config)
        await client.connect()
        print("✓ Lighter connected")

        # 创建AtomicQueryer
        symbol = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        queryer = AtomicQueryer(client, symbol)

        # 获取市场数据
        print("\n📊 Market Data:")
        market = await queryer.get_market()
        print(f"  Best Bid: {market.best_bid}")
        print(f"  Best Ask: {market.best_ask}")
        print(f"  Mid Price: {market.mid_price}")
        print(f"  Spread: {market.spread} ({market.spread_bps:.2f} bps)" if market.spread else "  Spread: N/A")

        # 获取资金费率
        print("\n💰 Funding Rate:")
        funding = await queryer.get_funding_rate()
        print(f"  Rate: {funding.rate} ({funding.rate * 100:.4f}%)")
        print(f"  Interval: {funding.interval_hours} hours")
        print(f"  Annual Rate: {funding.annual_rate * 100:.2f}% APR")
        print(f"  Daily Rate: {funding.daily_rate * 100:.4f}%")

        # 获取仓位
        print("\n📈 Position:")
        position = await queryer.get_position()
        print(f"  Side: {position.side}")
        print(f"  Quantity: {position.quantity}")
        print(f"  Signed Quantity: {position.signed_quantity}")

        await client.disconnect()
        print("\n✓ Lighter test completed")
        return True

    except Exception as e:
        print(f"\n❌ Lighter test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_comparison():
    """对比两个交易所的数据"""
    print("\n" + "="*60)
    print("Comparison: Backpack vs Lighter")
    print("="*60)

    try:
        # 初始化客户端
        backpack_config = Config(ticker="BTC", quantity=Decimal("0.1"))
        lighter_config = Config(ticker="BTC", quantity=Decimal("0.1"), direction="", close_order_side="")

        backpack_client = BackpackClient(backpack_config)
        lighter_client = LighterClient(lighter_config)

        await backpack_client.connect()
        await lighter_client.connect()
        print("✓ Both exchanges connected")

        symbol = Symbol(base="BTC", quote="USDT", contract_type="PERP")

        backpack_queryer = AtomicQueryer(backpack_client, symbol)
        lighter_queryer = AtomicQueryer(lighter_client, symbol)

        # 获取数据
        print("\n📊 Fetching data from both exchanges...")
        backpack_market = await backpack_queryer.get_market()
        lighter_market = await lighter_queryer.get_market()

        backpack_funding = await backpack_queryer.get_funding_rate()
        lighter_funding = await lighter_queryer.get_funding_rate()

        # 对比价格
        print("\n💵 Price Comparison:")
        print(f"  Backpack Mid: {backpack_market.mid_price}")
        print(f"  Lighter Mid:  {lighter_market.mid_price}")
        if backpack_market.mid_price and lighter_market.mid_price:
            price_diff = abs(backpack_market.mid_price - lighter_market.mid_price)
            price_diff_pct = (price_diff / backpack_market.mid_price) * 100
            print(f"  Difference:   {price_diff} ({price_diff_pct:.4f}%)")

        # 对比费率
        print("\n💰 Funding Rate Comparison:")
        print(f"  Backpack: {backpack_funding.rate * 100:.4f}% ({backpack_funding.interval_hours}h) → {backpack_funding.annual_rate * 100:.2f}% APR")
        print(f"  Lighter:  {lighter_funding.rate * 100:.4f}% ({lighter_funding.interval_hours}h) → {lighter_funding.annual_rate * 100:.2f}% APR")

        spread = abs(backpack_funding.annual_rate - lighter_funding.annual_rate)
        print(f"\n  📈 Funding Spread: {spread * 100:.2f}% APR")

        if spread > Decimal("0.05"):  # 5% APR
            print(f"  ✅ Potential arbitrage opportunity!")
        else:
            print(f"  ℹ️  Spread below threshold (5% APR)")

        await backpack_client.disconnect()
        await lighter_client.disconnect()
        print("\n✓ Comparison completed")
        return True

    except Exception as e:
        print(f"\n❌ Comparison failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("Exchange Data Test Suite")
    print("="*60)

    results = {
        "Backpack": False,
        "Lighter": False,
        "Comparison": False
    }

    # 测试Backpack
    results["Backpack"] = await test_backpack()

    # 测试Lighter
    results["Lighter"] = await test_lighter()

    # 对比测试
    if results["Backpack"] and results["Lighter"]:
        results["Comparison"] = await test_comparison()

    # 总结
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print("\n" + ("="*60))
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("⚠️  Some tests failed")
    print("="*60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
