"""
Unit tests for atomic.decisions

100% coverage target - 纯函数测试
"""

import pytest
from decimal import Decimal

from atomic.models import (
    Position,
    FundingRate,
    ExchangeIdentifier,
    Symbol,
    ArbitrageConfig,
    TradingSignal
)
from atomic.decisions import (
    FundingArbitrageDecision,
    RebalanceDecision,
    SafetyDecision,
    ActionType
)


@pytest.fixture
def symbol():
    """Fixture: 标准Symbol"""
    return Symbol(base="BTC", quote="USDT", contract_type="PERP")


@pytest.fixture
def config():
    """Fixture: 标准ArbitrageConfig"""
    return ArbitrageConfig(
        build_threshold=Decimal("0.05"),  # 5% APR
        close_threshold=Decimal("0.02"),  # 2% APR
        max_position=Decimal("10"),
        trade_size=Decimal("0.1"),
        max_imbalance=Decimal("0.3")
    )


class TestFundingArbitrageDecision:
    """Test FundingArbitrageDecision"""

    def test_analyze_opportunity_not_enough_exchanges(self, config):
        """Test with less than 2 exchanges"""
        rates = {
            "grvt": FundingRate(
                exchange=ExchangeIdentifier("grvt"),
                symbol=Symbol("BTC", "USDT", "PERP"),
                rate=Decimal("0.0001"),
                interval_hours=8
            )
        }
        positions = {}

        result = FundingArbitrageDecision.analyze_opportunity(rates, positions, config)
        assert result is None

    def test_analyze_opportunity_build_signal(self, symbol, config):
        """Test BUILD signal generation"""
        # 设置高费率差: 10.95% vs 43.8% APR = 32.85% spread
        rates = {
            "grvt": FundingRate(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                rate=Decimal("0.0001"),  # 10.95% APR (8h)
                interval_hours=8
            ),
            "lighter": FundingRate(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                rate=Decimal("0.00005"),  # 43.8% APR (1h)
                interval_hours=1
            )
        }

        positions = {
            "grvt": Position(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                quantity=Decimal("0"),
                side="none"
            ),
            "lighter": Position(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                quantity=Decimal("0"),
                side="none"
            )
        }

        result = FundingArbitrageDecision.analyze_opportunity(rates, positions, config)

        assert result is not None
        assert isinstance(result, TradingSignal)
        assert len(result.legs) == 2
        assert "BUILD" in result.reason
        assert result.confidence == Decimal("0.8")

    def test_analyze_opportunity_winddown_signal(self, symbol, config):
        """Test WINDDOWN signal generation"""
        # 设置低费率差: 小于2% APR
        # grvt: 0.000005 * 3 * 365 = 0.5475% APR
        # lighter: 0.000002 * 24 * 365 = 1.7520% APR
        # spread = 1.2045% < 2% threshold
        rates = {
            "grvt": FundingRate(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                rate=Decimal("0.000005"),
                interval_hours=8
            ),
            "lighter": FundingRate(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                rate=Decimal("0.000002"),
                interval_hours=1
            )
        }

        # 有现存仓位
        positions = {
            "grvt": Position(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                quantity=Decimal("5"),
                side="long"
            ),
            "lighter": Position(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                quantity=Decimal("5"),
                side="short"
            )
        }

        result = FundingArbitrageDecision.analyze_opportunity(rates, positions, config)

        assert result is not None
        assert "WINDDOWN" in result.reason
        assert result.confidence == Decimal("0.9")

    def test_analyze_opportunity_hold(self, symbol, config):
        """Test HOLD (no signal) case"""
        # 费率差在阈值之间 (2% < spread < 5%)
        # grvt: 0.00001 * 3 * 365 = 1.095% APR
        # lighter: 0.000012 * 24 * 365 = 10.512% APR
        # spread = 9.417% > 5%, 会BUILD，我们需要更小的差值
        # 改为：grvt: 0.00001 * 3 * 365 = 1.095%, lighter: 0.000004 * 24 * 365 = 3.504%
        # spread = 2.409% APR (在2%-5%之间，但没有仓位所以不会平仓，也不够大不会建仓)
        rates = {
            "grvt": FundingRate(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                rate=Decimal("0.00001"),
                interval_hours=8
            ),
            "lighter": FundingRate(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                rate=Decimal("0.000004"),
                interval_hours=1
            )
        }

        positions = {
            "grvt": Position(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                quantity=Decimal("0"),
                side="none"
            )
        }

        result = FundingArbitrageDecision.analyze_opportunity(rates, positions, config)
        assert result is None

    def test_analyze_opportunity_position_limit_reached(self, symbol, config):
        """Test BUILD blocked by position limit"""
        rates = {
            "grvt": FundingRate(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                rate=Decimal("0.0001"),
                interval_hours=8
            ),
            "lighter": FundingRate(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                rate=Decimal("0.00005"),
                interval_hours=1
            )
        }

        # 已达最大仓位
        positions = {
            "grvt": Position(
                exchange=ExchangeIdentifier("grvt"),
                symbol=symbol,
                quantity=Decimal("10"),  # = max_position
                side="long"
            ),
            "lighter": Position(
                exchange=ExchangeIdentifier("lighter"),
                symbol=symbol,
                quantity=Decimal("0"),
                side="none"
            )
        }

        result = FundingArbitrageDecision.analyze_opportunity(rates, positions, config)
        assert result is None

    def test_find_best_rate_pair(self, symbol):
        """Test finding best rate pair"""
        rates = {
            "grvt": FundingRate(ExchangeIdentifier("grvt"), symbol, Decimal("0.0001"), 8),
            "lighter": FundingRate(ExchangeIdentifier("lighter"), symbol, Decimal("0.00005"), 1),
            "binance": FundingRate(ExchangeIdentifier("binance"), symbol, Decimal("0.00008"), 8)
        }

        result = FundingArbitrageDecision._find_best_rate_pair(rates)

        assert result is not None
        exchange_high, exchange_low, spread, rate_high, rate_low = result
        # Lighter should have highest annual rate
        assert exchange_high == "lighter"


