# WorkBuddy 集成

本仓库自带一个 [WorkBuddy](https://www.workbuddy.cn/) 技能（skill），
让 WorkBuddy 智能体直接使用 `boss` 命令行，并内置了已知问题的绕行方案。

技能目录：`skills/boss-agent-cli/`

```
skills/boss-agent-cli/
├── SKILL.md                  技能正文（中文）
├── scripts/chat_history.py   chatmsg bug 的绕行脚本
└── references/pitfalls.md    已知问题排查手册
```

## 安装

**方式一：安装脚本（推荐）**

```bash
git clone https://github.com/davids-dot/boss-agent-cli.git
cd boss-agent-cli
scripts/install-skill.sh
```

**方式二：手动复制**

```bash
cp -r skills/boss-agent-cli ~/.workbuddy/skills/
```

想换安装目录用环境变量：`SKILL_INSTALL_DIR=~/.skills scripts/install-skill.sh`

## 验证

```bash
ls ~/.workbuddy/skills/boss-agent-cli/SKILL.md
```

装好后，在 WorkBuddy 里提到「BOSS 直聘」「沟通记录」「取回某个 HR 的完整对话」
这类需求时，智能体会自动加载该技能。

## 更新

技能与 CLI 同仓库维护，拉取最新代码后重装即可：

```bash
git pull && scripts/install-skill.sh
```

脚本会覆盖同名目录；如果你改过本地副本，先自行备份。

## 前置条件

技能假设你已经完成 CLI 的安装与登录，详见
[getting-started.md](../getting-started.md)：

```bash
uv tool install boss-agent-cli
export BOSS_CDP_URL=http://localhost:9222   # Chrome 需带 --remote-debugging-port 启动
boss login
boss status
```

## 已知问题

技能里已内置 `chatmsg` 必现 bug 的绕行方案，以及其他常见坑的排查表，
详见 `skills/boss-agent-cli/references/pitfalls.md`。
