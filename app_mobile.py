import streamlit as st
import re
from openai import OpenAI

# 导入你的模块（完全兼容原有代码，无需改动）
from prompts import (
    SIMPLE_TEXT_PROMPT, GB_FULL_PROMPT, WXYC_FULL_PROMPT, 
    PROMPT_LSYJ, PROMPT_ZXYJ, PROMPT_ZGSK, PROMPT_ZGFX, 
    PROMPT_WYYJ, PROMPT_SHXYJ
)

# ================= 1. 核心清洗函数（完全保留原有功能，不改动）=================
def clean_citation_number(text):
    if not text: return ""
    cleaned_lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line: continue 
        pattern = r"^[\s\[【\(]*\d+[\]】\)\.\,、]*\s*"
        clean_line = re.sub(pattern, "", line)
        cleaned_lines.append(clean_line)
    return "\n".join(cleaned_lines)

def extract_xml_result(text):
    if not text: return ""
    match = re.search(r'<result>(.*?)</result>', text, re.DOTALL)
    if match: content = match.group(1).strip()
    else: content = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
    content = content.replace('```xml', '').replace('```', '').strip()
    return content

# ================= 2. 重构：移动端界面渲染核心函数 =================
def render_mobile():
    
    # 🔴 样式完全保留原有，只修改字数统计逻辑
    st.markdown("""
    <style>
    /* ========================================================= */
    /* 【修改点1】注释掉了原来“彻底隐藏原生辅助栏”的代码，把原生实时字数统计释放出来 */
    /* ========================================================= */
    /* div[data-testid="stTextArea"] div:has(span) { display: none !important; } */
    /* div[data-testid="stTextArea"] > div > div:not(:first-child) { display: none !important; } */

    /* 全局基础规范：恢复自然滑动，不再锁死一屏 */
    [data-testid="stHeader"] {display: none !important;}
    [data-testid="stSidebar"] {display: none !important;}
    
    .stApp {
        background-color: #f8f7f4;
        font-family: "Source Han Serif CN", "Source Han Serif SC", "Noto Serif CJK SC", "Songti SC", "SimSun", serif;
        color: #2b2b2b;
        /* 删除了高度锁死和overflow隐藏，让页面恢复上下滑动 */
    }
    
    .block-container {
        padding-top: 0 !important; 
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 5rem !important; /* 【核心修改】：给底部留出充足的滑动空间，防止被悬浮按钮挡住内容 */
        max-width: 100% !important;
    }
    
    /* 全局间距规范：恢复正常的组件呼吸感 */
    [data-testid="stVerticalBlock"] {
        gap: 1rem !important; /* 【核心修改】：把 0.25rem 放宽到 1rem，解决拥挤和文字被切的问题 */
    }

    /* 顶部标题栏：极致压缩高度，减少留白 */
    .mobile-navbar {
        background-color: #ffffff;
        padding: 8px 0 8px 1rem !important;
        margin: 0 -1rem 1.7rem -1rem !important; /* 核心修改：把底部间距从0.4rem改成0.8rem */
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        text-align: left;
        border-bottom: 1px solid #f0f0f0;
    }
    .mobile-navbar .main-title {
        /* 引入与电脑端完全一致的字体序列 */
        font-family: 'Source Han Serif SC', 'SimSun', "Source Han Serif CN", "Songti SC", serif !important;
        margin: 0; font-weight: 700; font-size: 24px; 
        color: #8b0000 !important; /* 换成了电脑端的朱红色 */
        letter-spacing: 1px; line-height: 1.2;
    }
    .mobile-navbar .sub-title {
        font-size: 14px;
        color: #666666;
        font-weight: 300;
        margin-left: 4px;
    }

    /* Tab栏：压缩高度和间距 */
    div[data-testid="stTabs"] {
        margin-top: 0 !important;
        margin-bottom: 0.4rem !important; /* 底部间距压缩 */
        flex-shrink: 0;
    }
    div[data-baseweb="tab-list"] {
        gap: 0 !important;
        background-color: #ffffff;
        border-radius: 8px !important;
        padding: 3px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        margin-bottom: 0 !important;
    }
    button[data-baseweb="tab"] {
        font-family: "Source Han Serif CN", "Songti SC", serif !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        flex-grow: 1; 
        padding: 6px 0 !important;
        border-radius: 6px !important;
        color: #666666 !important;
        background-color: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #8b0000 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    div[data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* 折叠面板：压缩高度，减少留白 */
    [data-testid="stExpander"] {
        background-color: #ffffff !important;
        border-radius: 8px !important;
        border: 1px solid #e8e8e8 !important;
        box-shadow: none !important;
        margin-bottom: 0.4rem !important; /* 底部间距压缩 */
        overflow: hidden;
        flex-shrink: 0;
    }
    [data-testid="stExpander"] details summary {
        padding: 8px 10px !important;
        min-height: 0 !important;
        font-family: "Source Han Serif CN", serif;
        font-size: 15px;
        font-weight: 500;
        color: #333333;
    }
    [data-testid="stExpander"] details > div {
        padding: 10px 10px 8px 10px !important;
    }

    /* 国标子选项缩进：压缩高度 */
    /* ========================================================= */
    /* 子选项：胶囊按钮 (Segmented Control) 深度定制 */
    /* ========================================================= */
    /* 1. 整体容器：向右缩进对齐主选项文字，拉开间距 */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) {
        margin-left: 32px !important; /* 精准对齐上一级文字 */
        margin-top: -4px !important;
        margin-bottom: 16px !important;
    }

    /* 2. 胶囊底托：浅灰底色包裹 */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] {
        background-color: #f2f1ec !important; /* 宣纸灰底色 */
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 0 !important; /* 消除默认间距 */
        width: 100% !important;
    }

    /* 3. 隐藏原生红圈：杀掉自带的 Radio 圆形图标 */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label > div:first-child {
        display: none !important; 
    }

    /* 4. 胶囊选项基础样式 (未选中态) */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label {
        flex: 1 !important; /* 两个按钮平分 100% 宽度 */
        justify-content: center !important;
        padding: 8px 4px !important;
        margin: 0 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease;
    }
    
    /* 文字基础样式：字号缩小，体现从属层级 */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label p {
        font-size: 13px !important; 
        color: #888888 !important; /* 默认浅灰色 */
        font-weight: 500 !important;
        text-align: center !important;
    }

    /* 5. 选中状态：纯白滑块 + 阴影 + 朱红文字 */
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label:has(input:checked) {
        background-color: #ffffff !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important; /* 悬浮立体感 */
    }
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label:has(input:checked) p {
        color: #8b0000 !important; /* 激活态变红 */
        font-weight: 600 !important; /* 激活态加粗 */
    }

    /* 这里是你残留的多余 CSS 闭合括号问题，我帮你修正了 */
    
    [data-testid="stExpander"] > div > div > div[data-testid="stVerticalBlock"] > div:nth-child(2) div[role="radiogroup"] label {
        padding: 4px 0 !important;
    }

    /* 输入输出框：压缩高度，适配一屏 */
    div[data-testid="stTextArea"] {
        flex-shrink: 1 !important; /* 核心：让输入框自动适配剩余空间，不溢出 */
        margin-bottom: 0 !important;
    }
    div[data-testid="stTextArea"] > div {
        background-color: #ffffff !important;
        border-radius: 8px !important;
        border: 1px solid #e8e8e8 !important;
        padding: 4px !important;
        font-family: "Source Han Serif CN", serif;
    }
    div[data-testid="stTextArea"] > div:focus-within {
        border-color: #8b0000 !important;
        box-shadow: 0 0 0 2px rgba(139,0,0,0.08) !important;
    }
    div[data-testid="stTextArea"] textarea {
        font-family: "Source Han Serif CN", "Songti SC", serif !important;
        font-size: 16px !important;
        line-height: 1.6;
        color: #2b2b2b;
        min-height: unset !important; /* 取消默认最小高度 */
    }
    div[data-testid="stTextArea"] textarea::placeholder {
        font-family: "Source Han Serif CN", "Songti SC", serif !important;
        color: #999999 !important;
    }

    /* ========================================================= */
    /* 【修改点2】重写字数统计样式，完美接管原生实时统计 */
    /* ========================================================= */
    /* 1. 定位到底部的工具栏，保留你的压缩间距 */
    div[data-testid="stTextArea"] > div > div:last-child {
        justify-content: flex-end !important;
        margin-top: -2px !important;
        margin-bottom: 0.4rem !important;
    }
    
    /* 2. 核心魔法：把整个提示区（含英文和分隔点）字号变0、颜色透明，完全隐身 */
    div[data-testid="InputInstructions"] {
        font-size: 0 !important;
        color: transparent !important;
    }
    
    /* 3. 精准狙击：唯独把最后一个元素（即 35/500 字数部分）的字号和颜色恢复 */
    div[data-testid="InputInstructions"] > span:last-child {
        font-size: 12px !important; 
        color: #999999 !important;
        font-family: "Source Han Serif CN", serif !important;
        letter-spacing: 0.5px !important; /* 稍微加点间距更好看 */
    }

    /* 核心操作按钮：固定在屏幕底部，压缩高度 */
    /* ... 保持你代码里按钮往下原本的样式不变 ... */

    /* 核心操作按钮：固定在屏幕底部，压缩高度 */
    .fixed-bottom-btn-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #ffffff;
        padding: 8px 1rem !important; /* 上下内边距压缩 */
        box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
        z-index: 9999;
        flex-shrink: 0;
    }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #9a1010 0%, #8b0000 100%) !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 24px !important; /* 上下内边距压缩 */
        font-size: 18px !important;
        font-weight: 700 !important;
        font-family: "Source Han Serif CN", serif !important;
        width: 100% !important;
        margin: 0 !important;
        box-shadow: 0 4px 12px rgba(139, 0, 0, 0.18) !important;
        transition: all 0.15s ease;
    }
    div.stButton > button[kind="primary"]:active {
        transform: scale(0.98) !important;
        background: linear-gradient(135deg, #7a0c0c 0%, #6b0000 100%) !important;
        box-shadow: 0 2px 6px rgba(139, 0, 0, 0.25) !important;
    }

    /* 次要按钮：统一风格 */
    div.stButton > button {
        border-radius: 8px !important;
        font-family: "Source Han Serif CN", serif !important;
        font-weight: 500 !important;
    }

    /* Radio单选框：压缩间距 */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        flex-direction: column !important;
        gap: 0.6rem !important;
        align-items: flex-start !important;
    }
    div[data-testid="stRadio"] label p {
        font-family: "Source Han Serif CN", serif !important;
        font-size: 14px !important;
        color: #333333 !important;
        line-height: 1.4;
    }
    div[data-testid="stRadio"] input[type="radio"]:checked + label::before {
        background-color: #8b0000 !important;
        border-color: #8b0000 !important;
    }

    /* 输入框：规范样式 */
    div[data-testid="stTextInput"] > div {
        border-radius: 8px !important;
        font-family: "Source Han Serif CN", serif;
    }
    div[data-testid="stTextInput"] > div:focus-within {
        border-color: #8b0000 !important;
        box-shadow: 0 0 0 2px rgba(139,0,0,0.08) !important;
    }

    /* 隐藏Tab内容区的默认滚动条，确保不溢出 */
    div[data-testid="stTab"] > div[data-testid="stVerticalBlock"] {
        max-height: calc(100vh - 220px) !important; /* 核心：Tab内容区最大高度=屏幕高度-固定元素高度 */
        overflow-y: auto !important; /* 仅Tab内部内容过多时滚动，页面整体不滚动 */
        overflow-x: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ================= 3. 状态管理（API Key内置，无需用户输入）=================
    if "history_list" not in st.session_state:
        st.session_state.history_list = []
    if "temp_result" not in st.session_state:
        st.session_state.temp_result = ""
    # 【修改】API Key内置，从secrets读取，无需用户输入
    if "mobile_api_key" not in st.session_state:
        try:
            # 从Streamlit安全配置读取API Key
            st.session_state.mobile_api_key = st.secrets["MODELSCOPE_API_KEY"]
        except:
            # 兜底兼容，避免部署报错
            st.session_state.mobile_api_key = ""

    # ================= 4. 顶部标题栏（优化版左对齐）=================
    st.markdown("""
    <div class="mobile-navbar">
        <h2 class="main-title">典校大师<span class="sub-title">· 移动端</span></h2>
    </div>
    """, unsafe_allow_html=True)

    # ================= 5. 核心Tab栏 =================
    tab_work, tab_history, tab_help = st.tabs(["排版", "历史", "说明"])

            # ----------------- Tab 1: 排版工作台（核心功能页）-----------------
    with tab_work:
        # 1. 先初始化所有变量，避免未定义错误
        journal = ""
        is_disabled = False
        
        with st.expander("排版设置", expanded=False):
            # 排版规范主选项（扩充为 4 个，直接合并细分模式）
            mode = st.radio(
                "排版规范", 
                [
                    "通用国标 - 文末模式 (去除专著页码)", 
                    "通用国标 - 脚注模式 (保留引文页码)", 
                    "目标期刊格式（适配投稿要求）", 
                    "自定义规则（个性化格式要求）"
                ], 
                label_visibility="collapsed"
            )
            
            system_prompt = ""
            
            # 条件渲染：根据新合并的选项直接赋予相应的 Prompt
            
            if mode == "通用国标 - 文末模式 (去除专著页码)":
                # 你的 UI 没变，只把这里的一句话换成了长篇死命令
                task_adjust = """
                # Task Adjustment (User Override - Bibliography Mode):
                1. 用户选择了【文末参考文献】模式。
                
                2. 核心规则 - 第一类：**整体引用（强力去除页码）**
                   - 适用类型：普通图书 [M]、学位论文 [D]、汇编 [G]、标准 [S]、档案 [A]、舆图 [CM]、会议录整本 [C]。
                   - **关键指令**：即便你通过“上下文分析”补全了作者和出版社，**最终输出时也必须删除页码**！
                   - 错误示例：习近平. 报告[M]. 北京: 人民出版社, 2022: 43. (❌ 带有: 43)
                   - 正确示例：习近平. 报告[M]. 北京: 人民出版社, 2022. (✅ 无页码)
                   - 对于 (2) 这种同名补全的情况，补全元数据后，**不要**保留 ": 43"。

                3. 核心规则 - 第二类：**析出/连续出版物（必须保留页码）**
                   - 适用类型：期刊文章 [J]、报纸 [N]
                   - 操作：必须保留页码。

                4. 最终检查 (Final Check):
                   - 检查每一行，如果是 [M] 结尾（且不含 //），确保行尾是年份（如 2022.），而不是年份+页码（如 2022: 43.）。
                """
                system_prompt = GB_FULL_PROMPT + task_adjust
                
            elif mode == "通用国标 - 脚注模式 (保留引文页码)":
                # 你的 UI 没变，只替换 Prompt
                task_adjust = """
                # Task Adjustment (User Override):
                1. 用户选择了【页下注/脚注】模式。
                2. 规则：**必须保留**来源中的具体引文页码。
                3. 适用范围：包括普通图书[M]、学位论文[D]、报告[R]、汇编[G]、标准[S]、会议录[C]、档案[A]、舆图[CM]等所有专著性质文献。
                4. 【重要补全指令】：如果原始文本中**完全缺失页码信息**，请在输出结果的末尾强制加上 **[缺: 页码]** 字样，以提示用户补录。不要编造页码。
                """
                system_prompt = GB_FULL_PROMPT + task_adjust
                
            elif mode == "目标期刊格式（适配投稿要求）":
                # 你写的下拉框和禁用逻辑，一字不动！
                journal = st.selectbox(
                    "选择目标期刊", 
                    ["《文学遗产》", "更多期刊开发中"], 
                    label_visibility="collapsed"
                )
                system_prompt = WXYC_FULL_PROMPT if "文学遗产" in journal else SIMPLE_TEXT_PROMPT
                
                # 【核心逻辑】只有选了「更多期刊开发中」才禁用
                if journal == "更多期刊开发中":
                    is_disabled = True
            
            else: # 自定义规则
                custom_req = st.text_input(
                    "✍️ 特殊要求", 
                    placeholder="如：去除作者朝代", 
                    label_visibility="collapsed"
                )
                
                # --- 🌟 核心修改开始 🌟 ---
                custom_task = f"""
# Task Adjustment (User Override - 最高优先级):
1. 基础规范：请首先遵循上方提供的 GB/T 7714-2015 排版格式（作为底座）。
2. 个性化定制：用户提出了以下强制性特殊要求：
   【 {custom_req} 】
3. 冲突解决：如果在排版过程中，用户的【特殊要求】与前文的【核心原则】或【标准输出模板】发生冲突，**必须无条件以用户的【特殊要求】为准**。
"""
                system_prompt = GB_FULL_PROMPT + custom_task
                # --- 🌟 核心修改结束 🌟 ---


        # ================= 【核心修改】动态生成输入框提示文字 =================
        if mode == "目标期刊格式（适配投稿要求）" and journal == "《文学遗产》":
            # 选中《文学遗产》时，显示你给的专属提示
            input_placeholder = """请输入内容...

注意：《文学遗产》体例要求中，同一文献再次引证可省略作者、出版单位与年份，作者与著作间不加标点，间接引用可使用“参见”。

为统一格式规范，本工具对相同文献不做省略处理，不自动添加“参见”相关表述。"""
        else:
            # 其他模式，显示原来的通用提示
            input_placeholder = """快捷用法：直接粘贴平台整段文字，或输入文献关键信息，信息越全，结果越准确！

示例：
输入：李泽厚美的历程广西师大出版社2000年
输出：李泽厚. 美的历程[M]. 桂林: 广西师范大学出版社, 2000.

通用国标默认不标注朝代/国籍，如需调整可使用「自定义规则」模式。"""

        # 3. 核心输入区（动态禁用+动态提示文字）
        user_input = st.text_area(
            "输入文献", 
            height=320,
            placeholder=input_placeholder, # 【核心修改】替换成动态的提示文字
            label_visibility="collapsed",
            max_chars=500,
            disabled=is_disabled
        )

        # 5. 核心操作按钮：固定在屏幕底部
        st.markdown('<div class="fixed-bottom-btn-container">', unsafe_allow_html=True)
        if st.button("立即排版", type="primary", use_container_width=True, disabled=is_disabled):
            if not user_input.strip():
                st.warning("⚠️ 请输入待排版的文献内容")
            else:
                try:
                    with st.spinner("典校处理中..."):
                        client = OpenAI(api_key=st.session_state.mobile_api_key, base_url="https://api-inference.modelscope.cn/v1")
                        response = client.chat.completions.create(
                            model="ZhipuAI/GLM-5",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_input}
                            ],
                            temperature=0.3, 
                            stream=False,
                            extra_body={"enable_thinking": False}  # <--- 新增这一行（注意上一行的 stream=False 后面要确保有个逗号）
                        )
                        raw_result = response.choices[0].message.content.strip()
                        cleaned_result = clean_citation_number(extract_xml_result(raw_result))
                        st.session_state.temp_result = cleaned_result
                        st.success("✅ 典校完成！")
                except Exception as e:
                    st.error(f"出错啦: {str(e)}")
        st.markdown('</div>', unsafe_allow_html=True)

        # 6. 结果输出区：按需显示
        if st.session_state.temp_result:
            st.markdown("<div style='font-size:15px; color: #333; font-weight: 600; font-family: Source Han Serif CN, serif; margin-bottom: 4px;'>排版结果：</div>", unsafe_allow_html=True)
            final_text = st.text_area("输出", value=st.session_state.temp_result, height=160, label_visibility="collapsed")
            
            # 底部操作双按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 存入历史", use_container_width=True):
                    new_lines = [line.strip() for line in final_text.split('\n') if line.strip()]
                    st.session_state.history_list.extend(new_lines)
                    st.toast("已成功存入历史记录！", icon="🎉")
            with col2:
                if st.button("🗑️ 清除结果", use_container_width=True):
                    st.session_state.temp_result = ""
                    st.rerun()
                    
                    # ----------------- Tab 2: 历史记录 -----------------
    with tab_history:
        if not st.session_state.history_list:
            st.info("📭 暂无历史记录，快去排版页生成并保存吧！")
        else:
            full_history = "\n".join(st.session_state.history_list)
            st.markdown(f"<div style='font-size:14px; color:#666; font-family: Source Han Serif CN, serif;'>共积累 {len(st.session_state.history_list)} 条文献</div>", unsafe_allow_html=True)
            st.text_area("历史汇总", value=full_history, height=380, label_visibility="collapsed")
            
            col_export, col_clear = st.columns(2)
            with col_export:
                st.download_button(
                    label="📥 导出TXT",
                    data=full_history,
                    file_name="典校大师_参考文献汇总.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with col_clear:
                if st.button("🗑️ 清空历史", use_container_width=True):
                    st.session_state.history_list = []
                    st.rerun()

    # ----------------- Tab 3: 说明与设置（已删除API配置模块）-----------------
    with tab_help:
                # 模块1：💡 使用建议（默认收起，有需求的用户再点开）
        with st.expander("💡 使用说明", expanded=False):
            st.markdown("""
            典校大师支持**手机端/电脑端自动适配**，两端功能完全一致，仅界面针对设备做了专属优化：
            - 📱 **手机端（当前）**：适合临时排版、快速修改，随时随地处理文献
            - 💻 **电脑端**：适合批量处理大量文献、长文本排版，大屏操作更高效
            
            **切换方式**：直接在电脑浏览器打开同一网址，系统会自动切换为桌面端界面，无需额外下载安装。
            """)

               # 模块2：📖 工具简介
        with st.expander("📖 工具简介"):
            st.markdown("""
            **CanonMaster · 典校大师**
            专为**人文社科领域**学术群体打造，是一款基于智谱GLM-5大语言模型开发的**智能参考文献排版工具**。
            
            核心能力：一键将格式混乱、缺项漏项的参考文献，转换为符合学术标准的规范格式。
            -  **优化正则替换**：依托大模型语义理解能力，实现深度智能处理
            -  **智能规范排版**：自动识别作者、书名、卷次、出版地、年份等核心要素，按目标规范重组，既保格式合规，又保信息完整。
            """)

                # 模块3：📜 命名由来
        with st.expander("📜 命名由来"):
            st.markdown("""
            「典校」一职，源远有自。西汉成帝时，**刘向、刘歆父子**领校秘书，开系统性整理国家典籍之先河，后世遂以「典校」指称典籍订正、规范之业。
            
            本工具以「CanonMaster · 典校大师」为名，正承此意：
            - **典**：奉学界通例为圭臬，立文章之规矩
            - **校**：借现代科技补罅漏，正体例之讹误
            
            我们希望以现代技术，效古人校书之功，让每一处引用**皆合规**，每一篇文献**尽合范**。
            """)

               # 模块4：🛠️ 功能详解
        with st.expander("🛠️ 功能详解"):
            st.markdown("""
            **◆ 通用国标（GB/T 7714-2015）**：
            学术界通用著录基准，适配硕博论文、普通期刊论文等场景，按引用位置分为两类：
            - 文末模式：自动去除专著页码（适配参考文献列表）
            - 脚注模式：保留引文页码（适配正文页底注释）
            
            **◆ 目标期刊格式**：
            内置《文学遗产》等刊物排版规范，选择目标刊物即可一键适配投稿格式。
            
            **◆ 自定义规则**：
            满足特殊格式需求，先将文献转为通用国标格式，再按你的个性化要求完成定制化调整。
            """)

                      # 模块5：❓ 常见问题
        with st.expander("❓ 常见问题"):
            st.markdown("""
            **Q：典校大师采用哪一版GB/T 7714国标？**
            **A**：目前默认采用**学界通用的GB/T 7714-2015版**。

            **Q：可以补全缺漏的文献信息吗？**
            **A**：有智能补全功能，但对于无法100%确认的信息，会留空或标记「[缺]」。
            但请注意： 典校大师毕竟不是人类，请务必**人工核对信息**。

            **Q：专业期刊里没有我要的刊物怎么办？**
            **A**：工具处于**v1.0阶段**，更多刊物体例正在开发中。
            建议流程：先用**通用国标清洗**，再通过**自定义规则补充**刊物的特殊要求。

            **Q：刷新页面后历史记录还在吗？**
            **A**：没有。本工具**不连接任何数据库**。
            所有数据仅存于你当前的浏览器内存中，刷新/关闭标签页后**数据即刻销毁**。
            请养成「排版完成，及时导出」的习惯。
            """)
           

                      # 模块6：🤝 交流共建
        with st.expander("🤝 交流共建"):
            st.markdown("""
            **致每一位使用者：**
            
            CanonMaster·典校大师，是一款由个人开发维护的开源学术工具。
            
            开发初衷，是解决自己和身边同学在学术写作中遇到的文献排版痛点，希望能帮同样为此耗费精力的你，节省哪怕一分钟的时间。
            
            工具仍在成长迭代，欢迎通过以下渠道反馈交流：
            
            🐧 **QQ交流群**
            群号：1083502445
            可直接反馈Bug、功能许愿，也可参与内测、学术交流，这也是是最快找到我的渠道。
            
            💻 **GitHub开源社区**
            欢迎访问项目主页，在Issues区提交专业的Bug报告/功能建议，也可查看源码、提交PR共同完善工具。
            🌟 你的每一个Star，都是我持续迭代的最大动力！
            """)
            st.link_button("🔗 前往GitHub项目主页", "https://github.com/a2463712381-ui/CanonMaster", use_container_width=True)
