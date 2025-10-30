"""
Pushover通知模块 - 发送错误和重要事件通知。

使用Pushover API发送推送通知到手机/桌面。
"""

import os
import httpx
import logging
from typing import Optional
from enum import Enum


class NotificationPriority(Enum):
    """通知优先级"""
    LOW = -1        # 无声音
    NORMAL = 0      # 正常
    HIGH = 1        # 高优先级，绕过静音
    EMERGENCY = 2   # 紧急，需要确认


class PushoverNotifier:
    """Pushover通知器"""

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, user_key: Optional[str] = None, api_token: Optional[str] = None):
        """
        初始化Pushover通知器。

        Args:
            user_key: Pushover用户密钥（可选，从环境变量读取）
            api_token: Pushover应用token（可选，从环境变量读取）
        """
        self.user_key = user_key or os.getenv("PUSHOVER_USER_KEY")
        self.api_token = api_token or os.getenv("PUSHOVER_API_TOKEN")
        self.enabled = bool(self.user_key and self.api_token)
        self.logger = logging.getLogger(__name__)

        if not self.enabled:
            self.logger.warning("Pushover not configured - notifications disabled")

    async def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        url: Optional[str] = None
    ) -> bool:
        """
        发送Pushover通知。

        Args:
            message: 通知消息
            title: 通知标题（可选）
            priority: 优先级
            url: 附加URL（可选）

        Returns:
            bool: 是否发送成功
        """
        if not self.enabled:
            self.logger.debug(f"Pushover disabled, would send: {title or 'Notification'}")
            return False

        try:
            payload = {
                "token": self.api_token,
                "user": self.user_key,
                "message": message,
                "priority": priority.value
            }

            if title:
                payload["title"] = title

            if url:
                payload["url"] = url

            # Emergency priority需要额外参数
            if priority == NotificationPriority.EMERGENCY:
                payload["retry"] = 30  # 每30秒重试
                payload["expire"] = 3600  # 1小时后过期

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.API_URL, data=payload)

                if response.status_code == 200:
                    self.logger.debug(f"Pushover sent: {title or message[:50]}")
                    return True
                else:
                    self.logger.error(f"Pushover failed: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            self.logger.error(f"Error sending Pushover: {e}")
            return False

    async def notify_error(self, error: Exception, context: str = ""):
        """
        发送错误通知（高优先级）。

        Args:
            error: 异常对象
            context: 错误上下文
        """
        message = f"{context}\n\nError: {str(error)}" if context else str(error)
        await self.send(
            message=message,
            title="🚨 Hedge Bot Error",
            priority=NotificationPriority.HIGH
        )

    async def notify_critical(self, message: str, title: str = "🔴 Critical Alert"):
        """
        发送严重错误通知（紧急级别，需要确认）。

        Args:
            message: 通知消息
            title: 通知标题
        """
        await self.send(
            message=message,
            title=title,
            priority=NotificationPriority.EMERGENCY
        )

    async def notify_warning(self, message: str, title: str = "⚠️ Warning"):
        """
        发送警告通知（正常优先级）。

        Args:
            message: 通知消息
            title: 通知标题
        """
        await self.send(
            message=message,
            title=title,
            priority=NotificationPriority.NORMAL
        )

    async def notify_info(self, message: str, title: str = "ℹ️ Info"):
        """
        发送信息通知（低优先级）。

        Args:
            message: 通知消息
            title: 通知标题
        """
        await self.send(
            message=message,
            title=title,
            priority=NotificationPriority.LOW
        )
