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


def test_default_free_mode_no_config_needed(app):
    """默认免配置：站点未配共享 Key 时也不应崩溃，且给出引导而非强制拦截。"""
    assert not app.exception
    # 未配置自己的 Key 时，页面不应出现"必须填 Key 才能用"的阻塞式警告
    # （免费模式不可用时才提示，这里断言页面本身可用）
    assert any("API Key" in (t.label or "") for t in app.text_input)


def test_examples_present(app):
    texts = [b.label for b in app.button]
    assert "快龙怕什么属性？" in texts
    assert "保存到本会话" in texts


def test_chat_composer_structure(app):
    """聊天 Composer 是普通表单，避免 st.chat_input 的自动滚动副作用。"""
    assert any(t.label == "你的问题" for t in app.text_input)
    assert any(b.label == "↑" and b.key == "FormSubmitter:ask-↑" for b in app.button)
    assert len(app.chat_input) == 0


def test_clear_key_returns_to_free_mode(app):
    """自备 Key 模式应提供「清空（回到免费）」入口。"""
    assert any("清空" in (b.label or "") for b in app.button)
    assert any("可选" in (e.label or "") or "自己的 Key" in (e.label or "")
               for e in app.expander)


def test_secondary_sections_collapsed(app):
    """除配置区可能自动展开外，示例与检索调试默认收起。"""
    labels = [e.label for e in app.expander]
    assert any("模型配置" in l for l in labels)
    assert "💡 常见问题实例（点击展开）" in labels
    assert "🔍 检索调试" in labels
    assert len(labels) == 3


def test_chat_empty_state(app):
    md = "\n".join(m.value for m in app.markdown)
    assert "对话" in md
    assert "对战终端已就绪" in md


def test_no_raw_html_tags_in_rendered_output(app):
    """提示语不得以内联 HTML 输出（Streamlit 会转义成原始标签文本）。

    历史 bug：<sub>🌐 免费模式…</sub> 被原样显示成标签文字。
    """
    for m in app.markdown:
        assert "<sub>" not in m.value, f"markdown 出现原始 HTML: {m.value[:80]}"
        assert "</sub>" not in m.value
    for c in app.caption:
        assert "<sub>" not in c.value
