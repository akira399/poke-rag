"""云端单进程版（app_render.py）UI 冒烟：AppTest 真实渲染，无后端依赖。

断言移动端可用的关键点：配置区在主页面（不在侧边栏）、未配置时警告可见、
示例按钮存在。
"""
import os
import sys

import pytest
from streamlit.testing.v1 import AppTest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(_ROOT, "app_render.py")


@pytest.fixture(scope="module")
def app():
    os.environ["STREAMLIT_TELEMETRY_OPTOUT"] = "true"
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    yield at


def test_no_exception(app):
    assert not app.exception


def test_config_in_main_area_not_sidebar(app):
    """配置必须能在主区域找到（手机端侧边栏折叠不可见）。"""
    texts = "\n".join(getattr(b, "label", "") or "" for b in app.expander)
    assert "模型配置" in texts
    keys = [t.label for t in app.text_input]
    assert any("API Key" in k for k in keys)


def test_first_run_warning(app):
    assert any("模型配置" in w.value for w in app.warning)


def test_examples_present(app):
    texts = [b.label for b in app.button]
    assert "快龙怕什么属性？" in texts
    assert "保存到本会话" in texts


def test_chat_composer_structure(app):
    """聊天 Composer 是普通表单，避免 st.chat_input 的自动滚动副作用。"""
    assert any(t.label == "你的问题" for t in app.text_input)
    assert any(b.label == "↑" and b.key == "FormSubmitter:ask-↑" for b in app.button)
    assert len(app.chat_input) == 0


def test_secondary_sections_collapsed(app):
    labels = [e.label for e in app.expander]
    assert labels == [
        "⚙️ 模型配置 · 点此展开填入 API Key",
        "💡 常见问题实例（点击展开）",
        "🔍 检索调试",
    ]


def test_chat_empty_state(app):
    assert "对话" in "\n".join(m.value for m in app.markdown)
    assert "对战终端已就绪" in "\n".join(m.value for m in app.markdown)
