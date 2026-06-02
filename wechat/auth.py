"""
微信 iLink ClawBot 扫码登录 & 凭证管理

API 端点：
    - 获取二维码: GET /ilink/bot/get_bot_qrcode?bot_type=3
    - 轮询状态:  GET /ilink/bot/get_qrcode_status?qrcode={qrcode}
    - bot_type=3 表示个人微信机器人

流程：
    1. 获取二维码 → 显示给用户扫码
    2. 轮询等待用户扫码 + 确认
    3. 确认后保存 token / bot_id / user_id
    4. 后续所有请求用 token 鉴权
"""
import json
import logging
import os
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://ilinkai.weixin.qq.com"
BOT_TYPE = "3"  # 个人微信机器人

# 凭证默认存储路径
CRED_DIR = Path.home() / ".claude" / "channels" / "wechat"
CRED_FILE = CRED_DIR / "account.json"


@dataclass
class WeChatCredentials:
    """微信机器人凭证"""
    token: str
    baseUrl: str
    accountId: str
    userId: str
    savedAt: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "WeChatCredentials":
        return cls(
            token=d.get("token", ""),
            baseUrl=d.get("baseUrl", BASE_URL),
            accountId=d.get("accountId", "") or d.get("ilink_bot_id", ""),
            userId=d.get("userId", "") or d.get("ilink_user_id", ""),
            savedAt=d.get("savedAt", ""),
        )


@dataclass
class QRCodeResult:
    """二维码信息"""
    qrcode: str          # 用于轮询的 key
    qrcode_img_content: str  # 二维码图片内容（文本）
    expired_time: int = 0
    ret: int = 0


