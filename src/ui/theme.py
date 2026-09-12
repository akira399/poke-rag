import base64
import os

# 修复：st.chat_input 聚焦会让 Streamlit 在加载时把内容滚到底部。
# 不做"拉回纠正"（视觉跳动、观感差），而是在页面加载后前 3.5 秒内
# 拦截程序触发的滚动（scrollIntoView + scrollTop 赋值），页面自然停在
# 顶端；3.5 秒后恢复原生行为，用户浏览与提问后的滚动完全不受影响。
_JS = """<script>(function(){
  var w = window.parent;
  if (w.__pokeScrollHooked) return;
  w.__pokeScrollHooked = true;
  var UNTIL = Date.now() + 3500;
  var proto = w.Element.prototype;
  var nativeSIV = proto.scrollIntoView;
  proto.scrollIntoView = function(){
    if (Date.now() < UNTIL) return;
    return nativeSIV.apply(this, arguments);
  };
  var bind = function(){
    var sc = w.document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (!sc) { setTimeout(bind, 250); return; }
    var d = Object.getOwnPropertyDescriptor(proto, "scrollTop");
    Object.defineProperty(sc, "scrollTop", {
      get: function(){ return d.get.call(sc); },
      set: function(v){ if (Date.now() >= UNTIL) d.set.call(sc, v); },
      configurable: true,
    });
  };
  bind();
  setTimeout(function(){
    proto.scrollIntoView = nativeSIV;
    var sc = w.document.querySelector('[data-testid="stAppScrollToBottomContainer"]');
    if (sc) delete sc.scrollTop;  // 移除实例拦截，恢复原型原生属性
  }, 3700);
})();</script>"""

# 界面样式：虚化背景 + 留白 + 卡片层级（用 CSS 注入，Streamlit 原生组件保持功能不变）
_CSS = """
<style>
/* ---------- 背景：官方素材合成的虚化图 + 深色蒙层保证可读性 ---------- */
[data-testid="stAppViewContainer"] {
    background-image:
        linear-gradient(rgba(9, 16, 34, 0.34), rgba(7, 12, 26, 0.52)),
        var(--poke-bg);
    background-size: cover, cover;
    background-position: center, center;
    background-attachment: fixed, fixed;
    background-repeat: no-repeat, no-repeat;
}
[data-testid="stHeader"] { background: transparent; }

/* ---------- 留白：整体呼吸感 ---------- */
.block-container {
    padding-top: 2.4rem !important;
    padding-bottom: 3rem !important;
    max-width: 1280px;
}
[data-testid="stVerticalBlock"] > div { gap: 0.65rem; }
h1 { margin-bottom: 0.2rem !important; letter-spacing: .5px; }
h2, h3 { margin-top: 1.1rem !important; margin-bottom: .5rem !important; }

/* ---------- 卡片感：对话气泡、展开项、输入框统一为半透明面板 ---------- */
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 14px;
    padding: 14px 18px;
    margin-bottom: 10px;
    backdrop-filter: blur(6px);
}
[data-testid="stExpander"] {
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    border-radius: 10px !important;
    background: rgba(255, 255, 255, 0.035);
    margin-bottom: 6px;
}
[data-testid="stStatusWidget"], div[data-testid="stStatus"] {
    border-radius: 12px !important;
}
[data-testid="stChatInput"] textarea { border-radius: 12px !important; }

/* 侧栏（示例列表）面板化 */
[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] {
    background: rgba(12, 20, 40, 0.55);
    backdrop-filter: blur(8px);
}

/* 按钮：细边框 + 悬停高亮，避免拥挤感 */
[data-testid="stBaseButton-secondary"] {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 9px !important;
    font-size: 13px !important;
    color: #DCE7FA !important;
    padding: 7px 12px !important;
    margin-bottom: 5px !important;
}
/* 按钮内层容器也要左对齐（Streamlit 按钮结构有嵌套） */
[data-testid="stBaseButton-secondary"] > div,
[data-testid="stBaseButton-secondary"] p {
    justify-content: flex-start !important;
    text-align: left !important;
    width: 100%;
    margin: 0 !important;
}

/* 输入框 / 文本域配色与背景协调 */
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea,
[data-testid="stChatInput"] textarea {
    background: rgba(12, 20, 40, 0.72) !important;
    color: #EAF0FA !important;
    border-radius: 10px !important;
}
[data-testid="stChatInput"] {
    background: rgba(12, 20, 40, 0.72) !important;
    border: 1px solid rgba(255, 255, 255, 0.14) !important;
    border-radius: 12px !important;
}
/* 下拉框 */
[data-baseweb="select"] > div {
    background: rgba(12, 20, 40, 0.72) !important;
    border-color: rgba(255, 255, 255, 0.14) !important;
}

/* 隐藏部署按钮与主菜单，保持界面干净 */
[data-testid="stToolbar"], [data-testid="stDecoration"],
#MainMenu, [data-testid="stStatusWidget"] { display: none !important; }

/* 页签下划线更明显 */
[data-testid="stTabs"] [aria-selected="true"] {
    color: #8FBBFF !important;
}
[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(90, 140, 240, 0.22) !important;
    border-color: rgba(120, 170, 255, 0.55) !important;
}

/* Tab 标题留白 */
[data-testid="stTabs"] button { font-size: 15px; padding: 8px 14px; }

/* 表格与代码块在深色背景上的可读性 */
table { background: rgba(0, 0, 0, 0.18); }
pre { background: rgba(0, 0, 0, 0.28) !important; }

/* 引用链接：更醒目的可点击样式 */
[data-testid="stMarkdownContainer"] a {
    color: #7fb3ff !important;
    text-decoration: none;
    border-bottom: 1px dotted #7fb3ff;
}
[data-testid="stMarkdownContainer"] a:hover { color: #a8ccff !important; }
</style>
"""


def inject(base_dir: str | None = None, bg_name: str = "background.png") -> None:
    """注入样式；背景图存在时以内嵌 base64 方式引用（保证路径稳定）。"""
    import streamlit as st

    css = _CSS
    if base_dir:
        path = os.path.join(base_dir, "assets", bg_name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            css = css.replace("var(--poke-bg)", f"url('data:image/png;base64,{b64}')")
    if "var(--poke-bg)" in css:
        css = css.replace("var(--poke-bg)", "linear-gradient(#0c1428, #0c1428)")
    st.markdown(css, unsafe_allow_html=True)
    # JS 需经组件 iframe 注入才能执行；height=0 不可见
    from streamlit.components.v1 import html as components_html

    components_html(_JS, height=0)
