"""
钉钉消息推送模块
通过钉钉机器人 webhook 发送 Markdown 格式的晨报
支持加签（HMAC-SHA256）和普通模式
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Optional

import requests

from .ai_analyzer import AnalysisResult
from .config import get_config

logger = logging.getLogger(__name__)

_DINGTALK_API = "https://oapi.dingtalk.com/robot/send"
_REQUEST_TIMEOUT = 10  # 秒


# ---------- 签名工具 ----------


def _sign(secret: str, timestamp: int) -> str:
    """生成钉钉机器人加签"""
    string_to_sign = f"{timestamp}\n{secret}"
    h = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    )
    return h.hexdigest()


# ---------- Markdown 消息构建 ----------


_STRENGTH_SYMBOLS = ["", "⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]


def _strength_str(strength: int) -> str:
    """强度转星标"""
    return _STRENGTH_SYMBOLS[max(0, min(5, strength))]


def _short(s: str, max_cn: int = 18) -> str:
    """将长文本截断为适合钉钉手机窄屏的短句"""
    if len(s) <= max_cn:
        return s
    return s[:max_cn - 1] + "…"


def build_markdown(result: AnalysisResult, source_names: list[str]) -> str:
    """
    构建适配钉钉手机窄屏的晨报 Markdown。
    设计原则：
    - 每行不超过 25 个汉字（钉钉群聊手机端约 20-25 字换行）
    - 不画表格、不写长段落
    - 重点突出，一眼获取核心信息
    """
    today = datetime.now().strftime("%m/%d")

    # --- 情绪标签 ---
    sentiment = result.market_sentiment or "中性"
    sentiment_map = {
        "谨慎乐观": "🟡谨慎乐观", "谨慎悲观": "🟠谨慎悲观",
        "乐观": "🟢乐观", "悲观": "🔴悲观", "中性": "⚪中性",
    }
    emoji_tag = "📊"
    for k, v in sentiment_map.items():
        if k in sentiment:
            emoji_tag = v
            break

    lines = [
        f"📰 **通知：晨报** {today}",
        f"📊 {emoji_tag}",
        f"🟢利好  🔴利空  🔥重点  ⚪中性",
        "",
    ]

    # =============================================
    # 🔥 核心推荐（每只股票 1 行）
    # =============================================
    if result.top_picks:
        lines.append("—🔥 核心推荐🔥—")
        lines.append("")
        for i, pick in enumerate(result.top_picks, 1):
            bar = _strength_str(pick.strength)
            lines.append(f"▶ **{i}. {pick.name}** {bar}")
            reason = _short(pick.reason, 36)
            lines.append(f"   {reason}")
            if pick.stocks:
                for st in pick.stocks:
                    s_short = _short(st.reason, 20)
                    lines.append(f"   📈 `{st.code}` {st.name} — {s_short}")
            lines.append("")

    # =============================================
    # 📋 板块一览（每行一个，不加长理由）
    # =============================================
    lines.append("—📋 板块 📋—")
    lines.append("")

    top_names = {p.name for p in result.top_picks}
    for pick in result.top_picks:
        lines.append(f"🔥 {pick.name} {_strength_str(pick.strength)}")
    for s in result.good_sectors:
        if s.name in top_names:
            continue
        brief = _short(s.reason, 15) if s.reason else ""
        sep = f" — {brief}" if brief else ""
        lines.append(f"🟢 {s.name}{sep}")

    if result.bad_sectors:
        for name in result.bad_sectors:
            lines.append(f"🔻 {_short(name, 22)}")
    lines.append("")

    # =============================================
    # 📌 要闻 & 📊 个股
    # =============================================
    if result.key_events:
        lines.append("—📌 要闻 📌")
        for ev in result.key_events:
            t = _short(ev.title, 26)
            sec = "、".join(ev.related_sectors[:2]) if ev.related_sectors else ""
            suffix = f" · `{sec}`" if sec else ""
            lines.append(f"• {t}{suffix}")
        lines.append("")

    # --- 其他个股 ---
    if result.stock_mentions:
        recommended_codes = set()
        for pick in result.top_picks:
            for st in pick.stocks:
                if st.code:
                    recommended_codes.add(st.code)
        filtered = [st for st in result.stock_mentions if st.code not in recommended_codes]
        if filtered:
            tag_map = {"利好": "🟢", "利空": "🔴", "中性": "⚪"}
            items = []
            for st in filtered:
                sym = tag_map.get(st.direction, "⚪")
                items.append(f"{sym}{st.name}")
            lines.append("📊 " + "  ".join(items))
            lines.append("")

    # =============================================
    # 🏷️ 尾部
    # =============================================
    source_str = "、".join(source_names)
    lines.append("———————")
    lines.append(f"_{source_str}_")
    lines.append("_⚠️ 仅供参考，不构成投资建议_")

    return "\n".join(lines)


# ---------- 发送逻辑 ----------


def send_dingtalk(markdown_text: str, title: Optional[str] = None) -> bool:
    """
    通过钉钉机器人发送 Markdown 消息

    Args:
        markdown_text: Markdown 格式的消息内容
        title: 消息标题，默认从配置读取

    Returns:
        发送成功返回 True
    """
    config = get_config()

    if not config.dingtalk.available:
        logger.error("钉钉 Webhook URL 未配置，无法发送消息")
        return False

    webhook_url = config.dingtalk.webhook_url
    secret = config.dingtalk.secret
    msg_title = title or config.dingtalk.title

    # 如果配置了加签，补充签名参数
    params = {}
    if secret:
        timestamp = int(time.time() * 1000)
        sign = _sign(secret, timestamp)
        params["timestamp"] = timestamp
        params["sign"] = sign

    # 构建请求体
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": msg_title,
            "text": markdown_text,
        },
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
    }

    logger.info("发送钉钉消息: title=%s", msg_title)
    logger.debug("Webhook URL: %s, params: %s", webhook_url, params)

    try:
        resp = requests.post(
            webhook_url,
            params=params,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=_REQUEST_TIMEOUT,
        )
        body = resp.json()
    except requests.Timeout:
        logger.error("钉钉消息发送超时（%d秒）", _REQUEST_TIMEOUT)
        return False
    except requests.RequestException as e:
        logger.error("钉钉消息发送失败: %s", e)
        return False
    except json.JSONDecodeError:
        logger.error("钉钉返回非 JSON 响应: %s", resp.text[:200])
        return False

    # 检查钉钉返回码
    errcode = body.get("errcode", -1)
    if errcode == 0:
        logger.info("钉钉消息发送成功")
        return True
    else:
        logger.error(
            "钉钉返回错误: code=%d, msg=%s",
            errcode,
            body.get("errmsg", ""),
        )
        return False


def send_analysis(result: AnalysisResult, source_names: list[str]) -> bool:
    """
    整合同步操作：构建 Markdown → 发送钉钉

    Args:
        result: 分析结果
        source_names: 数据来源名称列表

    Returns:
        发送成功返回 True
    """
    markdown = build_markdown(result, source_names)
    return send_dingtalk(markdown)
