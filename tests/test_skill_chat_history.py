"""skills/boss-agent-cli/scripts/chat_history.py 的单元测试。

该脚本随 WorkBuddy 技能分发，不属于 src 包，因此用 importlib 按路径加载。
覆盖两个此前会误导用户的点：

1. 解释器版本不匹配时，旧实现会把别的 Python 编译出的 site-packages 硬塞进
   sys.path，`import boss_agent_cli` 能过、却在更深一层炸成
   `ModuleNotFoundError: No module named 'greenlet._greenlet'`。
2. 「招呼卡片」（type=3 且 body.type==8）里 jobDesc 才是对方在招的岗位，
   旧实现直接 json.dumps 出一坨被截断的原始 JSON，把有用字段埋掉。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "boss-agent-cli" / "scripts" / "chat_history.py"


def _load():
	spec = importlib.util.spec_from_file_location("skill_chat_history", SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


mod = _load()


def _make_site(tmp_path: Path, tag: str) -> Path:
	site = tmp_path / tag / "site-packages"
	(site / "boss_agent_cli").mkdir(parents=True)
	return site


def test_matching_site_accepts_same_python_version(tmp_path):
	good = _make_site(tmp_path, mod._py_tag())
	assert mod._matching_site([str(good)]) == str(good)


def test_matching_site_rejects_other_python_version(tmp_path):
	"""不匹配的版本必须被拒，而不是塞进 sys.path 后炸在半路。"""
	other = _make_site(tmp_path, "python3.99")
	assert mod._matching_site([str(other)]) is None


def test_matching_site_prefers_matching_over_foreign(tmp_path):
	good = _make_site(tmp_path, mod._py_tag())
	other = _make_site(tmp_path, "python3.99")
	assert mod._matching_site([str(other), str(good)]) == str(good)


def test_matching_site_requires_package_present(tmp_path):
	"""版本对但没有 boss_agent_cli 的目录也不算可用。"""
	empty = tmp_path / mod._py_tag() / "site-packages"
	empty.mkdir(parents=True)
	assert mod._matching_site([str(empty)]) is None


def test_body_text_extracts_job_card():
	"""招呼卡片要还原成岗位信息，不能退化成原始 JSON。"""
	msg = {
		"type": 3,
		"body": {
			"type": 8,
			"templateId": 1,
			"jobDesc": {
				"title": "产品与增长负责人",
				"salary": "30-40K·13薪",
				"city": "北京 海淀区 白石桥",
			},
		},
	}
	text = mod.body_text(msg)
	assert "产品与增长负责人" in text
	assert "30-40K·13薪" in text
	assert "北京 海淀区 白石桥" in text
	assert "{" not in text


def test_body_text_plain_and_placeholder_cases():
	assert mod.body_text({"type": 1, "body": {"text": "好的"}}) == "好的"
	assert mod.body_text({"type": 3, "body": {"text": "在吗"}}) == "在吗"
	assert mod.body_text({"type": 3, "body": {}}) == "[打招呼]"
	assert mod.body_text({"type": 4, "body": {}}) == "[简历卡片]"
	assert mod.body_text({"type": 2, "body": {}}) == "[图片]"
	assert mod.body_text({"type": 9, "body": {"name": "呲牙"}}) == "[表情] 呲牙"


def test_body_text_tolerates_missing_body():
	assert mod.body_text({"type": 4}) == "[简历卡片]"
	assert mod.body_text({}) == "[其他(None)]"
