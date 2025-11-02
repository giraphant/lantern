"""
Unit tests for atomic.models

100% coverage target
"""

import pytest
from decimal import Decimal
from datetime import datetime

from atomic.models import (
    ExchangeIdentifier,
    Symbol,
    Position,
    FundingRate,
    Order,
    Market,
    TradeLeg,
    TradingSignal,
    ArbitrageConfig
)


class TestExchangeIdentifier:
    """Test ExchangeIdentifier"""

    def test_create_simple(self):
        """Test creating exchange identifier without instance_id"""
        ex = ExchangeIdentifier(name="grvt")
        assert ex.name == "grvt"
        assert ex.instance_id is None

    def test_create_with_instance(self):
        """Test creating exchange identifier with instance_id"""
        ex = ExchangeIdentifier(name="grvt", instance_id="account1")
        assert ex.name == "grvt"
        assert ex.instance_id == "account1"

    def test_str_simple(self):
        """Test string representation without instance_id"""
        ex = ExchangeIdentifier(name="lighter")
        assert str(ex) == "lighter"

    def test_str_with_instance(self):
        """Test string representation with instance_id"""
        ex = ExchangeIdentifier(name="lighter", instance_id="main")
        assert str(ex) == "lighter:main"

    def test_hash(self):
        """Test hashing for dict keys"""
        ex1 = ExchangeIdentifier(name="grvt")
        ex2 = ExchangeIdentifier(name="grvt")
        ex3 = ExchangeIdentifier(name="lighter")

        assert hash(ex1) == hash(ex2)
        assert hash(ex1) != hash(ex3)

    def test_hashable_in_dict(self):
        """Test can be used as dict key"""
        ex = ExchangeIdentifier(name="binance")
        d = {ex: "test"}
        assert d[ex] == "test"

    def test_frozen(self):
        """Test immutability"""
        ex = ExchangeIdentifier(name="grvt")
        with pytest.raises(Exception):  # dataclass frozen
            ex.name = "changed"


class TestSymbol:
    """Test Symbol"""

    def test_create(self):
        """Test creating symbol"""
        sym = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        assert sym.base == "BTC"
        assert sym.quote == "USDT"
        assert sym.contract_type == "PERP"

    def test_str(self):
        """Test string representation"""
        sym = Symbol(base="ETH", quote="USD", contract_type="SPOT")
        assert str(sym) == "ETH-USD-SPOT"

    def test_hash(self):
        """Test hashing"""
        sym1 = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        sym2 = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        sym3 = Symbol(base="ETH", quote="USDT", contract_type="PERP")

        assert hash(sym1) == hash(sym2)
        assert hash(sym1) != hash(sym3)

    def test_frozen(self):
        """Test immutability"""
        sym = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        with pytest.raises(Exception):
            sym.base = "ETH"


class TestPosition:
    """Test Position"""

    def test_create_long(self):
        """Test creating long position"""
        ex = ExchangeIdentifier(name="grvt")
        sym = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        pos = Position(
            exchange=ex,
            symbol=sym,
            quantity=Decimal("5.0"),
            side="long"
        )

        assert pos.exchange == ex
        assert pos.symbol == sym
        assert pos.quantity == Decimal("5.0")
        assert pos.side == "long"

    def test_create_short(self):
        """Test creating short position"""
        ex = ExchangeIdentifier(name="lighter")
        sym = Symbol(base="BTC", quote="USDT", contract_type="PERP")
        pos = Position(
            exchange=ex,
            symbol=sym,
            quantity=Decimal("3.5"),
            side="short",
            entry_price=Decimal("50000")
        )

        assert pos.side == "short"
        assert pos.entry_price == Decimal("50000")

    def test_signed_quantity_long(self):
        """Test signed_quantity for long position"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("10"),
            side="long"
        )
        assert pos.signed_quantity == Decimal("10")

    def test_signed_quantity_short(self):
        """Test signed_quantity for short position"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("10"),
            side="short"
        )
        assert pos.signed_quantity == Decimal("-10")

    def test_signed_quantity_none(self):
        """Test signed_quantity for no position"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("0"),
            side="none"
        )
        assert pos.signed_quantity == Decimal("0")

    def test_value_with_price(self):
        """Test position value calculation"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("2.5"),
            side="long",
            entry_price=Decimal("50000")
        )
        assert pos.value == Decimal("125000")  # 2.5 * 50000

    def test_value_without_price(self):
        """Test position value when no entry price"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("2.5"),
            side="long"
        )
        assert pos.value is None

    def test_is_empty_true(self):
        """Test is_empty for empty position"""
        pos1 = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("0"),
            side="none"
        )
        pos2 = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("0"),
            side="long"
        )

        assert pos1.is_empty is True
        assert pos2.is_empty is True

    def test_is_empty_false(self):
        """Test is_empty for non-empty position"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("5"),
            side="long"
        )
        assert pos.is_empty is False

    def test_timestamp_auto(self):
        """Test automatic timestamp"""
        pos = Position(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            quantity=Decimal("1"),
            side="long"
        )
        assert isinstance(pos.timestamp, datetime)


