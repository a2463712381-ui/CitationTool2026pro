import streamlit as st
import time
from openai import OpenAI
import os 
import re  # <--- 【新增1】引入正则工具包

# 导入你的模块
from styles import apply_custom_style
from prompts import (
    SIMPLE_TEXT_PROMPT, GB_FULL_PROMPT, WXYC_FULL_PROMPT, 
    PROMPT_LSYJ, PROMPT_ZXYJ, PROMPT_ZGSK, PROMPT_ZGFX, 
    PROMPT_WYYJ, PROMPT_SHXYJ
)

# ================= 【新增2】定义全局清洗函数 =================
def clean_citation_number(text):
    """
    强力清洗函数：专门去除行首的 [1], 1., (1), 【1】 等序号
    适用于所有模式的输出结果
    """
    if not text:
        return ""
    
    cleaned_lines = []
    # 按行拆分，逐行清洗
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue # 跳过空行
        
        # 正则表达式解释：
        # ^          : 匹配行首
        # [\s\[【\(]* : 匹配开头可能有的空格、[、【、(
        # \d+        : 匹配数字
        # [\]】\)\.\,、]* : 匹配结尾的 ]、】、)、. 、, 、、
        # \s* : 匹配序号后的空格
        pattern = r"^[\s\[【\(]*\d+[\]】\)\.\,、]*\s*"
        
        # 将匹配到的序号替换为空字符串
        clean_line = re.sub(pattern, "", line)
        cleaned_lines.append(clean_line)
    
    # 重新组合成文本
    return "\n".join(cleaned_lines)
# =======================================================

# ================= 【新增3】XML 标签清洗函数 (必须加在这里！) =================
def extract_xml_result(text):
    """
    专门提取 <result> 标签内的内容，过滤掉 <thinking>
    """
    if not text:
        return ""
    
    # 1. 尝试提取 <result>...</result> 中间的内容
    # re.DOTALL 让 . 可以匹配换行符
    match = re.search(r'<result>(.*?)</result>', text, re.DOTALL)
    
    if match:
        content = match.group(1).strip()
    else:
        # 2. 兜底：如果没找到 result 标签，就硬行删除 thinking 标签
        content = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
    
    # 3. 去掉可能存在的 markdown 代码块符号
    content = content.replace('```xml', '').replace('```', '').strip()
    
    return content
# =======================================================

# ================= 1. 页面配置 (已注释，留给主入口) =================
# st.set_page_config(
#     page_title="CanonMaster - 典校大师",
#     page_icon="📜",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

