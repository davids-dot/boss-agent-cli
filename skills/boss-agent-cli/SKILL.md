---
name: boss-agent-cli
title: "boss-agent-cli · BOSS 直聘沟通与职位数据"
description: "操作本机 boss-agent-cli（BOSS 直聘求职者侧自动化）：查看沟通列表与真实对话流、搜索职位、读简历/求职期望。当用户提到 BOSS 直聘、沟通记录、聊天消息、招聘者联系、投递进度、求职情况，或需要取回某个 HR 的完整对话时使用。含 chatmsg 必现 bug 的正确绕行方案。"
---

# boss-agent-cli · BOSS 直聘沟通与职位数据

`boss-agent-cli` 通过 Chrome CDP 复用已登录会话，把 BOSS 直聘的沟通与职位数据暴露成
JSON 信封（`{ok, data, error, hints}`）供 agent 消费。

## 前置检查（动手前先做）

```bash
boss --version                              # 若未装：uv tool install boss-agent-cli
export BOSS_CDP_URL=http://localhost:9222    # 默认端口 9222；与本机其他调试端口冲突时自行改
boss status                                 # logged_in / auth_state=complete 才可用
curl -s http://localhost:9222/json/version | head -3   # 确认 Chrome CDP 在线
```

- Chrome 必须**带 `--remote-debugging-port=9222` 启动**。若用户的 Chrome 已在运行且没开 CDP，
  **不要 `pkill`** —— 那会关掉他正在用的窗口和标签页。改用**独立 `--user-data-dir`** 另起一个实例，
  两者互不干扰：

  ```bash
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="$HOME/.boss-agent/chrome-cdp-profile" \
    --no-first-run --no-default-browser-check \
    --no-sandbox --disable-gpu --disable-dev-shm-usage \
    "--remote-allow-origins=*" about:blank
  ```

  - `--no-sandbox --disable-gpu`：从受限/沙箱化的父进程启动时，Chrome 会因
    `sandbox initialization failed` 触发 `GPU process isn't usable. Goodbye.` 直接崩，加这两个参数可绕开。
  - zsh 下 `--remote-allow-origins=*` **必须加引号**，否则报 `no matches found`。
  - 该实例要常驻；`nohup … &` 在调用方退出后会被回收，请用受管后台任务启动。
- 数据目录 `~/.boss-agent/`，登录态 `~/.boss-agent/auth/session.enc`
- **先判断 Cookie 提取链路是否可用再动手**：`boss login` 的自动提取要求浏览器里确实存在
  `wt2` 与 `__zp_stoken__`。只读查一下（不需要解密 cookie 值）：

  ```bash
  cp ~/Library/Application\ Support/Google/Chrome/Default/Cookies /tmp/ck.db
  sqlite3 /tmp/ck.db "select name from cookies where host_key like '%zhipin%';"
  ```

  若结果里没有 `wt2`，说明浏览器并未登录 BOSS，Cookie 链路必然失败 —— 直接走扫码
  （`boss login` 或 `boss login --cdp`），别在提取上浪费时间。
- 未登录时先 `boss login`

## 常用命令

```bash
boss chat --days 7            # 沟通列表：公司/姓名/职位/发起方/最后一条消息/时间
boss chat --days 30           # 回看 30 天
boss chat --from boss         # 只看对方主动联系我的
boss chat --export md -o ./chat.md
boss me --section user        # 基本信息
boss me --section resume      # 简历
boss search "Python" --city 北京 --welfare "双休"
boss detail <security_id>     # 职位详情
boss show 3                   # 搜索结果中第 3 个职位
boss greet <sid> <jid> --message "…"
boss shortlist add <sid> <jid>
boss stats                    # 投递漏斗
boss doctor                   # 环境自检
```

`boss chat` **只给每个会话的最后一条消息**，拿不到对话流 —— 要完整对话流见下一节。

## 取完整对话流 ⚠️ 必读

`boss chatmsg <security_id>` 在 **v2.0.0 及更早版本必然报 `JOB_NOT_FOUND`**。
**这是项目自身的 bug，不是用法问题**：

- `security_id` 是 BOSS **每次请求轮换**的加密令牌（216 字符，`~~` 结尾）
- `chat` 与 `chatmsg` 内部调的是**同一个** `friend_list` 接口，两次调用拿到的令牌必然不同，
  而匹配逻辑用 `securityId == security_id` 精确比较 → 永远失败
- 把 `friend_list` 当场返回的 sid 传进去同样失败（`chatmsg` 会再查一次）
- 结论：**不存在任何"可以传对"的取值**，不要在 security_id 上反复试

### 绕行方案：按数值 uid 关联

用本技能目录下的脚本（安装后位于 `~/.workbuddy/skills/boss-agent-cli/scripts/chat_history.py`）：

