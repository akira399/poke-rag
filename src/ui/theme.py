import base64
import os

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

/* ---------- 对话区：回答是主视觉，输入是轻量 Composer ---------- */
.chat-kicker {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 1.25rem 0 .55rem;
    color: rgba(234, 240, 250, .62);
    font-size: 12px;
    letter-spacing: .14em;
    text-transform: uppercase;
}
.chat-kicker span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #6ea8ff;
    box-shadow: 0 0 12px rgba(110, 168, 255, .85);
}
.chat-empty {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: .2rem 0 1.1rem;
    padding: 18px 20px;
    border: 1px solid rgba(255, 255, 255, .09);
    border-radius: 16px;
    background: linear-gradient(110deg, rgba(91, 156, 255, .10), rgba(255, 255, 255, .035));
    color: rgba(234, 240, 250, .78);
}
.chat-empty-icon {
    display: grid;
    place-items: center;
    flex: 0 0 34px;
    width: 34px;
    height: 34px;
    border: 1px solid rgba(125, 178, 255, .44);
    border-radius: 11px;
    color: #9bc5ff;
    font-size: 20px;
}
.chat-empty strong { color: #eaf0fa; font-size: 14px; }
.chat-empty p { margin: 3px 0 0; color: rgba(234, 240, 250, .56); font-size: 12px; }

[data-testid="stChatMessage"] {
    display: flex;
    width: fit-content;
    max-width: 92%;
    background: rgba(255, 255, 255, 0.065);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 16px 6px 16px 16px;
    padding: 15px 18px;
    margin: 0 0 12px;
    backdrop-filter: blur(9px);
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
    line-height: 1.72;
    margin-bottom: .55rem;
}
/* AI 回答：宽阅读卡片 + 左侧状态线 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    display: flex;
    width: 100%;
    max-width: 100%;
    background: linear-gradient(105deg, rgba(19, 36, 68, .78), rgba(255, 255, 255, .055));
    border-left: 3px solid rgba(105, 170, 255, .92);
    border-radius: 6px 16px 16px 6px;
    box-shadow: 0 10px 28px rgba(3, 9, 24, .18);
}
/* 用户提问：窄气泡靠右，降低饱和度，避免抢过回答 */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    width: fit-content;
    max-width: 78%;
    margin-left: auto;
    background: rgba(67, 119, 202, .28);
    border: 1px solid rgba(132, 183, 255, .36);
    border-radius: 16px 16px 5px 16px;
    box-shadow: none;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] p {
    margin-bottom: 0;
    line-height: 1.55;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid^="stChatMessageAvatar"] {
    background: rgba(91, 156, 255, .32);
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
[data-baseweb="textarea"] textarea {
    background: rgba(12, 20, 40, 0.72) !important;
    color: #EAF0FA !important;
    border-radius: 10px !important;
}

/* 发送区域：只保留轻量操作感，不与消息内容争夺焦点 */
form[data-testid="stForm"] {
    margin: 1rem 0 1.35rem;
    padding: 8px 10px 8px 14px;
    border: 1px solid rgba(134, 183, 255, .22);
    border-radius: 17px;
    background: rgba(8, 18, 39, .64);
    box-shadow: 0 12px 30px rgba(3, 8, 22, .24);
}
form[data-testid="stForm"] [data-baseweb="input"] {
    border: 0 !important;
    box-shadow: none !important;
    background: transparent !important;
}
form[data-testid="stForm"] [data-baseweb="input"] input {
    min-height: 32px;
    background: transparent !important;
}
    form[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
    form [data-testid="stBaseButton-primaryFormSubmit"] {
    width: 38px !important;
    min-width: 38px !important;
    max-width: 38px !important;
    height: 38px !important;
    padding: 0 !important;
    border: 1px solid rgba(148, 195, 255, .7) !important;
    border-radius: 50% !important;
    color: #eaf3ff !important;
    background: rgba(75, 139, 235, .8) !important;
    box-shadow: 0 3px 12px rgba(55, 123, 227, .25);
    font-size: 18px !important;
    line-height: 1 !important;
}
    form[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover,
    form [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: rgba(96, 158, 248, .95) !important;
    transform: translateY(-1px);
}
    form[data-testid="stForm"] [data-testid="stFormSubmitButton"] p,
    form [data-testid="stBaseButton-primaryFormSubmit"] p {
    display: block !important;
    margin: 0 !important;
    line-height: 1 !important;
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

/* 窄屏：减少背景干扰，给对话文字更多可读宽度 */
@media (max-width: 600px) {
    .block-container {
        padding: 1.15rem .8rem 2rem !important;
    }
    h2 { font-size: 1.55rem !important; line-height: 1.2 !important; }
    [data-testid="stChatMessage"] {
        padding: 12px 13px;
        margin-bottom: 9px;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        max-width: 86%;
    }
    form[data-testid="stForm"] {
        margin-top: .85rem;
        padding: 6px 7px 6px 11px;
    }
    form[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
    form [data-testid="stBaseButton-primaryFormSubmit"] {
        width: 36px !important;
        min-width: 36px !important;
        max-width: 36px !important;
        height: 36px !important;
    }
    .chat-empty { padding: 14px; gap: 10px; }
    .chat-empty p { line-height: 1.45; }
}
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
