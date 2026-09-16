#!/usr/bin/env python3
"""boss chatmsg 的可用替代：按 uid 关联，取回真实对话流。

背景
----
`boss chatmsg <security_id>` 在 v2.0.0 及更早版本必然报 JOB_NOT_FOUND。
根因不是大小写格式问题，而是 security_id 是 BOSS **每次请求轮换**的加密令牌：
chat 列表与 friend_list 两次调用拿到的值不同，按 sid 字符串匹配永远失败。
正确做法是用 friend_list 的数值 uid 关联两边的同一联系人。

用法
----
    python3 chat_history.py                # 最近 12 个会话
    python3 chat_history.py --limit 30
    python3 chat_history.py --name "张"     # 只查姓名包含该串的联系人
    python3 chat_history.py --json         # 输出 JSON

前置
----
    export BOSS_CDP_URL=http://localhost:9222   # Chrome 已开 CDP 且已登录 BOSS
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

MSG_TYPE = {
	1: "文本", 2: "图片", 3: "招呼", 4: "简历", 5: "系统",
	6: "名片", 7: "语音", 8: "视频", 9: "表情",
}

CDP = os.environ.get("BOSS_CDP_URL", "http://localhost:9222")
DATA_DIR = Path(os.path.expanduser("~/.boss-agent"))


def _ensure_importable() -> None:
	"""把 boss_agent_cli 所在的 site-packages 加进 sys.path。

	本脚本不属于 boss-agent-cli 包，只是借用它的平台层，所以需要自己找包装在哪：
	优先直接用已安装的环境，其次扫 uv tool 目录，最后允许用 BOSS_AGENT_SITE 指路。
	"""
	try:
		import boss_agent_cli  # noqa: F401

		return
	except ImportError:
		pass

	override = os.environ.get("BOSS_AGENT_SITE")
	candidates = [override] if override else []
	if not candidates:
		patterns = [
			"~/.local/share/uv/tools/boss-agent-cli/lib/python3.*/site-packages",
			"~/.local/share/uv/tools/boss-agent-cli-*/lib/python3.*/site-packages",
		]
		for pattern in patterns:
			candidates.extend(glob.glob(os.path.expanduser(pattern)))

	candidates.sort(reverse=True)
	for candidate in candidates:
		if candidate and os.path.isdir(os.path.join(candidate, "boss_agent_cli")):
			sys.path.insert(0, candidate)
			return

	raise SystemExit(
		"找不到 boss_agent_cli。请先安装：uv tool install boss-agent-cli\n"
		"若装在非标准位置，用 BOSS_AGENT_SITE 指向包含 boss_agent_cli 的 site-packages。"
	)


def load_chat_list(days: int) -> list[dict]:
	"""借用 CLI 拿沟通列表（含公司/姓名/最后一条消息，用于匹配）。"""
	if shutil.which("boss") is None:
		raise SystemExit("PATH 里找不到 boss，请先安装：uv tool install boss-agent-cli")

	out = Path(tempfile.gettempdir()) / f"boss_chat_{days}d.json"
	env = dict(os.environ, BOSS_CDP_URL=CDP)
	subprocess.run(["boss", "chat", "--days", str(days)], stdout=out.open("w"), env=env, check=True)
	return json.loads(out.read_text()).get("data") or []


def fetch(limit: int, name_filter: str | None, days: int) -> list[dict]:
	_ensure_importable()
	from boss_agent_cli.auth.manager import AuthManager
	from boss_agent_cli.commands._platform import build_platform_instance

	auth = AuthManager(DATA_DIR, platform="zhipin")
	p = build_platform_instance("zhipin", auth, delay=(2.0, 3.5), cdp_url=CDP)

	resp = p.friend_list(page=1)
	data = p.unwrap_data(resp) or {}
	items = data.get("result") or data.get("friendList") or []

	# (brandName, name) -> [friend_item]；同名时用 encryptJobId 消歧
	idx: dict[tuple[str, str], list[dict]] = {}
	for it in items:
		key = ((it.get("brandName") or "").strip(), (it.get("name") or "").strip())
		idx.setdefault(key, []).append(it)

	snaps = load_chat_list(days)
	if name_filter:
		snaps = [s for s in snaps if name_filter in (s.get("name") or "")]
	snaps = snaps[:limit]

	results = []
	for s in snaps:
		key = ((s.get("brand_name") or "").strip(), (s.get("name") or "").strip())
		cands = idx.get(key) or []
		if not cands:
			results.append({
				**{k: s.get(k) for k in ("brand_name", "name", "title", "last_time")},
				"uid": None, "messages": [], "error": "friend_list 未匹配到",
			})
			continue

		jid = (s.get("encrypt_job_id") or "").strip()
		f = next((c for c in cands if jid and (c.get("encryptJobId") or "").strip() == jid), None) or cands[0]
		gid, sid = str(f.get("uid")), f.get("securityId")
		try:
			r = p.chat_history(gid, sid, page=1, count=50)
			d = p.unwrap_data(r) or {}
			msgs = d.get("messages") or d.get("historyMsgList") or []
			err = None if p.is_success(r) else f"code={r.get('code')}"
		except Exception as exc:  # noqa: BLE001
			msgs, err = [], repr(exc)

		results.append({
			"brand_name": s.get("brand_name"), "name": s.get("name"), "title": s.get("title"),
			"initiated_by": s.get("initiated_by"), "last_time": s.get("last_time"),
			"uid": gid, "messages": msgs, "error": err,
		})
		time.sleep(2.5)  # 控频，避免 code:37 风控
	return results


def render(rows: list[dict]) -> None:
	for c in rows:
		print("=" * 92)
		print(
			f"{c.get('brand_name')} | {c.get('name')}（{c.get('title')}）"
			f"  最近 {c.get('last_time')}  发起 {c.get('initiated_by')}  uid={c.get('uid')}"
		)
		print("-" * 92)
		if c.get("error"):
			print(f"  !! {c['error']}")
		for m in c.get("messages") or []:
			b = m.get("body") if isinstance(m.get("body"), dict) else {}
			frm = m.get("from") if isinstance(m.get("from"), dict) else {}
			who = "我" if str((frm or {}).get("uid", "")) != str(c.get("uid")) else "对方"
			ts = m.get("time")
			when = datetime.datetime.fromtimestamp(ts / 1000).strftime("%m-%d %H:%M") if ts else ""
			tname = MSG_TYPE.get(m.get("type"), f"其他({m.get('type')})")
			txt = (b or {}).get("text") or m.get("text") or ""
			if not txt:
				txt = (b or {}).get("name") or (b or {}).get("resumeName") or json.dumps(b or {}, ensure_ascii=False)
			print(f"  {when}  {who}  <{tname}>  {str(txt).replace(chr(10), ' / ')[:200]}")
		print()


def main() -> None:
	ap = argparse.ArgumentParser(description="按 uid 关联取回 BOSS 直聘完整对话流")
	ap.add_argument("--limit", type=int, default=12, help="最多查多少个会话")
	ap.add_argument("--days", type=int, default=30, help="沟通列表回看天数")
	ap.add_argument("--name", default=None, help="只查姓名包含该串的联系人")
	ap.add_argument("--json", action="store_true", help="输出 JSON")
	a = ap.parse_args()

	rows = fetch(a.limit, a.name, a.days)
	if a.json:
		print(json.dumps(rows, ensure_ascii=False, indent=1))
	else:
		render(rows)


if __name__ == "__main__":
	main()
