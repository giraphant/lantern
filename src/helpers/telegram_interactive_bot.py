"""
Interactive Telegram Bot for Funding Rate Arbitrage Bot
支持命令交互和实时状态查询
"""

import asyncio
import logging
from decimal import Decimal
from typing import Optional, Callable
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode


class TelegramInteractiveBot:
    """Interactive Telegram Bot with command handlers"""

    def __init__(self, token: str, chat_id: str):
        """
        Initialize Telegram Bot.

        Args:
            token: Bot token from @BotFather
            chat_id: Your Telegram chat ID
        """
        self.token = token
        self.chat_id = chat_id
        self.logger = logging.getLogger('TelegramBot')

        # 状态回调函数（由主bot设置）
        self.get_status_callback: Optional[Callable] = None
        self.get_positions_callback: Optional[Callable] = None
        self.get_profit_callback: Optional[Callable] = None

        self.app: Optional[Application] = None
        self._running = False

    def set_callbacks(
        self,
        get_status: Callable,
        get_positions: Callable,
        get_profit: Callable
    ):
        """设置回调函数，用于获取bot状态"""
        self.get_status_callback = get_status
        self.get_positions_callback = get_positions
        self.get_profit_callback = get_profit

    async def start(self):
        """启动Telegram Bot"""
        if self._running:
            return

        try:
            self.app = Application.builder().token(self.token).build()

            # 注册命令处理器
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CommandHandler("help", self.cmd_help))
            self.app.add_handler(CommandHandler("status", self.cmd_status))
            self.app.add_handler(CommandHandler("positions", self.cmd_positions))
            self.app.add_handler(CommandHandler("profit", self.cmd_profit))

            # 设置命令菜单
            await self.app.bot.set_my_commands([
                BotCommand("start", "开始使用"),
                BotCommand("help", "帮助信息"),
                BotCommand("status", "查看当前状态"),
                BotCommand("positions", "查看仓位详情"),
                BotCommand("profit", "查看收益统计"),
            ])

            # 启动bot（非阻塞）
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            self._running = True
            self.logger.info("✅ Telegram Bot started")

            # 发送启动消息
            await self.send_message("🤖 *Funding Rate Arbitrage Bot Started*\n\n使用 /help 查看可用命令")

        except Exception as e:
            self.logger.error(f"Failed to start Telegram Bot: {e}")
            raise

    async def stop(self):
        """停止Telegram Bot"""
        if self.app and self._running:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self._running = False
            self.logger.info("Telegram Bot stopped")

    async def send_message(self, text: str, parse_mode: str = ParseMode.MARKDOWN):
        """
        发送消息到指定chat.

        Args:
            text: 消息内容
            parse_mode: 解析模式（MARKDOWN或HTML）
        """
        if not self.app:
            return

        try:
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")

    # ========== 命令处理器 ==========

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        welcome_text = """
🤖 *欢迎使用 Funding Rate Arbitrage Bot*

这个机器人监控 GRVT 和 Lighter 之间的资金费率差异，自动执行套利交易。

*可用命令：*
/status - 查看当前状态
/positions - 查看仓位详情
/profit - 查看收益统计
/help - 显示帮助信息

📊 Bot 会在执行交易时自动通知您。
"""
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_text = """
📚 *帮助信息*

*命令列表：*
/status - 当前费率、仓位和操作
/positions - 详细仓位信息（包含不平衡度）
/profit - 今日和累计收益估算

*策略说明：*
• 当费率差 ≥ 建仓阈值时，开始建仓
• 当费率差 < 平仓阈值时，开始平仓
• 仓位达到上限时停止建仓

*通知：*
Bot 会在以下情况自动通知：
• 开始建仓（BUILD）
• 开始平仓（WINDDOWN）
• 触发安全限制
• 发生错误

💡 如有问题请查看日志或联系管理员
"""
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        if not self.get_status_callback:
            await update.message.reply_text("❌ 状态回调未设置")
            return

        try:
            status = await self.get_status_callback()
            await update.message.reply_text(status, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ 获取状态失败: {e}")

    async def cmd_positions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /positions 命令"""
        if not self.get_positions_callback:
            await update.message.reply_text("❌ 仓位回调未设置")
            return

        try:
            positions = await self.get_positions_callback()
            await update.message.reply_text(positions, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ 获取仓位失败: {e}")

    async def cmd_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /profit 命令"""
        if not self.get_profit_callback:
            await update.message.reply_text("❌ 收益回调未设置")
            return

        try:
            profit = await self.get_profit_callback()
            await update.message.reply_text(profit, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ 获取收益失败: {e}")

    # ========== 通知方法 ==========

    async def notify_build(self, symbol: str, side: str, quantity: Decimal, spread_apr: Decimal):
        """通知开始建仓"""
        text = f"""
📈 *BUILD {side.upper()} Position*

Symbol: `{symbol}`
Quantity: `{quantity}`
Spread: `{spread_apr*100:.2f}% APR`

Strategy: {self._get_strategy_text(side, spread_apr)}
"""
        await self.send_message(text)

    async def notify_winddown(self, symbol: str, side: str, quantity: Decimal, spread_apr: Decimal):
        """通知开始平仓"""
        text = f"""
📉 *WINDDOWN {side.upper()} Position*

Symbol: `{symbol}`
Quantity: `{quantity}`
Spread: `{spread_apr*100:.2f}% APR`

Reason: Spread below threshold or position limit reached
"""
        await self.send_message(text)

    async def notify_safety_warning(self, reason: str, position_info: str):
        """通知安全警告"""
        text = f"""
⚠️ *Safety Warning*

{reason}

Position Info:
```
{position_info}
```

Bot action: Paused for 60 seconds
"""
        await self.send_message(text)

    async def notify_error(self, error_message: str):
        """通知错误"""
        text = f"""
❌ *Error Occurred*

{error_message}

Please check logs for details.
"""
        await self.send_message(text)

    def _get_strategy_text(self, side: str, spread_apr: Decimal) -> str:
        """获取策略说明文本"""
        if side == "long":
            return "LONG GRVT + SHORT Lighter (GRVT费率低)"
        else:
            return "SHORT GRVT + LONG Lighter (GRVT费率高)"
