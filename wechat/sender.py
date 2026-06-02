"""
微信消息发送器 — 基于 iLink ClawBot API

API 端点: POST /ilink/bot/sendmessage
认证: Bearer token + AuthorizationType: ilink_bot_token + X-WECHAT-UIN

注意：
    - 主动发送消息需要缓存 context_token（从收到的消息中获取）
    - context_token 有效期约 24 小时
    - 建议先运行 --wechat 模式接收消息缓存 token 后再主动推送
"""
import base64
import json
import logging
import random
from pathlib import Path
from typing import Optional

from urllib.request import Request, urlopen
from urllib.error import URLError

from wechat.auth import WeChatAuth, BASE_URL

logger = logging.getLogger(__name__)

# context_token 缓存文件
CONTEXT_CACHE_FILE = Path.home() / ".claude" / "channels" / "wechat" / "context_cache.json"


class TokenCache:
    """context_token 缓存管理"""

    def __init__(self, cache_file: Path = CONTEXT_CACHE_FILE):
        self.cache_file = cache_file
        self._tokens: dict[str, dict] = {}  # user_id -> {token, updated_at}
        self._default_token: Optional[str] = None  # 最近一次收到的 token
        self._load()

    def _load(self):
        """从文件加载缓存"""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                self._tokens = data.get("tokens", {})
                self._default_token = data.get("default_token")
            except Exception as e:
                logger.debug("加载 context_token 缓存失败: %s", e)

    def _save(self):
        """保存缓存的 token 到文件"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tokens": self._tokens,
            "default_token": self._default_token,
        }
        self.cache_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(self, context_token: str, from_user_id: Optional[str] = None):
        """更新 token 缓存"""
        self._default_token = context_token
        if from_user_id:
            import time
            self._tokens[from_user_id] = {
                "token": context_token,
                "updated_at": time.time(),
            }
        self._save()

    def get(self, to_user_id: Optional[str] = None) -> Optional[str]:
        """
        获取缓存的 context_token

        Args:
            to_user_id: 目标用户 ID，有则返回该用户的 token

        Returns:
            context_token 或 None
        """
        if to_user_id and to_user_id in self._tokens:
            return self._tokens[to_user_id]["token"]
        return self._default_token

    def get_all_users(self) -> list[str]:
        """获取所有已缓存用户 ID 列表（按更新时间降序）"""
        return sorted(
            self._tokens.keys(),
            key=lambda u: self._tokens[u].get("updated_at", 0),
            reverse=True,
        )

    def clear(self):
        """清除所有缓存"""
        self._tokens = {}
        self._default_token = None
        if self.cache_file.exists():
            self.cache_file.unlink()


class WeChatSender:
    """
    微信消息发送器

    使用正确的 iLink ClawBot sendmessage API。

    用法：
        sender = WeChatSender(auth)
        sender.send_text("你好！", to_user_id="user@im.wechat")
    """

    def __init__(self, auth: WeChatAuth, token_cache: Optional[TokenCache] = None):
        self.auth = auth
        self.token_cache = token_cache or TokenCache()

    def _gen_uin(self) -> str:
        """生成随机的 X-WECHAT-UIN"""
        uin_bytes = random.randint(0, 2**32 - 1).to_bytes(4, "big")
        return base64.b64encode(uin_bytes).decode()

    def _headers(self) -> dict:
        """构建 API 请求头"""
        if not self.auth.credentials:
            raise RuntimeError("微信未登录")

        return {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.auth.credentials.token}",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._gen_uin(),
            "User-Agent": "StockStrategySystem/1.0",
        }

    def _resolve_recipient(self, to_user_id: Optional[str] = None) -> str:
        """
        解析目标用户 ID

        优先级：
          1. 显式传入的 to_user_id
          2. TokenCache 中最近联系过的用户
          3. 凭证中保存的 userId

        Returns:
            用户 ID（可能为空）
        """
        if to_user_id:
            return to_user_id

        # 检查缓存中有没有联系过的用户
        cached_users = self.token_cache.get_all_users()
        if cached_users:
            # 取最近联系的用户
            return cached_users[0]

        # 最后用凭证中的 userId
        if self.auth.credentials and self.auth.credentials.userId:
            return self.auth.credentials.userId

        return ""

    def _build_msg_payload(self, text: str, to_user_id: Optional[str] = None) -> dict:
        """
        构建 sendmessage 标准请求体

        Args:
            text: 消息文本
            to_user_id: 目标用户 ID（@im.wechat 格式），留空自动选择
        """
        target = self._resolve_recipient(to_user_id)
        ctx_token = self.token_cache.get(target) if target else self.token_cache.get()
        bot_id = self.auth.credentials.accountId if self.auth.credentials else ""

        return {
            "msg": {
                "from_user_id": "",
                "to_user_id": target,
                "client_id": f"openclaw-weixin-{random.randint(0, 0xffffffff):08x}",
                "message_type": 2,
                "message_state": 2,
                "context_token": ctx_token or "",
                "item_list": [
                    {
                        "type": 1,
                        "text_item": {
                            "text": text,
                        },
                    }
                ],
            },
            "base_info": {
                "channel_version": "1.0.2",
            },
        }

    # -------- 发送文本 --------

    def send_text(self, content: str, to_user_id: Optional[str] = None) -> bool:
        """
        发送文本消息

        Args:
            content: 文本内容
            to_user_id: 目标用户 ID，留空自动选择最近联系人

        Returns:
            True 表示发送成功
        """
        if not self.auth.check_login():
            logger.error("发送失败：微信未登录")
            return False

        payload = self._build_msg_payload(content, to_user_id)
        return self._do_post(payload, "文本消息")

    # -------- 发送图片 --------

    def send_image(self, image_path: str, to_user_id: Optional[str] = None) -> bool:
        """
        发送图片消息

        目前 iLink API 图片发送需要先上传到 CDN，此处先用文本通知。
        完整图片功能需要实现 CDN 上传流程。

        Args:
            image_path: 图片文件路径
            to_user_id: 目标用户 ID
        """
        logger.warning("图片发送需要 CDN 上传，暂不支持。改用文本提示。")
        return self.send_text(f"[图片] {image_path}", to_user_id)

    # -------- 发送报告（分段）--------

    def send_report(self, title: str, body: str, to_user_id: Optional[str] = None) -> bool:
        """
        发送格式化报告

        Args:
            title: 标题
            body: 正文
            to_user_id: 目标用户 ID，留空自动选择
        """
        header_ok = self.send_text(f"📋 {title}", to_user_id)
        if not header_ok:
            return False

        max_len = 1500
        if len(body) <= max_len:
            return self.send_text(body, to_user_id)

        # 分段发送
        paragraphs = body.split("\n\n")
        chunk = ""
        success = True

        for para in paragraphs:
            if len(chunk) + len(para) + 2 > max_len:
                if chunk.strip():
                    success = self.send_text(chunk.strip(), to_user_id) and success
                chunk = para + "\n\n"
            else:
                chunk += para + "\n\n"

        if chunk.strip():
            success = self.send_text(chunk.strip(), to_user_id) and success

        return success

    # -------- 低层级请求 --------

    def _do_post(self, payload: dict, label: str = "") -> bool:
        """执行 sendmessage POST 请求"""
        url = f"{BASE_URL}/ilink/bot/sendmessage"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            req = Request(url, data=data, headers=self._headers(), method="POST")
            with urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
            # iLink API 成功返回 {} (空对象) 或 {"ret":0}
            ret = result.get("ret", 0) if result else 0
            if ret == 0:
                logger.info("✅ 微信 %s 发送成功", label)
                return True
            else:
                msg = result.get("msg", f"错误码 {ret}")
                logger.warning("❌ 微信 %s 发送失败: %s", label, msg)
                return False
        except URLError as e:
            logger.error("❌ 微信 %s 网络错误: %s", label, e)
            return False
        except json.JSONDecodeError:
            logger.error("❌ 微信 %s 返回格式异常", label)
            return False
        except Exception as e:
            logger.error("❌ 微信 %s 发送异常: %s", label, e)
            return False