class TestFundingRate:
    """Test FundingRate"""

    def test_create(self):
        """Test creating funding rate"""
        ex = ExchangeIdentifier(name="grvt")
        sym = Symbol("BTC", "USDT", "PERP")
        rate = FundingRate(
            exchange=ex,
            symbol=sym,
            rate=Decimal("0.0001"),
            interval_hours=8
        )

        assert rate.exchange == ex
        assert rate.rate == Decimal("0.0001")
        assert rate.interval_hours == 8

    def test_annual_rate_8h(self):
        """Test annual rate calculation for 8-hour interval"""
        rate = FundingRate(
            exchange=ExchangeIdentifier(name="binance"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            rate=Decimal("0.0001"),
            interval_hours=8
        )
        # 0.0001 * (24/8) * 365 = 0.0001 * 3 * 365 = 0.1095
        expected = Decimal("0.0001") * Decimal("3") * Decimal("365")
        assert rate.annual_rate == expected

    def test_annual_rate_1h(self):
        """Test annual rate calculation for 1-hour interval"""
        rate = FundingRate(
            exchange=ExchangeIdentifier(name="lighter"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            rate=Decimal("0.00005"),
            interval_hours=1
        )
        # 0.00005 * 24 * 365 = 0.438
        expected = Decimal("0.00005") * Decimal("24") * Decimal("365")
        assert rate.annual_rate == expected

    def test_daily_rate(self):
        """Test daily rate calculation"""
        rate = FundingRate(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            rate=Decimal("0.0001"),
            interval_hours=8
        )
        # 0.0001 * (24/8) = 0.0003
        expected = Decimal("0.0001") * Decimal("3")
        assert rate.daily_rate == expected


class TestOrder:
    """Test Order"""

    def test_create(self):
        """Test creating order"""
        order = Order(
            exchange=ExchangeIdentifier(name="grvt"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="12345",
            side="buy",
            quantity=Decimal("0.5"),
            price=Decimal("50000"),
            order_type="limit",
            status="open"
        )

        assert order.order_id == "12345"
        assert order.side == "buy"
        assert order.status == "open"

    def test_remaining_quantity(self):
        """Test remaining quantity calculation"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("50000"),
            order_type="limit",
            status="open",
            filled_quantity=Decimal("3")
        )
        assert order.remaining_quantity == Decimal("7")

    def test_is_complete_filled(self):
        """Test is_complete for filled order"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("1"),
            price=None,
            order_type="market",
            status="filled"
        )
        assert order.is_complete is True

    def test_is_complete_cancelled(self):
        """Test is_complete for cancelled order"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="sell",
            quantity=Decimal("1"),
            price=Decimal("50000"),
            order_type="limit",
            status="cancelled"
        )
        assert order.is_complete is True

    def test_is_complete_rejected(self):
        """Test is_complete for rejected order"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("50000"),
            order_type="post_only",
            status="rejected"
        )
        assert order.is_complete is True

    def test_is_complete_open(self):
        """Test is_complete for open order"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("1"),
            price=Decimal("50000"),
            order_type="limit",
            status="open"
        )
        assert order.is_complete is False

    def test_fill_percentage(self):
        """Test fill percentage calculation"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("50000"),
            order_type="limit",
            status="open",
            filled_quantity=Decimal("3")
        )
        assert order.fill_percentage == Decimal("30")

    def test_fill_percentage_zero_quantity(self):
        """Test fill percentage with zero quantity"""
        order = Order(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            order_id="1",
            side="buy",
            quantity=Decimal("0"),
            price=Decimal("50000"),
            order_type="limit",
            status="rejected"
        )
        assert order.fill_percentage == Decimal("0")