class TestRebalanceDecision:
    """Test RebalanceDecision"""

    def test_analyze_imbalance_not_enough_exchanges(self, symbol, config):
        """Test with less than 2 exchanges"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("5"),
                "long"
            )
        }

        result = RebalanceDecision.analyze_imbalance(positions, config, symbol)
        assert result is None

    def test_analyze_imbalance_balanced(self, symbol, config):
        """Test balanced positions"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("5"),
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("5"),
                "short"
            )
        }

        result = RebalanceDecision.analyze_imbalance(positions, config, symbol)
        assert result is None  # imbalance = 0, within tolerance

    def test_analyze_imbalance_needs_rebalance_long(self, symbol, config):
        """Test net long exposure needs rebalance"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("10"),
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("5"),
                "short"
            )
        }

        result = RebalanceDecision.analyze_imbalance(positions, config, symbol)

        assert result is not None
        assert len(result.legs) == 1
        assert result.legs[0].side == "sell"  # 需要卖出减少多头
        assert "REBALANCE" in result.reason
        assert result.confidence == Decimal("1.0")

    def test_analyze_imbalance_needs_rebalance_short(self, symbol, config):
        """Test net short exposure needs rebalance"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("3"),
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("10"),
                "short"
            )
        }

        result = RebalanceDecision.analyze_imbalance(positions, config, symbol)

        assert result is not None
        assert result.legs[0].side == "buy"  # 需要买入减少空头

    def test_analyze_imbalance_quantity_limited(self, symbol, config):
        """Test rebalance quantity limited by trade_size"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("20"),  # Large imbalance
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("0"),
                "none"
            )
        }

        result = RebalanceDecision.analyze_imbalance(positions, config, symbol)

        # 应该限制为trade_size
        assert result.legs[0].quantity == config.trade_size


class TestSafetyDecision:
    """Test SafetyDecision"""

    def test_check_position_limits_safe(self, symbol, config):
        """Test position limits - safe"""
        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("5"),
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("5"),
                "short"
            )
        }

        is_safe, reason = SafetyDecision.check_position_limits(positions, config)

        assert is_safe is True
        assert reason is None

    def test_check_position_limits_per_exchange_exceeded(self, symbol, config):
        """Test single exchange position limit exceeded"""
        config.max_position_per_exchange = Decimal("10")

        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("15"),  # Exceeds limit
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("5"),
                "short"
            )
        }

        is_safe, reason = SafetyDecision.check_position_limits(positions, config)

        assert is_safe is False
        assert "grvt" in reason
        assert "exceeds limit" in reason

    def test_check_position_limits_total_exposure_exceeded(self, symbol, config):
        """Test total exposure limit exceeded"""
        config.max_total_exposure = Decimal("5")

        positions = {
            "grvt": Position(
                ExchangeIdentifier("grvt"),
                symbol,
                Decimal("8"),
                "long"
            ),
            "lighter": Position(
                ExchangeIdentifier("lighter"),
                symbol,
                Decimal("2"),
                "short"
            )
        }
        # Total exposure = 8 - 2 = 6 > 5

        is_safe, reason = SafetyDecision.check_position_limits(positions, config)

        assert is_safe is False
        assert "Total exposure" in reason

    def test_check_pending_orders_safe(self):
        """Test pending orders - safe"""
        pending_counts = {
            "grvt": 1,
            "lighter": 2
        }

        is_safe, exchange = SafetyDecision.check_pending_orders(
            pending_counts,
            max_per_exchange=3
        )

        assert is_safe is True
        assert exchange is None

    def test_check_pending_orders_exceeded(self):
        """Test pending orders exceeded"""
        pending_counts = {
            "grvt": 2,
            "lighter": 5  # Exceeds limit
        }

        is_safe, exchange = SafetyDecision.check_pending_orders(
            pending_counts,
            max_per_exchange=3
        )

        assert is_safe is False
        assert exchange == "lighter"

    def test_check_pending_orders_multiple_exceeded(self):
        """Test multiple exchanges exceeded (returns first)"""
        pending_counts = {
            "grvt": 5,
            "lighter": 4,
            "binance": 3
        }

        is_safe, exchange = SafetyDecision.check_pending_orders(
            pending_counts,
            max_per_exchange=3
        )

        assert is_safe is False
        assert exchange is not None  # One of them


class TestActionType:
    """Test ActionType enum"""

    def test_action_types_exist(self):
        """Test all action types exist"""
        assert ActionType.BUILD
        assert ActionType.HOLD
        assert ActionType.WINDDOWN
        assert ActionType.REBALANCE

    def test_action_type_values(self):
        """Test action type values"""
        assert ActionType.BUILD.value == "BUILD"
        assert ActionType.HOLD.value == "HOLD"
        assert ActionType.WINDDOWN.value == "WINDDOWN"
        assert ActionType.REBALANCE.value == "REBALANCE"
