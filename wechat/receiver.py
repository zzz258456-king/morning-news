"""
微信消息接收器 — 基于 iLink ClawBot getUpdates API

通过长轮询获取微信消息，缓存 context_token 用于后续主动发送。
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from wechat.auth import WeChatAuth, BASE_URL
from wechat.sender import TokenCache

logger = logging.getLogger(__name__)


@dataclass
class WeChatMessage:
    """微信接收到的消息"""
    msg_id: str = ""
    from_user_id: str = ""
    from_name: str = ""
    content: str = ""
    msg_type: int = 1
    create_time: str = ""
    context_token: str = ""   # 用于回复的上下文 token

    @classmethod
    def from_raw(cls, raw: dict) -> "WeChatMessage":
        """从 API 原始响应解析消息（兼容 GET/POST 两种格式）"""
        msg = raw.get("msg", raw)
        # POST 格式用 message_id，GET 格式用 msg_id
        raw_id = msg.get("msg_id") or msg.get("message_id") or ""
        return cls(
            msg_id=str(raw_id),
            from_user_id=msg.get("from_user_id", ""),
            from_name=msg.get("from_name", "") or msg.get("nick_name", ""),
            content=_extract_text(msg.get("item_list", [])),
            msg_type=msg.get("message_type", 1),
            create_time=str(msg.get("create_time", "") or msg.get("create_time_ms", "")),
            context_token=msg.get("context_token", "") or raw.get("context_token", ""),
        )


def _extract_text(item_list: list) -> str:
    """从 item_list 中提取文本"""
    if not item_list:
        return ""
    for item in item_list:
        if isinstance(item, dict):
            text_item = item.get("text_item", {})
            if text_item:
                return text_item.get("text", "")
    return ""


MessageHandler = Callable[[WeChatMessage], None]


class WeChatReceiver:
    """
    微信消息接收器（长轮询）

    用法：
        receiver = WeChatReceiver(auth)

        def on_msg(msg):
            print(f"收到: {msg.content}")
            # context_token 会自动缓存

        receiver.add_handler(on_msg)
        receiver.poll_once()
    """

    def __init__(self, auth: WeChatAuth, poll_timeout: int = 35,
                 token_cache: Optional[TokenCache] = None):
        """
        Args:
            auth: 已登录的 WeChatAuth
            poll_timeout: 长轮询超时秒数（与服务器保持一致）
            token_cache: 共享的 TokenCache 实例，留空则新建
        """
        self.auth = auth
        self.poll_timeout = poll_timeout
        self.handlers: list[MessageHandler] = []
        self._running = False
        self._seen_ids: set[str] = set()
        self.token_cache = token_cache or TokenCache()

    def add_handler(self, handler: MessageHandler):
        """添加消息处理器"""
        self.handlers.append(handler)

    # -------- 获取消息（长轮询）--------

    def poll_once(self) -> int:
        """
        执行一次长轮询获取消息（POST 方式）

        Returns:
            收到的新消息数量
        """
        if not self.auth.check_login():
            logger.warning("微信未登录，无法接收消息")
            return 0

        creds = self.auth.credentials
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {creds.token}",
            "AuthorizationType": "ilink_bot_token",
            "User-Agent": "StockStrategySystem/1.0",
        }

        payload = {
            "bot_type": 3,
            "ilink_bot_id": creds.accountId,
            "timeout": self.poll_timeout,
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{BASE_URL}/ilink/bot/getupdates"

        try:
            req = Request(url, data=data, headers=headers, method="POST")
            with urlopen(req, timeout=self.poll_timeout + 10) as resp:
                result = json.loads(resp.read().decode())
        except URLError as e:
            logger.debug("消息轮询超时或网络错误: %s", e)
            return 0
        except json.JSONDecodeError:
            logger.debug("消息轮询返回格式异常")
            return 0
        except Exception as e:
            logger.debug("消息轮询异常: %s", e)
            return 0

        # 解析消息列表（POST 返回 {"msgs": [...]} 格式）
        msg_list = result.get("msgs", [])
        if not msg_list:
            return 0

        new_count = 0
        for raw in msg_list:
            msg = WeChatMessage.from_raw(raw)
            if not msg.msg_id or msg.msg_id in self._seen_ids:
                continue

            self._seen_ids.add(msg.msg_id)

            # 缓存 context_token
            if msg.context_token:
                self.token_cache.update(msg.context_token, msg.from_user_id)
                logger.debug("已缓存 context_token: %s...", msg.context_token[:20])

            # 调用消息处理器
            logger.info("收到微信消息: [%s] %s: %s",
                        msg.msg_type, msg.from_name or msg.from_user_id,
                        msg.content[:80])
            for handler in self.handlers:
                try:
                    handler(msg)
                except Exception as e:
                    logger.error("消息处理器异常: %s", e)
            new_count += 1

        return new_count

    # -------- 持续轮询 --------

    def start_polling(self, stop_event: Optional[Callable] = None):
        """
        持续长轮询（阻塞）

        Args:
            stop_event: 可选，返回 True 时停止轮询的函数
        """
        self._running = True
        logger.info("开始微信消息长轮询（超时 %d 秒）", self.poll_timeout)
        print("💬 微信消息监听中... 按 Ctrl+C 停止")
        print("📌 先发一条消息到微信机器人以获取 context_token")

        try:
            while self._running:
                if stop_event and stop_event():
                    break
                count = self.poll_once()
                if count > 0:
                    logger.info("本次轮询收到 %d 条新消息", count)
        except KeyboardInterrupt:
            logger.info("消息轮询被用户中断")
        finally:
            self._running = False
            logger.info("消息轮询已停止")

    def stop(self):
        """停止轮询"""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running
