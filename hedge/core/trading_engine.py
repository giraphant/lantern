"""
简化的交易引擎。

只关注业务逻辑，不关心具体交易所实现。
"""

import asyncio
import logging
from decimal import Decimal
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta

from hedge.services.hedge_service import HedgeService, HedgePosition
from hedge.managers.safety_manager import SafetyManager, SafetyLevel


class TradingState(Enum):
    """交易状态"""
    IDLE = "IDLE"                # 空闲
    BUILDING = "BUILDING"         # 建仓中
    HOLDING = "HOLDING"          # 持仓中
    WINDING_DOWN = "WINDING_DOWN"  # 平仓中
    ERROR = "ERROR"              # 错误状态
    STOPPED = "STOPPED"          # 已停止


class TradingEngine:
    """
    简化的交易引擎。

    职责：
    1. 管理交易状态
    2. 执行对冲策略
    3. 协调安全检查
    """

    def __init__(
        self,
        hedge_service: HedgeService,
        safety_manager: SafetyManager,
        config,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化交易引擎。

        Args:
            hedge_service: 对冲服务（抽象接口）
            safety_manager: 安全管理器
            config: 配置对象
            logger: 日志记录器
        """
        self.hedge = hedge_service
        self.safety = safety_manager
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # 状态管理
        self.state = TradingState.IDLE
        self.running = False
        self.last_error = None

        # 交易参数
        self.target_cycles = config.target_cycles
        self.order_quantity = Decimal(str(config.order_quantity))
        self.rebalance_tolerance = Decimal(str(config.rebalance_tolerance))
        self.order_timeout = config.order_timeout

        # 统计信息
        self.completed_cycles = 0
        self.start_time = None
        self.last_cycle_time = None

    async def start(self) -> None:
        """启动交易引擎"""
        try:
            self.logger.info("Starting trading engine...")

            # 初始化服务
            await self.hedge.initialize()

            # 检查初始仓位
            positions = await self.hedge.get_positions()
            self.logger.info(f"Initial positions: {positions}")

            # 根据初始仓位决定状态
            if abs(positions.total_position) > self.order_quantity / 2:
                self.logger.warning(f"Non-zero initial position: {positions.total_position}")
                self.state = TradingState.WINDING_DOWN
            else:
                self.state = TradingState.IDLE

            self.running = True
            self.start_time = datetime.now()

            # 启动主循环
            await self._run_main_loop()

        except Exception as e:
            self.logger.error(f"Failed to start engine: {e}")
            self.state = TradingState.ERROR
            self.last_error = str(e)
            raise

    async def stop(self) -> None:
        """停止交易引擎"""
        self.logger.info("Stopping trading engine...")
        self.running = False
        self.state = TradingState.STOPPED

        try:
            # 取消所有订单
            await self.hedge.cancel_all_orders()

            # 清理资源
            await self.hedge.cleanup()

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    async def _run_main_loop(self) -> None:
        """主交易循环"""
        while self.running:
            try:
                # 获取当前仓位
                positions = await self.hedge.get_positions()

                # 安全检查
                safety_level = self.safety.check_positions(
                    grvt_position=float(positions.maker_position),
                    lighter_position=float(positions.taker_position)
                )

                # 处理紧急情况
                if safety_level == SafetyLevel.EMERGENCY:
                    await self._handle_emergency(positions)
                    continue

                # 根据状态执行操作
                if self.state == TradingState.IDLE:
                    await self._handle_idle_state(positions, safety_level)

                elif self.state == TradingState.BUILDING:
                    await self._handle_building_state(positions, safety_level)

                elif self.state == TradingState.HOLDING:
                    await self._handle_holding_state(positions, safety_level)

                elif self.state == TradingState.WINDING_DOWN:
                    await self._handle_winding_down_state(positions, safety_level)

                elif self.state == TradingState.ERROR:
                    await self._handle_error_state(positions, safety_level)

                # 短暂休息
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.state = TradingState.ERROR
                self.last_error = str(e)
                await asyncio.sleep(5)  # 错误后等待更长时间

    async def _handle_idle_state(self, positions: HedgePosition, safety_level: SafetyLevel) -> None:
        """处理空闲状态"""
        # 检查是否需要开始建仓
        if self.completed_cycles < self.target_cycles:
            if safety_level == SafetyLevel.NORMAL:
                self.logger.info(f"Starting build cycle {self.completed_cycles + 1}/{self.target_cycles}")
                self.state = TradingState.BUILDING
                self.last_cycle_time = datetime.now()
            else:
                self.logger.warning(f"Waiting for safe conditions to start building (safety={safety_level})")
        else:
            self.logger.info("All target cycles completed, remaining idle")

    async def _handle_building_state(self, positions: HedgePosition, safety_level: SafetyLevel) -> None:
        """处理建仓状态"""
        try:
            # 安全检查
            if safety_level >= SafetyLevel.PAUSE:
                self.logger.warning(f"Pausing build due to safety level: {safety_level}")
                self.state = TradingState.HOLDING
                return

            # 计算当前进度（基于仓位）
            current_position_abs = abs(positions.taker_position)  # 使用Lighter仓位作为进度指标
            expected_position = self.order_quantity * (self.completed_cycles + 1)

            # 检查是否已完成当前周期
            if current_position_abs >= expected_position - self.order_quantity * Decimal("0.1"):  # 10%容差
                self.completed_cycles += 1
                self.logger.info(f"Completed cycle {self.completed_cycles}/{self.target_cycles}")

                if self.completed_cycles >= self.target_cycles:
                    self.logger.info("All cycles completed, entering HOLDING state")
                    self.state = TradingState.HOLDING
                else:
                    # 继续下一个周期
                    await asyncio.sleep(self.config.cycle_interval)
            else:
                # 执行对冲
                direction = "long"  # 可以根据策略调整
                self.logger.info(f"Executing hedge cycle: direction={direction}, size={self.order_quantity}")

                result = await self.hedge.execute_hedge_cycle(direction, self.order_quantity)

                if result.success:
                    self.logger.info(f"Hedge cycle successful: {result}")
                else:
                    self.logger.error(f"Hedge cycle failed: {result}")
                    # 根据失败原因决定是否继续
                    if "timeout" in str(result.error).lower():
                        self.logger.warning("Order timeout, retrying...")
                    else:
                        self.state = TradingState.ERROR
                        self.last_error = result.error

            # 检查是否需要重平衡
            if abs(positions.imbalance) > self.rebalance_tolerance:
                await self._perform_rebalance(positions)

        except Exception as e:
            self.logger.error(f"Error in building state: {e}")
            self.state = TradingState.ERROR
            self.last_error = str(e)

    async def _handle_holding_state(self, positions: HedgePosition, safety_level: SafetyLevel) -> None:
        """处理持仓状态"""
        # 定期检查仓位平衡
        if abs(positions.imbalance) > self.rebalance_tolerance:
            if safety_level <= SafetyLevel.AUTO_REBALANCE:
                self.logger.info(f"Position imbalance detected: {positions.imbalance:.4f}")
                await self._perform_rebalance(positions)
            else:
                self.logger.warning(f"Imbalance {positions.imbalance:.4f} but safety={safety_level}, not rebalancing")

        # 检查是否应该开始平仓
        # （可以根据时间、市场条件等决定）
        if self._should_wind_down():
            self.logger.info("Starting wind down process")
            self.state = TradingState.WINDING_DOWN

    async def _handle_winding_down_state(self, positions: HedgePosition, safety_level: SafetyLevel) -> None:
        """处理平仓状态"""
        try:
            total_position = abs(positions.total_position)

            if total_position < Decimal("0.01"):  # 基本清零
                self.logger.info("Positions closed successfully")
                self.state = TradingState.IDLE
                self.completed_cycles = 0  # 重置计数
                return

            # 智能平仓策略
            if abs(positions.maker_position) > abs(positions.taker_position):
                # GRVT仓位较大，优先平GRVT
                self.logger.info(f"Closing GRVT position: {positions.maker_position}")
                side = "short" if positions.maker_position > 0 else "long"
                qty = min(abs(positions.maker_position), self.order_quantity)
            else:
                # Lighter仓位较大，优先平Lighter
                self.logger.info(f"Closing Lighter position: {positions.taker_position}")
                side = "short" if positions.taker_position > 0 else "long"
                qty = min(abs(positions.taker_position), self.order_quantity)

            # 执行平仓
            result = await self.hedge.execute_hedge_cycle(side, qty)

            if not result.success:
                self.logger.error(f"Failed to close position: {result.error}")
                # 尝试直接平仓
                if safety_level >= SafetyLevel.EMERGENCY:
                    await self.hedge.close_all_positions()

        except Exception as e:
            self.logger.error(f"Error in winding down: {e}")
            self.state = TradingState.ERROR
            self.last_error = str(e)

    async def _handle_error_state(self, positions: HedgePosition, safety_level: SafetyLevel) -> None:
        """处理错误状态"""
        self.logger.error(f"In ERROR state: {self.last_error}")

        # 尝试恢复
        if safety_level == SafetyLevel.NORMAL:
            self.logger.info("Attempting to recover from error state")
            self.state = TradingState.IDLE
            self.last_error = None
        elif safety_level >= SafetyLevel.EMERGENCY:
            # 紧急停止
            await self._handle_emergency(positions)

    async def _handle_emergency(self, positions: HedgePosition) -> None:
        """处理紧急情况"""
        self.logger.critical("EMERGENCY: Executing emergency stop")

        try:
            # 关闭所有仓位
            result = await self.hedge.close_all_positions()

            if result.success:
                self.logger.info("Emergency stop completed")
            else:
                self.logger.error(f"Emergency stop failed: {result.error}")

            # 停止引擎
            self.running = False
            self.state = TradingState.STOPPED

        except Exception as e:
            self.logger.critical(f"Critical error during emergency stop: {e}")
            # 最后的尝试
            await self.hedge.cancel_all_orders()
            self.running = False

    async def _perform_rebalance(self, positions: HedgePosition) -> None:
        """执行重平衡"""
        try:
            self.logger.info(f"Performing rebalance, imbalance={positions.imbalance:.4f}")

            result = await self.hedge.rebalance_positions(
                max_rebalance_size=self.order_quantity
            )

            if result.success:
                self.logger.info(f"Rebalance successful: {result.position_after}")
            else:
                self.logger.error(f"Rebalance failed: {result.error}")

        except Exception as e:
            self.logger.error(f"Error during rebalance: {e}")

    def _should_wind_down(self) -> bool:
        """判断是否应该开始平仓"""
        # 可以根据多种条件判断
        # 例如：运行时间、市场条件、用户信号等

        if not self.start_time:
            return False

        # 示例：运行超过指定时间后平仓
        max_runtime = getattr(self.config, 'max_runtime_hours', 24)
        runtime = datetime.now() - self.start_time

        if runtime > timedelta(hours=max_runtime):
            self.logger.info(f"Max runtime reached ({max_runtime} hours)")
            return True

        return False

    def get_status(self) -> dict:
        """获取引擎状态"""
        return {
            "state": self.state.value,
            "running": self.running,
            "completed_cycles": self.completed_cycles,
            "target_cycles": self.target_cycles,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "last_error": self.last_error
        }