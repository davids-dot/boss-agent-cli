# boss-agent-cli 已知问题排查手册

面向使用 `boss-agent-cli` 的 agent 与用户。按「现象 → 根因 → 解法」组织。

## 1. `boss chatmsg <security_id>` 必现 JOB_NOT_FOUND

**影响版本**：v2.0.0 及更早。

**现象**

```json
{"ok": false, "error": {"code": "JOB_NOT_FOUND",
 "message": "未在沟通列表中找到 security_id=...，请确认该联系人存在"}}
```

而 `boss schema` 对该参数的说明正是「联系人的 security_id（从 chat 命令获取）」——
按文档把 `boss chat` 的输出喂给 `boss chatmsg`，必然失败。

**根因**

`security_id` 是 BOSS 服务端**每次请求重新生成**的加密令牌（长度 216，以 `~~` 结尾），
同一联系人在两次请求中会拿到完全不同的值。

关键在于：`chat` 与 `chatmsg` 内部调用的是**同一个** `platform.friend_list(page=...)`，
而匹配逻辑用 `securityId == security_id` 做精确比较 —— 两次调用的令牌必然不同，
所以匹配永远失败。这不是「两个接口加密方式不同」的问题。

**证据链**

| 字段 | 多次请求中的表现 |
|---|---|
| `encrypt_job_id` | 完全一致 |
| `last_ts` | 完全一致 |
| `last_msg` | 完全一致 |
| `security_id` | **每次都不同** |

会话对象完全一致（排除「不同会话 / 不同职位」），只有令牌在轮换。

**不存在任何"可以传对"的取值**：把 `friend_list` 当场返回的 sid（该值直接用于
`chat_history` 是成功的）传给 `boss chatmsg`，仍然失败 —— 因为 `chatmsg` 内部会
再查一次 `friend_list`，拿到的令牌又变了。

**根因起点**：构造沟通列表输出时，原始条目里本就有稳定且唯一的 `uid`
（实测全部条目都有、互不重复），但输出只保留了 `security_id`，把 `uid` 丢掉了，
导致 CLI 侧没有任何可跨请求复用的句柄。

**解法**

1. 短期：用按 `uid` 关联的绕行脚本（见 `SKILL.md` 或 `scripts/chat_history.py`）
2. 根本：输出补 `uid`；匹配键改用 `uid`，`securityId` 仅作为 `chat_history` 的调用参数；
   并且**必须用本次 `friend_list` 返回的 `securityId`**，不能透传调用方入参

## 2. `boss me --section expect` 报 code:19「参数值错误」

该接口（`/wapi/zpgeek/resume/expect/query.json`）的 stoken 在 CDP httpx 模式下
无法正确注入 GET 参数，这个接口尤其敏感。

**解法**：用 CDP 导航到 `https://www.zhipin.com/web/geek/resume`，
从 DOM `innerText` 里读「期望职位」段落（含方向、薪资、城市）。

定位时可用 `scripts/debug_resume_expect.py`（在仓库根目录执行）绕过 CLI 直接调平台层，
用来区分「鉴权链路没注入 stoken」还是「接口本身变了」。该脚本只打印 token 的键名，
不输出任何凭据原文。

## 3. 搜索报 code:37 ENVIRONMENT_RISK

连续搜索 4 次以上触发环境风控。**解法**：每次搜索间隔 >3 秒，
避免短时间内用不同关键词连搜。取对话流时同理（脚本里已内置 2.5s 间隔）。

## 4. `boss chat --export -o /tmp/xxx` 报 INVALID_PARAM（退出码 1）

导出有路径安全校验：只允许输出到 data_dir 或当前工作目录下的路径。
写到 `/tmp` 会被拒绝。**解法**：输出到家目录或项目目录内。

## 5. `boss chat --days N` 的条数忽多忽少

`--days` 是**滑动窗口**，跨过时间边界的会话会掉出。不是 bug。

## 6. 拿不到常用语 / 发不了附件简历

CLI 都没有对应命令（常用语无命令；附件简历只有招聘者侧的请求/接收/下载）。
**解法**：CDP 打开网页端操作——
- 常用语：`https://www.zhipin.com/web/geek/chat`，从历史消息里读重复发送的内容
- 附件简历：进入对话 → 发简历按钮 → 选择附件

## 7. 改了源码却不生效

全局 `boss` 命令通常装在 uv **tool** 环境里
（`~/.local/share/uv/tools/boss-agent-cli/`），和项目的 `.venv` 是两套环境。
验证本地代码改动要用对应环境的入口，否则跑的还是旧代码。

## 8. Chrome CDP 连不上

Chrome 必须**带 `--remote-debugging-port=9222` 启动**。若 Chrome 已在运行且没开 CDP，
由于 Electron 单实例限制，**必须先 pkill 再重启**才生效。

## 排查建议

- 先看 `boss doctor` 的自检输出
- 再看 `boss status` 确认登录态
- 只解析 stdout；stderr 是日志和进度，不保证结构
- 拿不准命令契约时先跑 `boss schema`
