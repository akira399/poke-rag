"""UI 冒烟回归测试：用 Streamlit AppTest 真实渲染全部页签，确保无空白/异常。

需要后端（8765）在运行（模型设置页会读取 /api/settings）；后端不可达时跳过。
每个改动 UI 后都必须跑：pytest tests/test_ui_smoke.py
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("POKE_RAG_API", "http://127.0.0.1:8765")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _backend_up() -> bool:
    try:
        return requests.get(f"{API}/api/health", timeout=3).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _backend_up(), reason="后端未运行（先启动 scripts/serve.py）")


@pytest.fixture(scope="module")
def app():
    os.environ["STREAMLIT_TELEMETRY_OPTOUT"] = "true"
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(
        os.path.join(_ROOT, "scripts", "serve_ui.py"), default_timeout=120
    )
    at.run()
    return at


class TestAllTabsRender:
    """四个页签都必须渲染出各自的标志性控件（防止页签空白/索引错位）。"""

    def test_no_exception(self, app):
        assert not app.exception, f"页面渲染异常: {app.exception}"

    def test_tab_count(self, app):
        assert len(app.tabs) == 4, f"应有 4 个页签，实际 {len(app.tabs)}"

    def test_chat_tab(self, app):
        # 问答页：聊天输入框
        assert len(app.chat_input) >= 1, "问答页缺少聊天输入框"

    def test_search_tab(self, app):
        # 检索调试页：问题输入框 + 检索按钮
        labels = [t.label for t in app.text_input]
        assert any("检索" in lb for lb in labels), f"检索调试页缺少输入框: {labels}"

    def test_damage_tab(self, app):
        # 伤害计算器页：攻击方/防御方/招式三个下拉框
        labels = [s.label for s in app.selectbox]
        for need in ("攻击方", "防御方", "招式"):
            assert need in labels, f"伤害计算器缺少「{need}」下拉框: {labels}"

    def test_settings_tab(self, app):
        # 模型设置页：Base URL / 模型名 / API Key 三个输入框 + 保存按钮
        labels = [t.label for t in app.text_input]
        for need in ("Base URL", "模型名", "API Key"):
            assert need in labels, f"模型设置页缺少「{need}」输入框: {labels}"
        assert any("保存" in b.label for b in app.button), "模型设置页缺少保存按钮"
