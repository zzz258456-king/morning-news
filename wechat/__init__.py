"""
微信互联模块 — 基于微信 iLink ClawBot API

功能：
    - 扫码登录 / 凭证管理
    - 发送文本、Markdown、图片消息
    - 接收消息轮询
    - 与 StockStrategySystem 推送通道集成

依赖：
    pip install requests qrcode Pillow
"""
from wechat.bot import WeChatBot
from wechat.auth import WeChatAuth

__all__ = ["WeChatBot", "WeChatAuth"]