class WeChatAuth:
    """
    微信 ClawBot 认证管理

    用法：
        auth = WeChatAuth()
        # 交互式登录（控制台显示二维码）
        creds = auth.login_interactive()
        # 或使用已有凭证
        if auth.load_credentials():
            print("已登录:", auth.credentials)
    """

    def __init__(self, cred_file: Optional[Path] = None):
        self.credentials: Optional[WeChatCredentials] = None
        self.cred_file = cred_file or CRED_FILE

    # -------- 二维码获取 --------

    def fetch_qrcode(self) -> Optional[QRCodeResult]:
        """获取登录二维码"""
        url = f"{BASE_URL}/ilink/bot/get_bot_qrcode?bot_type={BOT_TYPE}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ClaudeCode/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            if data.get("ret") != 0:
                logger.error("获取二维码失败: %s", data.get("msg", "未知错误"))
                return None
            return QRCodeResult(
                qrcode=data["qrcode"],
                qrcode_img_content=data["qrcode_img_content"],
                expired_time=data.get("expired_time", 480),
                ret=data.get("ret", 0),
            )
        except Exception as e:
            logger.error("获取二维码异常: %s", e)
            return None

    # -------- 状态轮询 --------

    def poll_status(self, qrcode: str, timeout: int = 480) -> Optional[WeChatCredentials]:
        """
        轮询扫码状态，直到用户扫码确认或超时

        Args:
            qrcode: 二维码 key
            timeout: 超时秒数（默认 8 分钟）

        Returns:
            扫码成功返回 WeChatCredentials，失败返回 None
        """
        deadline = time.time() + timeout
        scanned = False

        logger.info("等待微信扫码（超时 %d 秒）...", timeout)

        while time.time() < deadline:
            status = self._query_status(qrcode)
            if status is None:
                time.sleep(2)
                continue

            s = status.get("status", "wait")

            if s == "wait":
                print(".", end="", flush=True)
            elif s == "scaned":
                if not scanned:
                    print("\n✅ 已扫码，请在微信中确认登录...")
                    scanned = True
            elif s == "expired":
                print("\n❌ 二维码已过期")
                return None
            elif s == "confirmed":
                bt = status.get("bot_token")
                bid = status.get("ilink_bot_id") or status.get("bot_id")
                burl = status.get("baseurl", BASE_URL)
                uid = status.get("ilink_user_id") or status.get("user_id")

                if not bt or not bid:
                    print("\n❌ 服务器未返回完整信息")
                    return None

                creds = WeChatCredentials(
                    token=bt,
                    baseUrl=burl,
                    accountId=str(bid),
                    userId=str(uid),
                    savedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                self.credentials = creds
                self._save_credentials(creds)
                print(f"\n🎉 微信登录成功！账号ID: {creds.accountId}")
                return creds

            time.sleep(2)

        print("\n⏰ 登录超时")
        return None

    def _query_status(self, qrcode: str) -> Optional[dict]:
        """查询二维码状态"""
        url = f"{BASE_URL}/ilink/bot/get_qrcode_status?qrcode={urllib.parse.quote(qrcode)}"
        req = urllib.request.Request(url, headers={"iLink-App-ClientVersion": "1"})
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug("状态查询异常: %s", e)
            return None

    # -------- 凭证管理 --------

    def _save_credentials(self, creds: WeChatCredentials):
        """保存凭证到文件"""
        self.cred_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cred_file, "w", encoding="utf-8") as f:
            json.dump(asdict(creds), f, indent=2, ensure_ascii=False)
        logger.info("凭证已保存至: %s", self.cred_file)

    def load_credentials(self) -> bool:
        """从文件加载已保存的凭证"""
        if not self.cred_file.exists():
            logger.warning("未找到已保存的凭证: %s", self.cred_file)
            return False

        try:
            with open(self.cred_file, encoding="utf-8") as f:
                data = json.load(f)
            self.credentials = WeChatCredentials.from_dict(data)

            # 简单验证 token 有效性
            if not self.credentials.token or not self.credentials.accountId:
                logger.warning("凭证不完整，请重新登录")
                return False

            logger.info("已加载微信凭证（账号ID: %s）", self.credentials.accountId)
            return True
        except Exception as e:
            logger.error("加载凭证失败: %s", e)
            return False

    def check_login(self) -> bool:
        """
        检查是否已登录。优先加载已有凭证，优先于重新登录。

        Returns:
            True 表示已登录可用
        """
        if self.credentials and self.credentials.token:
            return True
        return self.load_credentials()

    # -------- 交互式登录 --------

    def login_interactive(self) -> Optional[WeChatCredentials]:
        """交互式登录：获取二维码 → 等待扫码 → 保存凭证"""
        # 先检查是否已有有效凭证
        if self.load_credentials():
            logger.info("已有有效凭证，无需重新登录")
            return self.credentials

        print("\n" + "=" * 50)
        print("🔐  微信 ClawBot 扫码登录")
        print("=" * 50)

        # 1. 获取二维码
        qr = self.fetch_qrcode()
        if not qr:
            print("❌ 获取二维码失败，请检查网络")
            return None

        # 2. 输出二维码内容（文本二维码）
        print(f"\n📱 请使用微信扫描下方二维码：\n")
        print(qr.qrcode_img_content)
        print()

        # 尝试生成二维码图片
        self._try_save_qr_image(qr.qrcode_img_content)

        # 3. 轮询等待扫码
        creds = self.poll_status(qr.qrcode, timeout=qr.expired_time or 480)
        return creds

    def _try_save_qr_image(self, qr_data: str):
        """尝试保存二维码图片（依赖 qrcode 库）"""
        try:
            import qrcode as qrcode_lib
            from PIL import Image  # noqa: F401

            save_path = Path(os.environ.get("TEMP", ".")) / "wechat_qrcode.png"
            qr = qrcode_lib.QRCode(box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(str(save_path))
            print(f"📸 二维码图片已保存: {save_path}")
            print(f"💡 打开图片扫码，或在浏览器中打开查看")
        except ImportError:
            print("💡 提示: pip install qrcode Pillow 可生成二维码图片")
        except Exception as e:
            logger.debug("保存二维码图片失败: %s", e)


# -------- 便捷函数 --------

def ensure_login(auth: Optional[WeChatAuth] = None) -> Optional[WeChatAuth]:
    """确保已登录，未登录则启动交互式登录"""
    if auth is None:
        auth = WeChatAuth()
    if not auth.check_login():
        print("尚未登录微信，启动扫码登录...")
        result = auth.login_interactive()
        if not result:
            print("微信登录失败，请重试")
            return None
    return auth
