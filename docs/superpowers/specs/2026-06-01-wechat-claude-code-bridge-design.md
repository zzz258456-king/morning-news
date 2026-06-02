# 微信与 Claude Code 互联设计方案

## 概述

通过腾讯官方 iLink API（ClawBot 插件），将个人微信与 Claude Code 深度互联，实现双向消息通信、远程审批、定时推送等功能。

## 方案选型

**选定方案：** claude-code-wechat（LinekForge 版）

**选择理由：**
- 基于腾讯官方 iLink API，合法安全，非逆向协议
- 功能最全面：消息收发、远程审批、对话记忆、定时心跳、全媒体支持
- 采用 Claude Code Channel 机制，作为 MCP Server 原生集成
- MIT 开源协议

**不选其他方案的原因：**
- cc-weixin：功能过于基础，无审批/记忆/心跳
- cli-wechat-bridge：功能中等，无记忆回放
- WeChatFerry：基于 Hook 技术，有封号风险，且已停止维护

## 设备与环境要求

### 手机端
- 微信最新版（iOS 8.0.70+ / 安卓 8.0.69+）
- 微信 → 我 → 设置 → 插件 → 开启 ClawBot
- ClawBot 将微信消息转发至腾讯 iLink 服务器（ilinkai.weixin.qq.com）

### 电脑端
- Windows / macOS / Linux 均可
- Node.js >= 18（本项目使用 v24.16.0）
- Claude Code >= 2.1.81（本项目使用 v2.1.158）
- claude.ai 账号（不支持 API Key）
- ffmpeg + ffprobe（可选，用于视频抽帧，本项目不需要）

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│ 手机 (Android + 微信 ClawBot)                                 │
│  微信 → 我 → 设置 → 插件 → ClawBot → [开启]                    │
│  所有消息经 ClawBot 转发至 iLink 服务器                         │
└────────────────────────┬────────────────────────────────────┘
                         │ iLink API (HTTP 长轮询)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Windows 电脑                                                  │
│                                                              │
│ claude-code-wechat (作为 Claude Code Channel)                  │
│                                                              │
│  ├── wechat-channel.ts    ← MCP Server 主入口                 │
│  ├── ilink-api.ts         ← iLink HTTP 调用层（轮询+发送）     │
│  ├── allowlist.ts         ← 白名单管理                         │
│  ├── chat-log.ts          ← 对话记忆持久化+回放                │
│  ├── heartbeat.ts         ← 定时心跳调度                       │
│  ├── media.ts             ← 媒体加解密/CDN 上传下载            │
│  ├── config.ts            ← 路径/超时/日志配置                 │
│  └── types.ts             ← 接口和常量定义                     │
│         │                                                     │
│         ▼                                                     │
│  Claude Code (主进程)                                          │
│  ├── 启动参数: --dangerously-load-development-channels         │
│  ├── 环境: claude.ai 账号登录                                  │
│  ├── 可执行: Bash / 文件操作 / Web搜索 / MCP工具               │
│  └── 通过 MCP 工具回复微信                                    │
└─────────────────────────────────────────────────────────────┘
```

## 核心功能清单

| 功能 | 模块 | 说明 |
|------|------|------|
| 文字消息收发 | ilink-api.ts | 微信 ↔ Claude Code 双向文字对话 |
| 媒体消息收发 | media.ts | 图片/文件/语音/视频（CDN 加解密） |
| 远程审批 | tools.ts | 敏感操作推送到微信确认（`/approve` / `/deny`） |
| 定时心跳 | heartbeat.ts | 每天随机时间发问候，聊天中不打扰，支持热重载 |
| 对话记忆 | chat-log.ts | 重启后回放最近 200 条对话，区分历史和当前 |
| 白名单 | allowlist.ts | 仅授权用户可与 Claude 对话，首消息用户自动添加 |
| TTS 语音 | tools.ts | 通过 `wechat_send_voice` 工具发送语音消息 |

## 数据流设计

### 微信 → Claude Code（发送任务/提问）
```
① 用户在微信聊天框输入消息
② ClawBot 插件拦截消息，发送至 iLink 服务器
③ claude-code-wechat 通过 HTTP 长轮询 (getupdates) 拉取消息
④ 消息解析后注入 Claude Code Session
⑤ Claude Code 执行任务（bash、读文件、代码等）
⑥ 处理完成后，通过 MCP 工具（wechat_reply）生成回复
⑦ 桥接程序通过 iLink API (sendmessage) 发送回复
⑧ 回复出现在微信聊天界面
```

### Claude Code → 微信（推送通知/审批请求）
```
① Claude Code 在运行过程中需要推送消息
② 调用 MCP 工具 wechat_reply / wechat_send_file / wechat_send_voice
③ 桥接程序拦截工具调用
④ 通过 iLink API 发送消息到用户微信
⑤ 用户在手机上收到通知
```

## 安全设计

1. **白名单机制**：未授权的微信用户发消息会被静默丢弃
2. **首消息自动授权**：第一个发消息的用户自动加入白名单（符合预期的使用场景）
3. **远程审批**：高危操作需微信确认才执行
4. **官方协议**：基于腾讯官方 iLink API，非逆向/非 Hook，无封号风险

## 部署步骤

See implementation plan.

## 测试验证

1. 文字消息：微信发 "你好" → 确认 Claude 回复
2. 文件传输：微信发图片 → 确认 Claude 收到并描述图片
3. 工具调用：微信发 "帮我查看当前目录" → 确认执行 bash 并回传结果
4. 双向推送：在 Claude Code 中手动调用 wechat_reply → 确认微信收到
5. 白名单：用其他微信发消息 → 确认静默丢弃

## 注意事项

1. `--resume` 与 `channel flag` 不兼容，无法使用对话恢复功能
2. 需要保持电脑终端运行（可使用后台 Daemon 模式或搭配 tmux/screen）
3. ClawBot 仍处于灰度阶段，若未来微信政策变化可能影响可用性
4. 建议配合开机自启脚本使用