def render_desktop():
    # 应用样式
    apply_custom_style()

    # 🔴 全局 CSS：宣纸白背景 + 侧边栏朱红界栏
    st.markdown("""
    <style>
        /* 全局背景：宣纸白 (#f9f9f9) */
        .stApp {
            background-color: #f9f9f9;
        }
        
        /* 侧边栏：稍微深一点的米灰色 + 朱红界栏 */
        section[data-testid="stSidebar"] {
            background-color: #f2f2f2;
            /* ✨ 重点修改：加了 !important 强制显示红色 */
            border-right: 2px solid #8b0000 !important;
        }

        /* 顶部Header透明 */
        [data-testid="stHeader"] {
            background-color: rgba(0,0,0,0);
        }
        
        
        /* 强制全局字体优化：兼容性更强的宋体列表 */
        body {
            font-family: "Source Han Serif CN", "Source Han Serif SC", "Noto Serif CJK SC", 
                         "Songti SC", "SimSun", "STSong", "AR PL New Sung", "华文宋体", "宋体", serif;
        }
    </style>
    """, unsafe_allow_html=True)

    # ================= 2. 全局状态管理 =================
    if "history_list" not in st.session_state:
        st.session_state.history_list = []
    if "temp_result" not in st.session_state:
        st.session_state.temp_result = ""
    if "last_input" not in st.session_state:
        st.session_state.last_input = ""

    # ✨【新增】用于记录上一次“确认入库”时的完整文本，防止手抖，但允许正常添加
    if "last_archived_text" not in st.session_state:
        st.session_state.last_archived_text = ""

    # ================= 3. 侧边栏 (导航 + 设置) =================
    with st.sidebar:
        st.markdown("### 🧭 功能导航")
        
        # 🔴 修改点 1：更新列表内的文字
        page = st.radio(
            "导航", 
            ["🚀 文献排版", "📂 历史记录", "📖 使用说明", "🤝 交流共建"], 
            label_visibility="collapsed"
        )
        
        
        # 🌟【修复版】兼容性更强的 Key 读取逻辑 🌟
        api_key = "" 

        try:
            # 只要读到了 Key，就静默赋值，什么都不显示
            if "MODELSCOPE_API_KEY" in st.secrets:
                api_key = st.secrets["MODELSCOPE_API_KEY"]
                # 这里什么都不用写，留白就是最好的设计
            else:
                raise ValueError("Key missing")
            
        except Exception:
            # 💡 这里是“兜底方案”：
            # 如果找不到 secrets.toml 文件，或者文件里没 Key，
            # 就会显示这个输入框，让你可以手动输入，保证软件能用！
            st.header("⚙️ 设置")
            # st.warning("⚠️ 未检测到本地配置，请手动输入") # 这行可以注释掉，清爽一点
            api_key = st.text_input("ModelScope API Key", type="password", help="未检测到 .streamlit/secrets.toml，请手动输入") 

    # ================= 4. 页面 A：排版工作台 =================
    if page == "🚀 文献排版":
        # 标题区：卷轴 + 居中
        st.markdown("""
        <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 20px;">
            <div style="font-size: 40px; margin-right: 15px;">📜</div>
            <div style="text-align: center;">
                <div style="font-size: 32px; font-weight: bold; color: #1f2d3d; line-height: 1.2; font-family: 'Source Han Serif SC', 'SimSun', serif;">
                    CanonMaster <span style="font-size: 28px; color: #8b0000;">典校大师</span>
                </div>
                <div style="font-size: 14px; color: #666; font-weight: 400; letter-spacing: 1px;">
                    为文献排版而生 · 文献规范智能工具
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- 顶部设置区 ---
        with st.container():
            col_list = st.columns([1.5, 4, 1.5, 4])

            
            with col_list[0]:
                st.markdown('<p class="radio-label">模式：</p>', unsafe_allow_html=True)
            with col_list[1]:
                mode = st.radio(
                    "模式选择", 
                    ["通用国标", "专业期刊", "自定义规则"], 
                    horizontal=True, 
                    label_visibility="collapsed",
                    key="mode_radio"
                )

            system_prompt = ""
            placeholder_text = "请输入..."
            
            if mode == "通用国标":
                with col_list[2]:
                    st.markdown('<p class="radio-label">选项：</p>', unsafe_allow_html=True)
                with col_list[3]:
                    gb_type = st.radio(
                        "细节微调", 
                        ["文末模式", "脚注模式"], 
                        horizontal=True, 
                        label_visibility="collapsed"
                    )
                
                # ----------------- 🌟 修改开始 🌟 -----------------
                # 根据用户选择的模式，生成更详细的 Prompt 指令
                if "脚注模式" in gb_type:
                    # 【脚注模式】：要求保留页码，且明确了所有“专著”类型，并要求补全缺失标记
                    task_adjust = """
                    # Task Adjustment (User Override):
                    1. 用户选择了【页下注/脚注】模式。
                    2. 规则：**必须保留**来源中的具体引文页码。
                    3. 适用范围：包括普通图书[M]、学位论文[D]、报告[R]、汇编[G]、标准[S]、会议录[C]、档案[A]、舆图[CM]等所有专著性质文献。
                    4. 【重要补全指令】：如果原始文本中**完全缺失页码信息**，请在输出结果的末尾强制加上 **[缺: 页码]** 字样，以提示用户补录。不要编造页码。
                    """
                else:
                    # 【文末模式】：区分“整体”与“析出”
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
                # ----------------- 🌟 修改结束 🌟 -----------------
                # 优化后的 placeholder 文案：更直观、更强调 AI 的补全能力
                placeholder_text = """快捷用法：直接粘贴知网 / 豆瓣等平台的整段文字，或输入关键信息。信息越全，结果越准确！

示例：
输入：李泽厚美的历程广西师大出版社2000年
输出：李泽厚. 美的历程[M]. 桂林: 广西师范大学出版社, 2000.

注：通用国标默认不标注朝代、国籍，外国作者名字不写全称，本工具按实际使用需求统一补齐；如需严格按国标执行，可使用「自定义规则」模式调整。"""
            
            # -------------------------------------------------------
            # 分支 2：专业期刊模式
            # -------------------------------------------------------
            elif mode == "专业期刊":
                with col_list[2]:
                    st.markdown('<p class="radio-label">选择：</p>', unsafe_allow_html=True)
                with col_list[3]:
                    # 定义期刊列表（带开发中标记）
                    journal_options = [
                        "《文学遗产》", 
                        "《历史研究》 (开发中)", 
                        "《哲学研究》 (开发中)", 
                        "《中国社会科学》 (开发中)", 
                        "《中国法学》 (开发中)", 
                        "《文艺研究》 (开发中)", 
                        "《社会学研究》 (开发中)"
                    ]
                    
                    selected_display = st.selectbox(
                        "选择目标期刊", 
                        journal_options, 
                        label_visibility="collapsed"
                    )
                
                # --- 核心判断逻辑 ---
                if "开发中" in selected_display:
                    is_journal_disabled = True  # ⛔ 标记为禁用
                    target_journal = selected_display.split(" ")[0]
                    system_prompt = "" 
                    placeholder_text = f"🚫 {target_journal} 体例规则正在适配中，暂不开放使用。请先使用「通用国标」模式，或切换至「《文学遗产》」体验。"
                    
                    st.warning(f"🚧 {target_journal} 暂未上线，排版按钮已锁定。", icon="🔒")
                
                else:
                    is_journal_disabled = False # ✅ 标记为可用
                    target_journal = selected_display
                    
                    # 正常的 Prompt 映射
                    journal_map = {
                        "《文学遗产》": WXYC_FULL_PROMPT, 
                        "《历史研究》": PROMPT_LSYJ, 
                        "《哲学研究》": PROMPT_ZXYJ,
                        "《中国社会科学》": PROMPT_ZGSK, 
                        "《中国法学》": PROMPT_ZGFX, 
                        "《文艺研究》": PROMPT_WYYJ, 
                        "《社会学研究》": PROMPT_SHXYJ
                    }
                    
                    system_prompt = journal_map.get(target_journal, SIMPLE_TEXT_PROMPT)
                    
                    # 正常的 Placeholder 提示
                    if target_journal == "《文学遗产》":
                        placeholder_text = """请输入内容...

注意：《文学遗产》体例要求中，同一文献再次引证可省略作者、出版单位与年份，作者与著作间不加标点，间接引用可使用 “参见”。

为统一格式规范，本工具对相同文献不做省略处理，不自动添加 “参见” 相关表述。"""
                    else:
                        placeholder_text = f"请输入... (AI 将严格遵循{target_journal}体例进行清洗)"

            # -------------------------------------------------------
            # 分支 3：自定义规则模式 (这是最外层的 else，对应 mode 的判断)
            # -------------------------------------------------------
            # -------------------------------------------------------
            # 分支 3：自定义规则模式 (这是最外层的 else，对应 mode 的判断)
            # -------------------------------------------------------
            else: # 即 mode == "自定义规则"
                # 务必在这里也标记为可用，否则切换过来按钮会保持禁用状态！
                is_journal_disabled = False 
                
                with col_list[2]:
                    st.markdown('<p class="radio-label">要求：</p>', unsafe_allow_html=True)
                with col_list[3]:
                    custom_req = st.text_input("特殊要求", placeholder="例如：去除作者朝代", label_visibility="collapsed")
                
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
                
                # 给自定义模式一个默认提示
                placeholder_text = "请输入待处理的参考文献，并在上方填写特殊要求..."

        st.markdown("---")

        col_input, col_output = st.columns(2, gap="large")

        # === 左栏：输入 ===
        with col_input:
            # 🔴 修改点：将 st.subheader 替换为带宋体样式的 HTML
            st.markdown("""
            <h3 style="font-family: 'Source Han Serif CN', 'Songti SC', 'SimSun', serif; font-size: 20px; font-weight: bold; color: #333; margin-bottom: 10px;">
                &#128221; 原始文本
            </h3>
            """, unsafe_allow_html=True)
            
            user_input = st.text_area(
                "Input", 
                height=300, 
                placeholder=placeholder_text, 
                label_visibility="collapsed",
                key="input_area",
                max_chars=1000  # 强制最多 500 字
            )


            st.write("")
            c1, c2, c3 = st.columns([1, 2, 1])
            # === 逻辑处理 ===
        # 找到原来的 st.button 代码，修改如下：
        
        with c2:
            # 如果是“通用国标”或“自定义”，is_journal_disabled 默认为 False (可用)
            # 只有在“专业期刊”且选了开发中选项时，is_journal_disabled 为 True
            
            # 为了代码健壮性，先初始化一下这个变量（防止在非专业期刊模式下报错）
            if 'is_journal_disabled' not in locals():
                is_journal_disabled = False

            run_btn = st.button(
                "✨ 立即排版", 
                type="primary", 
                use_container_width=True, 
                disabled=is_journal_disabled  # <--- 核心修改在这里！
            )

        # === 逻辑处理 ===
        if run_btn:
            if not api_key:
                st.toast("🚫 请先在侧边栏设置 API Key", icon="🚫")
            elif not user_input:
                st.toast("⚠️ 请输入文本", icon="⚠️")
            else:
                try:
                    with st.status("📝 典校处理中...", expanded=True) as status:
                        st.write("正在解析引用内容...")
                        
                        # 这两行是你刚换的魔塔代码，注意它们的前面缩进要一致
                        client = OpenAI(api_key=api_key, base_url="https://api-inference.modelscope.cn/v1")
                        
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
                        
                        # 👇 报错的就是这一行！
                        # 它的左边必须和上面的 response = ... 完全对齐（一样多的空格）
                        st.write("正在规范引用格式...") 

                        raw_result = response.choices[0].message.content.strip()

                        # 2. ✨【新步骤】先提取 XML (把思考过程过滤掉)
                        xml_cleaned_result = extract_xml_result(raw_result)

                        # 3. 🌟 再调用序号清洗函数
                        # 无论什么模式，这一步都会把序号洗掉
                        final_result = clean_citation_number(xml_cleaned_result)
                        
                        # 3. 把清洗后的结果存入状态
                        st.session_state.temp_result = final_result
                        st.session_state.last_input = user_input
                        
                        status.update(label="✅ 典校完成！", state="complete", expanded=False)
                    
                except Exception as e:
                    st.error(f"出错啦：{e}")

        # === 右栏：输出 ===
        with col_output:
            # 🔴 标题：宋体样式
            st.markdown("""
            <h3 style="font-family: 'Source Han Serif CN', 'Songti SC', 'SimSun', serif; font-size: 20px; font-weight: bold; color: #333; margin-bottom: 10px;">
                &#9989; 排版结果
            </h3>
            """, unsafe_allow_html=True)
            
            if st.session_state.temp_result:
                # 获取当前文本框的内容（允许用户手动修改后提交）
                final_text = st.text_area(
                    "Result", 
                    value=st.session_state.temp_result, 
                    height=300, 
                    label_visibility="collapsed"
                )
                
                b_col1, b_col2 = st.columns([1, 1])
                
                # --- 按钮 1：确认并入库 ---
                with b_col1:
                    # 给按钮加个 key
                    if st.button("📥 确认并入库", type="primary", use_container_width=True, key="btn_archive"):
                        # 1. 获取当前文本框里的完整内容
                        current_text_content = final_text.strip()
                        
                        # 2. 【核心修改】检查是否和“上一次成功入库的文本”完全一致
                        # 如果完全一样，说明是用户不小心多点了一次按钮 -> 拦截
                        if current_text_content == st.session_state.last_archived_text:
                            st.toast("🔔 这些内容刚才已经入库啦，请勿重复点击。", icon="✋")
                        
                        else:
                            # 3. 如果不一样（哪怕只是多了一行或少了一行），都视为新的操作 -> 执行入库
                            new_entries = [line.strip() for line in current_text_content.split('\n') if line.strip()]
                            
                            if new_entries:
                                st.session_state.history_list.extend(new_entries)
                                
                                # ✨ 更新“最后一次入库文本”的记录
                                st.session_state.last_archived_text = current_text_content
                                
                                st.toast(f"✅ 已成功归档 {len(new_entries)} 条文献！结果已保留。", icon="🎉")
                            else:
                                st.toast("⚠️ 文本为空，无法入库", icon="⚠️")

                # --- 按钮 2：放弃结果 ---
                with b_col2:
                    if st.button("🗑️ 放弃结果", use_container_width=True):
                        st.session_state.temp_result = ""
                        st.rerun()
                
                # 底部提示信息
                st.markdown("""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 5px; margin-bottom: 20px;">
                    <span style="font-size: 12px; color: #888;">💡 提示：点击文本框 Ctrl+A 全选</span>
                    <span style="font-size: 12px; color: #e6a23c;">生成结果仅供参考，建议核对后确认。</span>
                </div>
                """, unsafe_allow_html=True)
                
            else:
                # 空状态占位符
                st.markdown(
                    """
                    <div style="height: 300px; background-color: #fff; border: 1px dashed #ddd; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #888;">
                        <p style="font-size: 18px; margin-bottom: 10px;">👋 准备就绪</p>
                        <p style="font-size: 14px;">请在左侧输入参考文献并点击排版</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )

    # ================= 5. 页面 B：历史记录库 =================
    elif page == "📂 历史记录":
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 30px; margin-right: 10px;">📂</span>
            <span style="font-size: 30px; font-weight: bold; color: #333;">历史记录</span>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.history_list:
            st.info("📭 还没有历史记录，快去「文献排版」生成并确认入库吧！")
        else:
            full_history_text = "\n".join(st.session_state.history_list)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"共累积 {len(st.session_state.history_list)} 条文献。")
            with col2:
                st.download_button(
                    label="📥 导出全部 TXT",
                    data=full_history_text,
                    file_name="RefMaster_Export.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            st.text_area("历史汇总", value=full_history_text, height=500, label_visibility="collapsed")
            if st.button("🗑️ 清空所有历史", use_container_width=True):
                st.session_state.history_list = []
                st.rerun()

    # ================= 6. 页面 C：使用说明 =================
    elif page == "📖 使用说明":
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 30px; margin-right: 10px;">📖</span>
            <span style="font-size: 30px; font-weight: bold; color: #333;">使用说明</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 1. 工具简介 (标题改为与历史页一致的样式)
        st.markdown("""
        <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 22px; margin-right: 10px;">💡</span>
            <span style="font-size: 22px; font-weight: bold; color: #333;">工具简介</span>
        </div>

        **CanonMaster · 典校大师** 是一款基于 **智谱GLM-5大语言模型** 的智能参考文献排版转换工具，专为**人文社科领域**的学术群体打造。

        它的核心使命是将格式混乱、标点缺失、缺字漏项或是不符合目标规范的参考文献，**一键转换成符合学术标准的规范格式**。

        * **拒绝机械替换**：它不是简单的正则替换，而是依托大模型的**语义理解能力**，实现深度智能处理；
        * **准确排版重组**：能**识别补全**作者、书名、卷次、出版地、年份等要素，再按目标规范排版 —— 既确保**格式合规**，又保障**文献信息完整**。

        ---
        """, unsafe_allow_html=True)
        
        # 2. 名义考释 (标题改为与历史页一致的样式，样式保持不变)
        st.markdown("""
        <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 22px; margin-right: 10px;">📜</span>
            <span style="font-size: 22px; font-weight: bold; color: #333;">命名由来</span>
        </div>

        <style>
            .book-text {
                font-size: 16px;
                line-height: 1.8;
                text-align: justify;
                text-indent: 2em;
                margin-bottom: 15px;
            }
            .definition-list {
                list-style-type: none;
                font-size: 16px;
                line-height: 1.8;
                margin-bottom: 15px;
                padding-left: 0;
                text-indent: 2em;
            }
            b { color: #31333F; }
        </style>

        <div class="book-text">
            <b>「典校」一职，源远有自。</b>西汉成帝时，诏命<b>刘向、刘歆</b>父子<b>领校秘书</b>（见班固《汉书》），开系统性整理国家典籍之先河，后世遂以<b>「典校」</b>指称此项整理大业。东汉于兰台置令史，<b>「典校秘书」</b>（见应劭《风俗通义》），官制愈明；至三国东吴，更设<b>「中书典校」</b>一职，专司文书核查（见陈寿《三国志》），可见其责之重。
        </div>

        <div style="font-size: 16px; margin-bottom: 5px; text-indent: 2em;">
            本工具以 <b>CanonMaster · 典校大师</b> 为名，正承此意：
        </div>

        <ul class="definition-list">
            <li><b>「典」者，法度也：</b>奉学界通例为圭臬，立文章之规矩。</li>
            <li><b>「校」者，订正也：</b>借现代科技补罅漏，正体例之讹误。</li>
        </ul>

        <div class="book-text">
            我们希望以<b>现代科学技术</b>，<b>效古人校书之功</b>，让每一处引用皆经得起<b>法度之范</b>，每一篇文献尽合乎<b>体例之正</b>。
        </div>
        """, unsafe_allow_html=True)

        # 3. 简明指南 & 功能详解 & 常见问题 & 声明 (各小节标题改为与历史页一致的样式)
        st.markdown("""
        ---
        <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 22px; margin-right: 10px;">🛠️</span>
            <span style="font-size: 22px; font-weight: bold; color: #333;">功能详解</span>
        </div>

        **1. 通用国标 (GB/T 7714-2015)**：
        学术界通用的著录基准，适用于硕博学位论文、一般期刊论文等场景。本模式严格遵循国家标准，并根据引用位置细分为：
        * **文末模式**：适用于论文末尾的参考文献列表，去除专著页码。
        * **脚注模式**：适用于正文页底注释，保留引文页码。

        **2. 专业期刊**：
        针对《文学遗产》《历史研究》等特定刊物，内置各刊物官方“征稿启事”中的排版规则。只需选择目标刊物，即可自动适配体例要求，确保投稿格式合规。

        **3. 自定义规则**：
        适用于上述模式无法覆盖的特殊需求。该模式下先将文献格式转化为通用国标，再严格执行您输入的要求，实现个性化定制。

        ---
        <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 22px; margin-right: 10px;">❓</span>
            <span style="font-size: 22px; font-weight: bold; color: #333;">常见问题</span>
        </div>

        Q： **典校大师采用的是哪一版国标（GB/T 7714）？** A： 目前默认基于学界通用的**GB/T 7714-2015**标准。

        Q： **典校大师可以补全有缺漏的文献信息吗？** A： 典校大师有智能补全功能。如果典校大师无法在您提供的文本中找到确切的年份、出版信息等内容，它倾向于留空或标记 [缺]，而不是胡编乱造。 但请注意： 典校大师毕竟不是人类，**请务必人工核对信息**。

        Q： **为什么“专业期刊”里没有我想要的刊物？** A： 目前典校大师处于 v1.0 阶段，更多刊物排版要求正在开发中。 您可以先使用“通用国标”清洗一遍，然后在“自定义规则”中输入该刊物的特殊要求。

        Q： **刷新页面后，刚才的历史记录还有吗？** A： **没有**。基于隐私安全设计，典校大师**不连接任何数据库**，所有数据仅存在于您当前的浏览器内存中。刷新页面或关闭标签页后，数据即刻销毁，请及时导出相关文献。 
        
        """, unsafe_allow_html=True)  # <--- 🚨 这里漏了这一行！一定要补上！
    # ================= 7. 页面 D：交流共建 (新增) =================
    elif page == "🤝 交流共建":
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px;">
            <span style="font-size: 30px; margin-right: 10px;">🤝</span>
            <span style="font-size: 30px; font-weight: bold; color: #333;">交流共建</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
    <div style="background-color: #fff; padding: 20px; border-radius: 8px; border: 1px solid #eee; margin-bottom: 25px;">
        <p style="font-size: 16px; color: #333; line-height: 1.8; margin: 0;">
            <b>致每一位使用者：</b>
        </p>
        <p style="font-size: 16px; color: #555; line-height: 1.8; margin: 0; text-indent: 2em;">
            CanonMaster·典校大师 是一款由个人开发维护的开源工具。
        </p>
        <p style="font-size: 16px; color: #555; line-height: 1.8; margin: 0; text-indent: 2em;">
            在学术写作中，我和身边同学深受文献排版困扰，因此，我开发了这款工具，希望能够帮助同样为此耗费精力的你，节省哪怕一分钟的时间。
        </p>
        <p style="font-size: 16px; color: #555; line-height: 1.8; margin: 0; text-indent: 2em;">
            作为一个正在成长的工具，典校大师还有许多改进的地方。为了让它变得更好用、更顺手，我开设了以下两个反馈方式：
        </p>
    </div>
    """, unsafe_allow_html=True)

        # 等高布局容器 + 统一风格的双卡片（已缩进至该分支内）
        with st.container():
            col_qq, col_github = st.columns([1, 1], gap="medium")

            # 左侧 QQ 群卡片（字体大小统一 + 无列表Emoji）
            with col_qq:
                st.markdown("""
                <div style="
                    background-color: #f8f9fa; 
                    padding: 24px; 
                    border-radius: 10px; 
                    border: 1px solid #e9ecef; 
                    height: 100%; 
                    display: flex; 
                    flex-direction: column;
                ">
                    <h4 style="color: #333; margin-top: 0; margin-bottom: 16px; font-family: 'Source Han Serif CN', 'Songti SC', serif; font-size: 20px;">
                        🐧 方式一： QQ 交流群（1083502445） 
                    </h4>
                    <p style="font-size: 16px; color: #555; line-height: 1.6; margin-bottom: 20px;">
                        本群用于工具反馈与学术交流，也是能最快能找到我的地方。
                    </p>
                    <div style="font-size: 16px; color: #333; line-height: 1.8; flex-grow: 1;">
                        <b style="font-size: 16px; color: #333;">加入我们，你可以：</b>
                        <ul style="padding-left: 24px; margin-top: 12px; margin-bottom: 0;">
                            <li style="margin-bottom: 8px;"><b>反馈Bug：</b>排版结果异常？直接在群内提出，在线响应。</li>
                            <li style="margin-bottom: 8px;"><b>许愿功能：</b>你的想法就是下个版本的迭代方向。</li>
                            <li style="margin-bottom: 8px;"><b>优先体验：</b>抢先试用内测功能，参与版本测试。</li>
                            <li><b>学术互助：</b>寻找同路人，交流经验。</li>
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # 右侧 GitHub 卡片（字体大小统一 + 恢复星标）
            with col_github:
                st.markdown("""
                <div style="
                    background-color: #f8f9fa; 
                    padding: 24px; 
                    border-radius: 10px; 
                    border: 1px solid #e9ecef; 
                    height: 100%; 
                    display: flex; 
                    flex-direction: column;
                ">
                    <h4 style="color: #333; margin-top: 0; margin-bottom: 16px; font-family: 'Source Han Serif CN', 'Songti SC', serif; font-size: 20px;">
                        💻 方式二：GitHub 开源社区
                    </h4>
                    <div style="font-size: 16px; color: #555; line-height: 1.8; flex-grow: 1;">
                        <p style="margin-top: 0; margin-bottom: 16px;">
                            如果你是技术爱好者或习惯使用 GitHub，欢迎访问我的项目主页。
                        </p>
                        <ul style="padding-left: 24px; margin-top: 0; margin-bottom: 0;">
                            <li style="margin-bottom: 8px;">在 <b>Issues 区</b> 提交专业的 Bug 报告或功能建议。</li>
                            <li style="margin-bottom: 8px;">查看源码、提交 PR，与我一同完善工具的功能与体验。</li>
                            <li style="color: #8b0000; font-weight: bold;">🌟 你的每一个 Star，都是我持续迭代的最大动力！</li>
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # GitHub 跳转按钮（主按钮样式 + 宽度自适应）
                st.link_button(
                    "🔗 点击前往 GitHub 项目主页", 
                    "https://github.com/a2463712381-ui/CanonMaster",  # 替换为实际仓库地址
                    type="primary",
                    use_container_width=True
                )

    # ================= 8. 页脚 =================
    st.markdown("""
        <div style='text-align: center; color: #ccc; font-size: 12px; margin-top: 50px; border-top: 1px solid #eee; padding-top: 10px;'>
            <b>CanonMaster · 典校大师 v1.0</b> &nbsp; © 2026 &nbsp; | &nbsp; 仅限个人学习与学术研究
        </div>
        """, unsafe_allow_html=True)
