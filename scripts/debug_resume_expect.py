#!/usr/bin/env python3
"""复现并诊断 `boss me --section expect` 的 code:19 问题。

背景：求职期望接口 `/wapi/zpgeek/resume/expect/query.json` 的 stoken 在 CDP httpx
模式下注入不到 GET 参数，CLI 会报 code:19「参数值错误」。绕过 CLI 直接调平台层，
可以确定是鉴权链路的问题还是接口本身变了，便于定位。

安全：只打印 token 的**键名**与 stoken 是否存在，不打印任何凭据原文。

前置：Chrome 已带 `--remote-debugging-port` 启动且已登录 BOSS。

用法（在仓库根目录执行）：
    python3 scripts/debug_resume_expect.py
"""
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from boss_agent_cli.api.client import BossClient  # noqa: E402
from boss_agent_cli.auth.manager import AuthManager  # noqa: E402


def main() -> None:
	auth = AuthManager(os.path.expanduser("~/.boss-agent"), platform="zhipin")
	token = auth.get_token()
	print("Token keys:", list(token.keys()))
	print("Stoken present:", bool(token.get("stoken")))
	print("Cookies count:", len(token.get("cookies", {})))

	cdp_url = os.environ.get("BOSS_CDP_URL", "http://localhost:9222")
	client = BossClient(auth, cdp_url=cdp_url)
	try:
		resp = client.resume_expect()
		print("Response:", json.dumps(resp, ensure_ascii=False)[:2000])
	except Exception as exc:
		print("Error:", type(exc).__name__, exc)
	finally:
		client.close()


if __name__ == "__main__":
	main()
