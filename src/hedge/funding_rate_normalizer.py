"""
资金费率归一化模块 - 纯函数。

职责：
1. 将不同周期的funding rate归一化为年化费率（APR）
2. 计算费率差的年化收益
3. 不依赖任何外部状态
"""

from decimal import Decimal
from typing import NamedTuple
from datetime import timedelta


class FundingRateData(NamedTuple):
    """单个交易所的资金费率数据"""
    rate: Decimal              # 原始费率（如0.0001 = 0.01%）
    interval_hours: int        # 结算周期（小时）
    exchange_name: str         # 交易所名称


class NormalizedFundingRate(NamedTuple):
    """归一化后的资金费率"""
    original_rate: Decimal     # 原始费率
    interval_hours: int        # 结算周期
    annual_rate: Decimal       # 年化费率（APR）
    daily_rate: Decimal        # 日化费率
    exchange_name: str


class FundingRateSpread(NamedTuple):
    """费率差信息（归一化后）"""
    grvt_normalized: NormalizedFundingRate
    lighter_normalized: NormalizedFundingRate
    annual_spread: Decimal     # 年化费率差
    daily_spread: Decimal      # 日化费率差
    profitable_side: str       # 盈利方向（"long"或"short"）


class FundingRateNormalizer:
    """
    资金费率归一化器 - 纯函数式设计。

    常见的funding周期：
    - Binance: 8小时（3次/天）
    - OKX: 8小时（3次/天）
    - Bybit: 8小时（3次/天）
    - dYdX: 1小时（24次/天）
    - GMX: 连续（每秒）
    - GRVT: 需要API查询
    - Lighter: 需要API查询
    """

    @staticmethod
    def normalize_to_annual(funding_data: FundingRateData) -> NormalizedFundingRate:
        """
        将资金费率归一化为年化费率（APR）。

        公式：
        annual_rate = rate × (24 / interval_hours) × 365

        例如：
        - 费率0.01%，周期8小时：0.0001 × (24/8) × 365 = 10.95% APR
        - 费率0.01%，周期1小时：0.0001 × (24/1) × 365 = 87.6% APR

        Args:
            funding_data: 原始费率数据

        Returns:
            NormalizedFundingRate: 归一化后的费率
        """
        if funding_data.interval_hours <= 0:
            raise ValueError(f"Invalid interval_hours: {funding_data.interval_hours}")

        # 每天的结算次数
        settlements_per_day = Decimal(24) / Decimal(funding_data.interval_hours)

        # 日化费率
        daily_rate = funding_data.rate * settlements_per_day

        # 年化费率
        annual_rate = daily_rate * Decimal(365)

        return NormalizedFundingRate(
            original_rate=funding_data.rate,
            interval_hours=funding_data.interval_hours,
            annual_rate=annual_rate,
            daily_rate=daily_rate,
            exchange_name=funding_data.exchange_name
        )

    @staticmethod
    def calculate_spread(
        grvt_data: FundingRateData,
        lighter_data: FundingRateData
    ) -> FundingRateSpread:
        """
        计算两个交易所之间的归一化费率差。

        费率差 = GRVT年化费率 - Lighter年化费率

        正值：GRVT收费率更高，做空GRVT + 做多Lighter盈利
        负值：Lighter收费率更高，做多GRVT + 做空Lighter盈利

        Args:
            grvt_data: GRVT费率数据
            lighter_data: Lighter费率数据

        Returns:
            FundingRateSpread: 费率差信息
        """
        # 归一化两边的费率
        grvt_normalized = FundingRateNormalizer.normalize_to_annual(grvt_data)
        lighter_normalized = FundingRateNormalizer.normalize_to_annual(lighter_data)

        # 计算费率差（年化）
        annual_spread = grvt_normalized.annual_rate - lighter_normalized.annual_rate
        daily_spread = grvt_normalized.daily_rate - lighter_normalized.daily_rate

        # 判断盈利方向
        # 如果GRVT费率更高（正spread），做空GRVT（收费率）+ 做多Lighter（付费率）= 盈利
        # 如果Lighter费率更高（负spread），做多GRVT（付费率）+ 做空Lighter（收费率）= 盈利
        if annual_spread > 0:
            # GRVT费率高 → 做空GRVT
            profitable_side = "short"
        elif annual_spread < 0:
            # Lighter费率高 → 做多GRVT（实际是做空Lighter）
            profitable_side = "long"
        else:
            # 费率相同，无套利空间
            profitable_side = "neutral"

        return FundingRateSpread(
            grvt_normalized=grvt_normalized,
            lighter_normalized=lighter_normalized,
            annual_spread=annual_spread,
            daily_spread=daily_spread,
            profitable_side=profitable_side
        )

    @staticmethod
    def estimate_profit(
        spread: FundingRateSpread,
        position_size: Decimal,
        holding_days: Decimal
    ) -> Decimal:
        """
        估算持仓期间的费率收益。

        收益 = abs(annual_spread) × position_size × (holding_days / 365)

        Args:
            spread: 费率差信息
            position_size: 仓位大小（USD）
            holding_days: 持仓天数

        Returns:
            Decimal: 预估收益（USD）
        """
        # 使用年化费率差计算
        annual_return = abs(spread.annual_spread) * position_size

        # 按持仓天数折算
        estimated_profit = annual_return * (holding_days / Decimal(365))

        return estimated_profit

    @staticmethod
    def format_rate_info(spread: FundingRateSpread) -> str:
        """
        格式化费率信息为可读字符串。

        Args:
            spread: 费率差信息

        Returns:
            str: 格式化的字符串
        """
        grvt = spread.grvt_normalized
        lighter = spread.lighter_normalized

        info = []
        info.append(f"GRVT: {grvt.original_rate:.4%} ({grvt.interval_hours}h) → {grvt.annual_rate:.2%} APR")
        info.append(f"Lighter: {lighter.original_rate:.4%} ({lighter.interval_hours}h) → {lighter.annual_rate:.2%} APR")
        info.append(f"Spread: {spread.annual_spread:+.2%} APR (Daily: {spread.daily_spread:+.4%})")
        info.append(f"Strategy: {spread.profitable_side.upper()}")

        return " | ".join(info)


# 示例使用
if __name__ == "__main__":
    # 示例1：GRVT 8小时周期，Lighter 1小时周期
    grvt = FundingRateData(
        rate=Decimal("0.0001"),  # 0.01%
        interval_hours=8,
        exchange_name="GRVT"
    )

    lighter = FundingRateData(
        rate=Decimal("0.00005"),  # 0.005%
        interval_hours=1,
        exchange_name="Lighter"
    )

    spread = FundingRateNormalizer.calculate_spread(grvt, lighter)

    print("=== Funding Rate Arbitrage Analysis ===")
    print(FundingRateNormalizer.format_rate_info(spread))
    print()

    # 估算收益：1000 USD仓位，持有7天
    profit = FundingRateNormalizer.estimate_profit(
        spread=spread,
        position_size=Decimal("1000"),
        holding_days=Decimal("7")
    )
    print(f"Estimated 7-day profit on $1000: ${profit:.2f}")
