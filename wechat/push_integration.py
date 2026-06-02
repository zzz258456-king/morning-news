"""
微信推送集成 — 将微信作为 StockStrategySystem 的推送通道

注意：微信 ClawBot 的 sendmessage API 需要 context_token，
该 token 只能通过接收消息获取。因此：

流程：
    1. 先启动 --wechat 进入消息监听模式，微信发一条消息到机器人
    2. context_token 被缓存到文件
    3. 后续推送可直接使用缓存 token 发送

如果 context_token 失效（超过 24 小时无交互），
需要重新让用户发消息给机器人刷新 token。
"""
import logging
from typing import Optional

from morning.config import get_config
from morning.dingtalk_sender import send_dingtalk

logger = logging.getLogger(__name__)

_wechat_bot = None


def get_wechat_bot():
    """获取微信 bot 单例"""
    global _wechat_bot
    if _wechat_bot is None:
        from wechat.bot import WeChatBot
        _wechat_bot = WeChatBot()
    return _wechat_bot


def wechat_available() -> bool:
    """检查微信推送是否可用（已登录 + 有 context_token）"""
    bot = get_wechat_bot()
    if not bot.login(interactive=False):
        return False
    if not bot.has_context_token:
        logger.warning("微信可用但无 context_token，请先运行 --wechat 接收消息获取 token")
        return False
    return True


# ============================================================
# 统一推送
# ============================================================

def push_notification(title: str, body: str = "",
                      channel: str = "auto",
                      msg_type: str = "info",
                      to_user_id: Optional[str] = None) -> bool:
    """
    统一推送 — 微信优先，失败回退钉钉

    Args:
        title: 标题
        body: 正文
        channel: auto/wechat/dingtalk/both
        msg_type: info/warning/error/success
        to_user_id: 微信目标用户 ID
    """
    cfg = get_config()
    success = False

    # 微信：auto 模式总是优先尝试，wechat/both 模式需要配置启用
    wechat_enabled = hasattr(cfg, 'wechat') and cfg.wechat.enabled

    if channel == "auto":
        wechat_ok = _push_wechat(title, body, msg_type, to_user_id)
        if wechat_ok:
            return True
        logger.info("微信不可用，回退钉钉: %s", title)

    elif channel in ("wechat", "both") and wechat_enabled:
        wechat_ok = _push_wechat(title, body, msg_type, to_user_id)
        if wechat_ok:
            success = True

    # 钉钉
    if channel in ("auto", "dingtalk", "both"):
        dingtalk_ok = _push_dingtalk(title, body)
        if dingtalk_ok:
            success = True

    return success


def _push_wechat(title: str, body: str, msg_type: str,
                 to_user_id: Optional[str] = None) -> bool:
    """通过微信推送"""
    try:
        bot = get_wechat_bot()
        if not bot.login(interactive=False):
            logger.warning("微信未登录，跳过推送")
            return False
        if not bot.has_context_token:
            logger.warning("无 context_token，无法推送。请先发消息给机器人")
            return False

        if body and len(body) > 10:
            return bot.send_report(title, body, to_user_id)
        else:
            return bot.send_notification(title, body, msg_type, to_user_id)
    except Exception as e:
        logger.debug("微信推送异常: %s", e)
        return False


def _push_dingtalk(title: str, body: str) -> bool:
    """通过钉钉推送"""
    try:
        full_md = f"# {title}\n\n{body}" if body else f"# {title}"
        return send_dingtalk(full_md, title=title)
    except Exception as e:
        logger.warning("钉钉推送异常: %s", e)
        return False


# ============================================================
# 特定推送
# ============================================================

def push_morning_report(markdown: str, title: str = "📰 财经新闻晨报") -> bool:
    """推送晨报到微信"""
    try:
        bot = get_wechat_bot()
        if bot.login(interactive=False) and bot.has_context_token:
            text_body = _md_to_wechat_text(markdown)
            return bot.send_report(title, text_body)
        logger.warning("微信未就绪，无法推送晨报")
        return False
    except Exception as e:
        logger.warning("微信推送晨报失败: %s", e)
        return False


def push_risk_warning(risk_section: str) -> bool:
    """推送风险预警"""
    return push_notification("【风险预警】市场风险评分", risk_section, msg_type="warning")


def push_evolution_report(report: str) -> bool:
    """推送策略进化报告"""
    return push_notification("【策略进化】遗传算法最优参数", report, msg_type="info")


def _md_to_wechat_text(md: str) -> str:
    """Markdown 转纯文本"""
    import re
    text = md
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '[图片]', text)
    text = re.sub(r'\[(.+?)\]\(.*?\)', r'\1', text)
    return text.strip()