```bash
export BOSS_CDP_URL=http://localhost:9222
BOSS_PY=~/.local/share/uv/tools/boss-agent-cli/bin/python3   # 必须用 CLI 自带解释器，见下
"$BOSS_PY" <本技能目录>/scripts/chat_history.py              # 最近 12 个会话
"$BOSS_PY" <本技能目录>/scripts/chat_history.py --limit 30
"$BOSS_PY" <本技能目录>/scripts/chat_history.py --name "张"   # 只查姓名包含该串的
"$BOSS_PY" <本技能目录>/scripts/chat_history.py --json        # 输出 JSON
```

**别用系统 `python3`。** `boss_agent_cli` 依赖含编译扩展（greenlet、patchright 等），
用与安装 boss-agent-cli 时不同的 Python 跑会报
`ModuleNotFoundError: No module named 'greenlet._greenlet'` —— 这个报错点离病根很远，
容易误判成"装坏了"。脚本检测到版本不匹配时会直接提示该用哪个解释器；
装在非标准位置时也可 `export BOSS_AGENT_SITE=<含 boss_agent_cli 的 site-packages>` 指路。

脚本原理（要自己实现时照抄）：

1. `friend_list(page=1)` 一次返回全部联系人，每条含数值 `uid` + 当次有效的 `securityId`
2. 用 `(brandName, name)` 把 `boss chat` 列表项对应到 friend_list 条目，
   同名时用 `encryptJobId` 消歧
3. `chat_history(gid=uid, securityId=friend_list 返回的 sid, count=50)` → `zpData.messages`
4. 消息 `type`：1文本 2图片 3招呼 4简历 5系统 6名片 7语音 8视频 9表情；
   `from.uid != gid` 是自己发的。注意 `type=4`「简历卡片」在数据里 `from` 是**对方**，
   不要当成本人发出的简历
5. **对方在招的岗位藏在招呼卡片里**：`type=3` 且 `body.type==8` 的消息，
   `body.jobDesc` 含 `title` / `salary` / `city` / `experience` / `education`，
   `body.jobDesc.bottomText` 记着发起时间与方向。`boss chat` 返回的 `title` 是招聘者
   **自己的头衔**（CEO、招聘总监…），不是岗位名，两者别混淆
6. 每个会话之间 `sleep 2.5s` 控频，避免 `code:37` 风控

> 上游已有修复（按 uid 匹配 + 用本次返回的 securityId）。若你装的版本里
> `boss chat` 已输出 `uid`，直接 `boss chatmsg <uid>` 即可，不再需要脚本。

## 常见坑速查

| 现象 | 原因 / 解法 |
|---|---|
| `boss me --section expect` 报 `code:19` | 该接口 stoken 在 CDP httpx 模式下注入失败；改用 CDP 打开 `https://www.zhipin.com/web/geek/resume` 读 DOM |
| 搜索返回 `code:37 ENVIRONMENT_RISK` | 连续搜索 4+ 次触发风控；每次搜索间隔 >3 秒 |
| `chat --export -o /tmp/x.md` 报 `INVALID_PARAM` | 路径安全守卫只允许输出到 data_dir 或 cwd 下，别写到 `/tmp` |
| `--days 30` 的条数忽多忽少 | 它是**滑动窗口**，跨过边界的会话会掉出，不是 bug |
| 拿不到常用语 | CLI 无此命令；CDP 打开 `https://www.zhipin.com/web/geek/chat` 读重复发送的消息 |
| 发附件简历 | CLI 无此命令（只有招聘者侧）；需在网页聊天界面用 CDP 操作 |
| 改了源码不生效 | 全局 `boss` 走 uv **tool** 环境，与项目 `.venv` 是两套；验证改动要用对应环境的入口 |
| `chat_history.py` 报 `No module named 'greenlet._greenlet'` | 用了别的 Python 解释器；改用 `~/.local/share/uv/tools/boss-agent-cli/bin/python3` |
| Chrome 启动即崩，日志里有 `GPU process isn't usable. Goodbye.` | 受限环境下 Chrome 沙箱起不来；加 `--no-sandbox --disable-gpu` 重启 |
| `boss login --cdp` 报 `CDP_UNAVAILABLE` | 多半是 Chrome 进程已经退出；先 `curl -s http://localhost:9222/json/version` 确认 |
| zsh 下传 `--remote-allow-origins=*` 报 `no matches found` | shell 把 `*` 当通配符展开；给整个参数加引号 |
| `boss chat` 里找不到 `last_message` 字段 | 字段名是 `last_msg`；`--no-json` 也不存在，子命令只输出 JSON |

完整证据链与排查过程见 `references/pitfalls.md`。

## 不要做的事

- **不要用脚本批量打招呼。** BOSS 对高频自动打招呼有风控，轻则 `code:37`，重则封号。
  本技能**不提供**任何批量打招呼脚本。
- 不要解析 stderr；CLI 只保证 stdout 是 JSON 信封。
- 不要把登录态、cookie、简历文件内容写进任何会被提交或分享的地方。
