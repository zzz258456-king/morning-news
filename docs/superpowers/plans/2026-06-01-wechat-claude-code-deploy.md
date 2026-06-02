# 微信与 Claude Code 互联 — 部署实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 Windows 上完成 claude-code-wechat 的安装、配置、测试，实现微信与 Claude Code 双向互联

**Architecture:** 通过 claude-code-wechat (MCP Channel Server) 桥接微信 iLink API 和 Claude Code，微信消息经过腾讯官方服务器中转，电脑端通过 HTTP 长轮询接收并响应

**Tech Stack:** Node.js (v24) + Claude Code (v2.1.158) + iLink API (腾讯官方)

---

### Task 1: 全局安装 claude-code-wechat

**文件/操作：**
- 执行 npm install -g

- [ ] **Step 1: 全局安装 npm 包**

```bash
npm install -g claude-code-wechat@latest
```

Expected: 安装成功，无报错

- [ ] **Step 2: 验证安装**

```bash
claude-code-wechat --version
```

Expected: 输出版本号（如 v0.3.0）

---

### Task 2: 扫码登录微信 ClawBot

**文件/操作：**
- 执行 npx claude-code-wechat setup

- [ ] **Step 1: 运行 setup 命令**

```bash
npx claude-code-wechat setup
```

Expected: 终端出现二维码

- [ ] **Step 2: 手机微信扫码登录**

打开手机微信 → 扫一扫 → 扫描终端二维码 → 确认登录

Expected: 终端显示 "登录成功"，凭据文件保存到本地

---

### Task 3: 生成 MCP 配置并安装

**文件/操作：**
- 执行 install 命令
- 确认 .claude/settings.json 被修改

- [ ] **Step 1: 运行 install 命令**

```bash
npx claude-code-wechat install
```

Expected: 成功生成 MCP 配置，注入到 Claude Code 的 settings.json 中

- [ ] **Step 2: 验证 MCP 配置生效**

```bash
claude mcp list
```

Expected: 列表中能看到 wechat 相关的 MCP server

---

### Task 4: 白名单配置

- [ ] **Step 1: 查看当前白名单**

```bash
npx claude-code-wechat setup --list
```

Expected: 显示白名单列表（首次为空或包含当前登录用户）

- [ ] **Step 2: 添加当前微信用户到白名单（如需要）**

```bash
npx claude-code-wechat setup --allow <你的微信ID> "<你的昵称>"
```

---

### Task 5: 首次启动 Claude Code + WeChat Channel

- [ ] **Step 1: 启动 Claude Code 并加载 WeChat Channel**

```bash
claude --dangerously-load-development-channels server:wechat
```

Expected: Claude Code 启动成功，终端显示 Channel 已连接

- [ ] **Step 2: 手机微信发送测试消息**

在微信中向 ClawBot 发送消息："你好，我是 Claude Code！"

Expected: Claude Code 收到消息并回复，微信端看到回复内容

---

### Task 6: 功能验证

- [ ] **Step 1: 文字对话测试**

微信发送："帮我看一下当前电脑的系统时间"

Expected: Claude 执行 bash 命令 `date`，返回结果到微信

- [ ] **Step 2: 工具调用测试**

微信发送："帮我写一个 Python hello world 脚本并保存"

Expected: Claude 创建文件并回复

- [ ] **Step 3: 文件传输测试（如支持）**

微信发送一张图片

Expected: Claude 接收图片（或提示不支持）

- [ ] **Step 4: 主动推送测试**

在 Claude Code 会话中执行：
```
请调用 wechat_reply 工具给微信发送一条消息："测试推送消息"
```

Expected: 微信收到 Claude Code 主动推送的消息

---

### Task 7: 开机自启配置（推荐）

- [ ] **Step 1: 创建启动脚本**

在 `D:\缓存区\` 下创建 `start-wechat-claude.bat`：

```batch
@echo off
cd /d C:\Users\Administrator
start "" cmd /c "claude --dangerously-load-development-channels server:wechat"
```

- [ ] **Step 2: 添加到开机启动**

将脚本添加到 Windows 开机启动项（shell:startup），或配置为计划任务

---

### Task 8: 收尾总结

- [ ] **Step 1: 提交设计文档和计划到 git**

```bash
cd C:\Users\Administrator\Desktop\_Projects\try
git add docs/superpowers/specs/2026-06-01-wechat-claude-code-bridge-design.md
git add docs/superpowers/plans/2026-06-01-wechat-claude-code-deploy.md
git commit -m "docs: 添加微信-Claude Code 互联设计方案和部署计划"
```