class TestMarket:
    """Test Market"""

    def test_create(self):
        """Test creating market data"""
        market = Market(
            exchange=ExchangeIdentifier(name="grvt"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            best_bid=Decimal("49999"),
            best_ask=Decimal("50001"),
            tick_size=Decimal("0.5")
        )

        assert market.best_bid == Decimal("49999")
        assert market.best_ask == Decimal("50001")

    def test_mid_price(self):
        """Test mid price calculation"""
        market = Market(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            best_bid=Decimal("50000"),
            best_ask=Decimal("50002")
        )
        assert market.mid_price == Decimal("50001")

    def test_mid_price_none(self):
        """Test mid price when bid/ask missing"""
        market = Market(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            best_bid=None,
            best_ask=Decimal("50000")
        )
        assert market.mid_price is None

    def test_spread(self):
        """Test spread calculation"""
        market = Market(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            best_bid=Decimal("50000"),
            best_ask=Decimal("50005")
        )
        assert market.spread == Decimal("5")

    def test_spread_bps(self):
        """Test spread in basis points"""
        market = Market(
            exchange=ExchangeIdentifier(name="test"),
            symbol=Symbol("BTC", "USDT", "PERP"),
            best_bid=Decimal("50000"),
            best_ask=Decimal("50005")
        )
        # spread = 5, mid = 50002.5
        # bps = (5 / 50002.5) * 10000 = 0.9999...
        assert abs(market.spread_bps - Decimal("0.9999")) < Decimal("0.01")


class TestTradeLeg:
    """Test TradeLeg"""

    def test_create(self):
        """Test creating trade leg"""
        leg = TradeLeg(
            exchange_id="grvt",
            symbol=Symbol("BTC", "USDT", "PERP"),
            side="buy",
            quantity=Decimal("0.5")
        )

        assert leg.exchange_id == "grvt"
        assert leg.side == "buy"
        assert leg.quantity == Decimal("0.5")

    def test_str(self):
        """Test string representation"""
        leg = TradeLeg(
            exchange_id="lighter",
            symbol=Symbol("ETH", "USD", "PERP"),
            side="sell",
            quantity=Decimal("2.0")
        )
        assert "SELL" in str(leg)
        assert "lighter" in str(leg)


class TestTradingSignal:
    """Test TradingSignal"""

    def test_create(self):
        """Test creating trading signal"""
        legs = [
            TradeLeg("grvt", Symbol("BTC", "USDT", "PERP"), "buy", Decimal("0.5")),
            TradeLeg("lighter", Symbol("BTC", "USDT", "PERP"), "sell", Decimal("0.5"))
        ]

        signal = TradingSignal(
            legs=legs,
            reason="Test signal",
            confidence=Decimal("0.8")
        )

        assert len(signal.legs) == 2
        assert signal.reason == "Test signal"
        assert signal.confidence == Decimal("0.8")

    def test_exchange_count(self):
        """Test counting unique exchanges"""
        legs = [
            TradeLeg("grvt", Symbol("BTC", "USDT", "PERP"), "buy", Decimal("1")),
            TradeLeg("lighter", Symbol("BTC", "USDT", "PERP"), "sell", Decimal("1")),
            TradeLeg("binance", Symbol("BTC", "USDT", "PERP"), "sell", Decimal("1"))
        ]

        signal = TradingSignal(legs=legs, reason="test", confidence=Decimal("1"))
        assert signal.exchange_count == 3

    def test_is_hedge_true(self):
        """Test is_hedge for balanced signal"""
        legs = [
            TradeLeg("grvt", Symbol("BTC", "USDT", "PERP"), "buy", Decimal("1")),
            TradeLeg("lighter", Symbol("BTC", "USDT", "PERP"), "sell", Decimal("1"))
        ]

        signal = TradingSignal(legs=legs, reason="test", confidence=Decimal("1"))
        assert signal.is_hedge is True

    def test_is_hedge_false(self):
        """Test is_hedge for unbalanced signal"""
        legs = [
            TradeLeg("grvt", Symbol("BTC", "USDT", "PERP"), "buy", Decimal("2")),
            TradeLeg("lighter", Symbol("BTC", "USDT", "PERP"), "sell", Decimal("1"))
        ]

        signal = TradingSignal(legs=legs, reason="test", confidence=Decimal("1"))
        assert signal.is_hedge is False

    def test_str(self):
        """Test string representation"""
        legs = [TradeLeg("test", Symbol("BTC", "USDT", "PERP"), "buy", Decimal("1"))]
        signal = TradingSignal(legs=legs, reason="test reason", confidence=Decimal("0.5"))

        s = str(signal)
        assert "test reason" in s


class TestArbitrageConfig:
    """Test ArbitrageConfig"""

    def test_create(self):
        """Test creating config"""
        config = ArbitrageConfig(
            build_threshold=Decimal("0.05"),
            close_threshold=Decimal("0.02"),
            max_position=Decimal("10"),
            trade_size=Decimal("0.1")
        )

        assert config.build_threshold == Decimal("0.05")
        assert config.close_threshold == Decimal("0.02")
        assert config.max_position == Decimal("10")
        assert config.trade_size == Decimal("0.1")

    def test_defaults(self):
        """Test default values"""
        config = ArbitrageConfig(
            build_threshold=Decimal("0.05"),
            close_threshold=Decimal("0.02"),
            max_position=Decimal("10"),
            trade_size=Decimal("0.1")
        )

        assert config.max_position_per_exchange == Decimal("999999")
        assert config.max_total_exposure == Decimal("999999")
        assert config.max_imbalance == Decimal("1")
