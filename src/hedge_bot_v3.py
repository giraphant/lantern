"""
对冲机器人V3 - 清晰解耦的架构。

架构：
├── SafetyChecker (纯函数 - 安全检查)
├── Rebalancer (纯函数 - 计算操作)
├── TradingExecutor (执行层 - 调用exchange)
└── HedgeBot (协调器 - 主循环)
"""

import asyncio
import logging
import os
import sys
from decimal import Decimal
from enum import Enum
from pathlib import Path
import dotenv

# 抑制冗余日志
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('pysdk').setLevel(logging.ERROR)

from exchanges.factory import ExchangeFactory
from hedge.safety_checker import SafetyChecker, PositionState, SafetyAction
from hedge.rebalancer import Rebalancer, TradeAction
from hedge.trading_executor import TradingExecutor
from hedge.phase_detector import PhaseDetector, TradingPhase
from helpers.pushover_notifier import PushoverNotifier


class Config:
    """配置类"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class HedgeBotV3:
    """对冲机器人V3 - 清晰解耦的架构"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.load_config()

        # 初始化交易所客户端 (使用工厂模式)
        self.exchange_a = self._init_exchange_client(
            self.exchange_a_name,
            self.exchange_a_config
        )
        self.exchange_b = self._init_exchange_client(
            self.exchange_b_name,
            self.exchange_b_config
        )

        # 初始化模块
        self.executor = TradingExecutor(self.exchange_a, self.exchange_b, self.logger)
        self.notifier = PushoverNotifier()

    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('HedgeBotV3')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
        logger.addHandler(handler)
        return logger

    def load_config(self):
        """加载配置"""
        # 加载.env
        env_paths = [Path(".env"), Path("../.env"), Path("/app/.env")]
        for env_path in env_paths:
            if env_path.exists():
                dotenv.load_dotenv(env_path, override=True)
                break

        # 交易所配置
        self.exchange_a_name = os.getenv("EXCHANGE_A", "GRVT").upper()
        self.exchange_b_name = os.getenv("EXCHANGE_B", "LIGHTER").upper()

        # 交易参数
        self.symbol = os.getenv("TRADING_SYMBOL", "BNB")
        self.order_quantity = Decimal(os.getenv("TRADING_SIZE", "0.1"))
        self.target_cycles = int(os.getenv("CYCLE_TARGET", "5"))
        self.hold_time = int(os.getenv("CYCLE_HOLD_TIME", "180"))

        # 交易方向：long=多头策略, short=空头策略
        self.direction = os.getenv("TRADING_DIRECTION", "long").lower()
        if self.direction not in ["long", "short"]:
            raise ValueError(f"Invalid TRADING_DIRECTION: {self.direction}. Must be 'long' or 'short'")

        # 安全参数
        self.max_position_per_side = self.order_quantity * self.target_cycles * Decimal("1.5")
        self.max_total_position = self.order_quantity * self.target_cycles * Decimal("1.5")
        self.max_imbalance = self.order_quantity * Decimal("3")

        # 为每个交易所准备配置
        self.exchange_a_config = self._prepare_exchange_config(self.exchange_a_name)
        self.exchange_b_config = self._prepare_exchange_config(self.exchange_b_name)

    def _prepare_exchange_config(self, exchange_name: str) -> Config:
        """为指定交易所准备配置"""
        exchange_name = exchange_name.upper()

        # 基础配置
        base_config = {
            "ticker": self.symbol,
            "quantity": self.order_quantity,
        }

        # 根据交易所转换symbol格式和设置contract_id
        if exchange_name == "LIGHTER":
            # Lighter会自动解析ticker到contract_id,不需要预设
            # ticker保持原样(如'BTC')
            pass
        elif exchange_name == "BACKPACK":
            # Backpack需要完整的交易对格式,如'BTC_USDC'
            # 如果symbol不包含分隔符,自动添加_USDC
            if '_' not in self.symbol and '-' not in self.symbol:
                base_config["contract_id"] = f"{self.symbol}_USDC"
            else:
                # 将-替换为_
                base_config["contract_id"] = self.symbol.replace('-', '_')
            # 设置默认tick_size,会在connect时被市场数据覆盖
            base_config["tick_size"] = Decimal("0.01")
        else:
            # 其他交易所默认使用symbol作为contract_id
            base_config["contract_id"] = self.symbol

        # 根据交易所类型添加特定配置
        if exchange_name == "GRVT":
            base_config.update({
                "api_key": os.getenv("GRVT_API_KEY"),
                "priv_key_file": os.getenv("GRVT_PRIVATE_KEY"),
                "block_order_recreation": False,
                "block_orders": False
            })
            if not all([base_config["api_key"], base_config["priv_key_file"]]):
                raise ValueError("Missing GRVT API keys (GRVT_API_KEY, GRVT_PRIVATE_KEY)")

        elif exchange_name == "LIGHTER":
            lighter_key = os.getenv("LIGHTER_PRIVATE_KEY") or os.getenv("LIGHTER_API_PRIVATE_KEY")
            base_config.update({
                "direction": "long",
                "close_order_side": "sell"
            })
            if not lighter_key:
                raise ValueError("Missing LIGHTER_PRIVATE_KEY")
            # 确保环境变量可用
            if not os.getenv("LIGHTER_PRIVATE_KEY"):
                os.environ["LIGHTER_PRIVATE_KEY"] = lighter_key

        elif exchange_name == "BINANCE":
            base_config.update({
                "api_key": os.getenv("BINANCE_API_KEY"),
                "api_secret": os.getenv("BINANCE_API_SECRET"),
            })
            if not all([base_config.get("api_key"), base_config.get("api_secret")]):
                raise ValueError("Missing BINANCE API keys (BINANCE_API_KEY, BINANCE_API_SECRET)")

        elif exchange_name == "BACKPACK":
            # Backpack使用环境变量直接初始化,不需要在config中传递
            # 只需要确保环境变量存在
            if not all([os.getenv("BACKPACK_PUBLIC_KEY"), os.getenv("BACKPACK_SECRET_KEY")]):
                raise ValueError("Missing BACKPACK API keys (BACKPACK_PUBLIC_KEY, BACKPACK_SECRET_KEY)")

        else:
            # 其他交易所的通用配置
            self.logger.warning(f"Using generic config for {exchange_name}, may need customization")

        return Config(**base_config)

    def _init_exchange_client(self, exchange_name: str, config: Config):
        """使用工厂模式初始化交易所客户端"""
        try:
            client = ExchangeFactory.create_exchange(exchange_name.lower(), config)
            self.logger.info(f"✓ Initialized {exchange_name} exchange client")
            return client
        except Exception as e:
            self.logger.error(f"Failed to initialize {exchange_name}: {e}")
            raise

    async def connect(self):
        """连接交易所"""
        self.logger.info(f"Connecting to exchanges ({self.exchange_a_name} & {self.exchange_b_name})...")
        await self.exchange_a.connect()
        self.logger.info(f"✓ {self.exchange_a_name} connected")

        await self.exchange_b.connect()
        self.logger.info(f"✓ {self.exchange_b_name} connected")

    async def run(self):
        """主循环"""
        try:
            await self.connect()

            # 检查初始仓位
            position = await self.executor.get_positions()
            self.logger.info(f"Initial position: {self.exchange_a_name}={position.exchange_a_position}, {self.exchange_b_name}={position.exchange_b_position}")

            # 主循环 - 完全无状态，每次都从交易所获取真实状态
            while True:
                # ========== 步骤1: 获取真实状态 ==========
                position = await self.executor.get_positions()
                pending_orders = await self.executor.get_pending_orders()

                # ========== 步骤2: 安全检查 ==========
                safety_result = SafetyChecker.check_all(
                    position,
                    self.max_position_per_side,
                    self.max_total_position,
                    self.max_imbalance,
                    pending_orders=pending_orders,
                    max_pending_per_side=1
                )

                # 根据安全检查结果执行对应操作（纯编排）
                if safety_result.action == SafetyAction.CANCEL_ALL_ORDERS:
                    self.logger.warning(f"⚠️  {safety_result.reason}")
                    self.logger.warning("   Cancelling all orders...")
                    await self.executor.cancel_all_orders()
                    await asyncio.sleep(2)
                    continue

                elif safety_result.action == SafetyAction.PAUSE:
                    self.logger.error(f"❌ {safety_result.reason}")
                    self.logger.error(f"   Position: {position}")
                    self.logger.error("   Pausing for 60 seconds...")
                    # 发送安全警告通知
                    await self.notifier.notify_warning(
                        message=f"{safety_result.reason}\n\nPosition:\n{self.exchange_a_name}: {position.exchange_a_position}\n{self.exchange_b_name}: {position.exchange_b_position}\nTotal: {position.total_position}\n\nBot paused for 60s",
                        title="⚠️ Safety Limit Triggered"
                    )
                    await asyncio.sleep(60)
                    continue

                # ========== 步骤3: 检查是否需要打平不平衡 ==========
                # 改为超过order_size才触发打平（因为GRVT可能有挂单未成交）
                rebalance_threshold = self.order_quantity

                if position.imbalance > rebalance_threshold:
                    # 需要打平，目标 = 0（让两边完全对冲）
                    # 通过调整Lighter仓位来实现（市价单立即成交）
                    target_position = Decimal(0)

                    rebalance_instruction = Rebalancer.calculate_rebalance(
                        current_position=position,
                        target_total_position=target_position,
                        order_size=self.order_quantity,
                        tolerance=rebalance_threshold
                    )

                    if rebalance_instruction.action != TradeAction.HOLD:
                        self.logger.warning(f"⚖️  REBALANCING: Imbalance={position.imbalance}")
                        self.logger.warning(f"   {rebalance_instruction.reason}")

                        result = await self.executor.execute_trade(
                            rebalance_instruction.action,
                            rebalance_instruction.quantity,
                            wait_for_fill=False,  # Lighter市价单不需要等待
                            fill_timeout=30
                        )

                        if not result.success:
                            self.logger.error(f"   Rebalance failed: {result.error}")

                        await asyncio.sleep(2)
                        continue  # 打平后重新开始，跳过阶段判断和正常交易

                # ========== 步骤4: 阶段判断 ==========
                # 根据策略方向确定BUILD阶段的交易方向
                build_side = "buy" if self.direction == "long" else "sell"

                # 尝试获取最后成交订单(如果交易所支持)
                last_order_side = None
                last_order_time = None
                if hasattr(self.exchange_a, 'get_last_filled_order'):
                    try:
                        last_order = await self.exchange_a.get_last_filled_order(
                            contract_id=self.exchange_a.config.contract_id,
                            build_side=build_side
                        )
                        if last_order:
                            last_order_side, last_order_time = last_order
                    except Exception as e:
                        self.logger.debug(f"Failed to get last filled order: {e}")
                        # 继续执行,不影响主流程

                phase_info = PhaseDetector.detect_phase(
                    position=position,
                    target_cycles=self.target_cycles,
                    order_size=self.order_quantity,
                    hold_time=self.hold_time,
                    last_order_side=last_order_side,
                    last_order_time=last_order_time
                )

                self.logger.info(f"📍 Phase: {phase_info.phase.value} | Last order: {last_order_side} | {phase_info.reason}")

                # ========== 步骤5: 根据阶段执行对应操作 ==========
                if phase_info.phase == TradingPhase.BUILDING:
                    await self._handle_building_phase(position)

                elif phase_info.phase == TradingPhase.HOLDING:
                    # 持仓等待中，不执行交易
                    if phase_info.time_remaining:
                        self.logger.info(f"⏳ HOLDING: {phase_info.time_remaining}s remaining")
                    await asyncio.sleep(min(10, phase_info.time_remaining or 10))

                elif phase_info.phase == TradingPhase.WINDING_DOWN:
                    await self._handle_winddown_phase(position)

                # 短暂休息
                await asyncio.sleep(2)

        except KeyboardInterrupt:
            self.logger.info("\nShutting down...")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            # 发送错误通知
            await self.notifier.notify_critical(
                message=f"Bot crashed with error:\n{str(e)}\n\nBot has stopped running!",
                title="🔴 Hedge Bot Crashed"
            )
        finally:
            await self.cleanup()

    async def _handle_building_phase(self, position: PositionState):
        """处理建仓阶段 - 执行固定的对冲交易"""
        if self.direction == "long":
            # 多头策略：Exchange A buy + Exchange B sell
            self.logger.info(f"📈 BUILDING (LONG): {self.exchange_a_name} buy + {self.exchange_b_name} sell {self.order_quantity}")
            action = TradeAction.BUILD_LONG
        else:
            # 空头策略：Exchange A sell + Exchange B buy
            self.logger.info(f"📈 BUILDING (SHORT): {self.exchange_a_name} sell + {self.exchange_b_name} buy {self.order_quantity}")
            action = TradeAction.CLOSE_LONG

        result = await self.executor.execute_trade(
            action=action,
            quantity=self.order_quantity,
            wait_for_fill=True,
            fill_timeout=30
        )

        if not result.success:
            self.logger.warning(f"   Trade failed: {result.error}, retrying in 5s...")
            await asyncio.sleep(5)

    async def _handle_winddown_phase(self, position: PositionState):
        """处理平仓阶段 - 执行固定的对冲交易"""
        if self.direction == "long":
            # 多头策略：Exchange A sell + Exchange B buy
            self.logger.info(f"📉 WINDING DOWN (LONG): {self.exchange_a_name} sell + {self.exchange_b_name} buy {self.order_quantity}")
            action = TradeAction.CLOSE_LONG
        else:
            # 空头策略：Exchange A buy + Exchange B sell
            self.logger.info(f"📉 WINDING DOWN (SHORT): {self.exchange_a_name} buy + {self.exchange_b_name} sell {self.order_quantity}")
            action = TradeAction.BUILD_LONG

        result = await self.executor.execute_trade(
            action=action,
            quantity=self.order_quantity,
            wait_for_fill=True,
            fill_timeout=30
        )

        if not result.success:
            self.logger.warning(f"   Trade failed: {result.error}, retrying in 5s...")
            await asyncio.sleep(5)

    async def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("Cleaning up...")
            await self.exchange_a.disconnect()
            await self.exchange_b.disconnect()
        except:
            pass


async def main():
    bot = HedgeBotV3()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
