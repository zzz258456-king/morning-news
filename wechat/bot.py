"""
微信机器人 — 统一高层接口

整合 auth + sender + receiver，提供完整功能：
    - 扫码登录
    - 消息接收（长轮询获取 context_token）
    - 消息发送（利用缓存的 context_token）
    - 系统通知推送
"""
import logging
from pathlib import Path
from typing import Optional

from wechat.auth import WeChatAuth
from wechat.sender import WeChatSender, TokenCache
from wechat.receiver import WeChatReceiver, MessageHandler, WeChatMessage

logger = logging.getLogger(__name__)


class WeChatBot:
    """
    微信机器人统一接口

    用法：
        bot = WeChatBot()

        # 1. 登录
        bot.login()

        # 2. 先收消息（获取 context_token）
        bot.poll_once()

        # 3. 再发消息
        bot.send_text("你好！", "user_id@im.wechat")
    """

    def __init__(self, cred_file: Optional[Path] = None):
        self.auth = WeChatAuth(cred_file=cred_file)
        self.sender: Optional[WeChatSender] = None
        self.receiver: Optional[WeChatReceiver] = None
        self.token_cache = TokenCache()

    # -------- 登录 --------

    @property
    def is_logged_in(self) -> bool:
        return self.auth.credentials is not None and bool(self.auth.credentials.token)

    def login(self, interactive: bool = True) -> bool:
        """
        登录微信

        Args:
            interactive: True 则未登录时交互式扫码

        Returns:
            True 表示登录成功
        """
        if self.auth.check_login():
            self._init_components()
            logger.info("微信已登录（账号ID: %s）", self.auth.credentials.accountId)
            return True

        if interactive:
            logger.info("微信未登录，启动扫码登录...")
            creds = self.auth.login_interactive()
            if creds:
                self._init_components()
                logger.info("微信登录成功")
                return True
            logger.error("微信登录失败")
            return False

        logger.warning("微信未登录")
        return False

    def logout(self):
        """清除所有登录和缓存信息"""
        self.auth.credentials = None
        self.sender = None
        self.receiver = None
        self.token_cache.clear()
        if self.auth.cred_file.exists():
            self.auth.cred_file.unlink()
        logger.info("已清除微信登录信息和缓存")

    def _init_components(self):
        """初始化 sender 和 receiver（共享同一个 TokenCache 实例）"""
        if self.auth.credentials:
            if not self.sender:
                self.sender = WeChatSender(self.auth, token_cache=self.token_cache)
            if not self.receiver:
                self.receiver = WeChatReceiver(self.auth, token_cache=self.token_cache)

    # -------- 发送消息 --------

    def send_text(self, content: str, to_user_id: Optional[str] = None) -> bool:
        """发送文本消息"""
        self._init_components()
        if not self.sender:
            logger.error("发送失败：微信未初始化")
            return False
        return self.sender.send_text(content, to_user_id)

    def send_report(self, title: str, body: str, to_user_id: Optional[str] = None) -> bool:
        """发送格式化报告"""
        self._init_components()
        if not self.sender:
            logger.error("发送失败：微信未初始化")
            return False
        return self.sender.send_report(title, body, to_user_id)

    def send_notification(self, title: str, body: str = "",
                          msg_type: str = "info",
                          to_user_id: Optional[str] = None) -> bool:
        """
        发送通知消息

        Args:
            title: 标题
            body: 正文
            msg_type: info / warning / error / success
            to_user_id: 目标用户
        """
        emoji_map = {
            "info": "ℹ️", "warning": "⚠️",
            "error": "❌", "success": "✅",
        }
        emoji = emoji_map.get(msg_type, "📢")
        content = f"{emoji} {title}"
        if body:
            content += f"\n\n{body}"
        return self.send_text(content, to_user_id)

    # -------- 接收消息 --------

    def add_handler(self, handler: MessageHandler):
        """添加消息处理回调"""
        self._init_components()
        if self.receiver:
            self.receiver.add_handler(handler)

    def poll_once(self) -> int:
        """
        单次轮询消息（获取 context_token 的关键步骤）

        必须先收到一条消息才能获取 context_token，
        然后才能主动发送消息。
        """
        self._init_components()
        if not self.receiver:
            return 0
        return self.receiver.poll_once()

    def start_polling(self):
        """持续长轮询（阻塞）"""
        self._init_components()
        if self.receiver:
            self.receiver.start_polling()

    def stop_polling(self):
        """停止轮询"""
        if self.receiver:
            self.receiver.stop()

    @property
    def has_context_token(self) -> bool:
        """检查是否有可用的 context_token"""
        return self.token_cache.get() is not None
