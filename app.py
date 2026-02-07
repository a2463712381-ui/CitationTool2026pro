import streamlit as st
from openai import OpenAI

# ================= 1. 页面配置 & CSS (保持微信绿风格) =================
st.set_page_config(
    page_title="参考文献 AI 排版助手",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    .stApp { background-color: #f6f7f9; font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif; }
    .stTextArea textarea { background-color: #ffffff !important; border: 1px solid #dcdfe6 !important; border-radius: 12px !important; padding: 16px !important; font-size: 15px !important; color: #333 !important; }
    .stTextArea textarea:focus { border-color: #07c160 !important; box-shadow: 0 0 0 1px #07c160 !important; }
    div.stButton > button { width: 100%; background: linear-gradient(135deg, #07c160 0%, #05a350 100%) !important; color: white !important; border: none !important; border-radius: 50px !important; padding: 12px 24px !important; font-size: 16px !important; font-weight: 600 !important; box-shadow: 0 4px 12px rgba(7, 193, 96, 0.3) !important; transition: all 0.3s !important; }
    div.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(7, 193, 96, 0.4) !important; }
    div[role="radiogroup"] { background-color: #eef1f6; padding: 4px; border-radius: 12px; display: flex; justify-content: space-around; }
    .stDeployButton {display:none;}
    </style>
""", unsafe_allow_html=True)

# ================= 2. Prompt 仓库 =================

# 【仓库1】通用国标 Prompt
GB_FULL_PROMPT = """
# Role
你是一个专业的参考文献格式清洗工具，特别精通社科理科与古籍引用规范。你的核心任务是将用户提供的非结构化文本，转换为符合 GB/T 7714-2015 标准的规范格式。

# Core Protocol (核心原则)
1. 格式独裁：严格执行标点、空格、排序规范。
2. 内容克制：对于年份、页码等特指性信息，严禁“模型幻觉”式猜测。
3. 双轨处理：严格区分“中文文献”与“西文文献”的排版习惯。

# 1. 核心处理逻辑
🟢 绿区：自动化格式清洗
1. 标点与空格: 强制将所有中文标点转换为英文半角符号( . , : )。中文文献标点后禁止空格，西文文献标点后必须空格。
2. 作者逻辑: 
   - 作者 ≤ 3人: 全部列出。
   - 作者 > 3人: 只列前3人, 后加 ", et al." (西文) 或 ", 等" (中文)。
   -大写规则 (仅适用于外文文献): 所有西文作者姓名、以及用汉语拼音书写的中国作者姓名，一律执行“姓全大写”规则。
   -名缩写: 西文名取首字母 (无缩写点)。例: LECUN Y 或 LI J N (拼音)
3. 载体与路径: 
   -纸质文献 ([M], [J], [D], [C], [N]等)：严禁输出 DOI、URL 或 [引用日期]。
   - 电子文献 ([M/OL], [J/OL], [EB/OL]等):
     - 特征：含 URL/DOI 时必加 /OL, 必须补全 [引用日期] (若无具体日期则填今日)。
     - 路径处理 (关键):
       - 情形 A (有 URL + 有 DOI): "获取和访问路径"填 URL; "DOI"项填 "DOI:xxx"。
       - 情形 B (仅有 URL): "获取和访问路径"填 URL; "DOI"项留空。
       - 情形 C (仅有 DOI): "获取和访问路径"自动拼装为 "http://doi.org/[DOI号码]"; "DOI"项填 "DOI:xxx"。
4. 出版地补全: 利用知识库识别出版社总部（如中华书局→北京）。
5. 类型识别:
   - 析出文献：识别到"//","见","In" → 启用 // 结构。
   - 报纸：[N]；期刊：[J]；图书：[M]；学位：[D]；会议：[C]；标准[S]; 专利[P]; 汇编 [G]；报告 [R]；档案 [A]；舆图 [CM]电子公告/数据库：[EB/OL], [DB/OL]。

🟡 黄区：书名定责核心逻辑
1. 书名定责:
   - 原典名 (如《史记》): (朝代)原著者. 题名[M].
   - 特定注本 (如《世说新语笺疏》): (朝代)原著者. 题名[M]. (朝代)核心注者,角色.
   - 独立专著 (如《四库全书总目》): (朝代)作者. 题名[M].
   -若书名包含‘注’、‘疏’、‘解’、‘笺’、‘栓’、‘集’且原输入缺失注者，尝试利用知识库补全核心注者；若无法确认则保持原样。•错误示例： (唐)杜甫. 杜诗镜铨...正确示例： (唐)杜甫. 杜诗镜铨[M]. (清)杨伦, 笺注...”
2. 朝代与国籍增强:
   - 古代作者：必须补全朝代，如 (南朝宋)、（西汉）。
   - 外国作者：必须补全 (国籍)和全名。若输入为中文，外国作者姓名必须使用中文全称译名，并补全(国籍)。如输入"康德" → 输出"(德)伊曼努尔·康德"、输入"纯粹理性批判",输出作者为"(德)伊曼努尔·康德"。

🔴 红区：绝对禁止区
- 严禁猜测年份、页码、卷期号、出版社。若输入未提供出版社信息，严禁利用知识库擅自补全特定出版社和出版地。若缺失则标记 [缺:xxx]。

#  输出模板 (Templates)
A. 纸质专著/古籍/译著/汇编/报告 [M/G/R]: 主要责任者.题名[M].其他责任者,角色.出版地:出版者,[缺:出版年]:[缺:页码].
B. 纸质期刊 [J] (无 DOI): 主要责任者.题名[J].刊名,[缺:出版年],[卷]([期]):[缺:页码].
C. 电子期刊 [J/OL]: 主要责任者.题名[J/OL].刊名,[缺:出版年],[卷]([期]):[缺:页码].[缺:引用日期].获取和访问路径.DOI:[DOI号码].
D. 报纸 [N]: 主要责任者.题名[N].报纸名,YYYY-MM-DD([版次]).
E. 析出文献 [C]// 或 [M]//: 析出责任者.析出题名[文献类型]//专著主要责任者.专著题名:其他题名信息.出版地:出版者,[缺:出版年]:[缺:析出页码].
F. 专利文献 [P] (新增): 专利申请者或所有者. 专利题名: 专利号[P]. 公告日期或公开日期.
G. 标准文献 [S] (新增): 主要责任者(标准提出者). 标准名称: 标准号[S]. 出版地: 出版者, 出版年: 页码. (示例: 全国信息与文献标准化技术委员会. 文献著录: GB/T 3792.4—2009[S]. 北京: 中国标准出版社, 2010: 3.)
H. 外文文献: Author. Title [Type]. Other Contributors. City: Publisher, [Year]: [Pages].(示例: 邓一刚. 全智能节电器: 200610171314.3[P]. 2006-12-13.)

# Output Format
请直接输出处理后的纯文本，每条引用换行显示。不要输出 JSON 格式，不要包含 "formatted_text" 键名。
如果原文本包含多条引用，请逐条处理并换行。
"""

# 【仓库2】文学遗产专用 Prompt
WXYC_FULL_PROMPT = """
# Role 
你是一位《文学遗产》杂志社的资深责任编辑。你的任务是将输入转换为符合《文学遗产》注释体例的文本。

# 1. 绝对红线
1. **禁止冒号连接**：作者与书名号之间绝不可加冒号或逗号 (错误: 司马迁：《史记》,正确: 司马迁《史记》 )。
2. **禁止期刊页码**：现代期刊论文绝不可输出页码。(正确:《文学遗产》2003年第6期。)
3. **禁止析出连接词**：绝不可使用“载”或“参见”。(正确：鲁迅《篇名》，《全集》...)
4. **禁止出版社简称**：必须还原全称 (人大出版社 -> 中国人民大学出版社)
5. **必须数字规范**：古籍卷数"0"写作"〇"；现代卷数/册数/页码均用阿拉伯数字。

# 2. 核心双轨制逻辑
1. **卷数**：古籍用汉字(卷一)；现代用数字(第1卷)。
2. **册数**：统一用"第x册"。
3. **页码**：统一用"第x页"。古书叶码用"第xa/b叶"。
4. **年份**：古书和民国线装书用"年号"；现代仅"公元"。

# 3. 标准输出模板
1. **专著**：[责任者]《[书名]》，[出版社][年份]版，[册次]，[页码]。
   - 例：钱锺书《管锥编》，中华书局1979年版，第10页。
2. **古籍整理本**：([朝代])原作者著，([朝代])整理者校注《[书名]》[卷次]《[篇名]》，[出版社][年份]版，[页码]。
   - 例：(晋)陶渊明著，逯钦立校注《陶渊明集》卷二《饮酒》，中华书局1979年版，第150页。
3. **期刊**：[作者]《[篇名]》，《[刊名]》[年份]第[期号]期。
   - 例：刘跃进《秦汉文学史研究》，《文学遗产》2003年第6期。
4. **析出文献**：[作者]《[篇名]》，[编者]《[书名]》，[出版社][年份]版，[页码]。
5. **学位论文**：[作者]《[篇名]》，[学校][年份][性质]，[页码]。
   - 例： 傅刚《陆机诗歌简论》，上海师范大学1986年硕士论文，第28页。
6. **外文文献**：遵照该语种通行体例（通常为MLA或Chicago）。
   - 例： M.M. Baktin, Discourse in the Novel, The Dialogic Imagination: Four Essays by M.M. Baktin. Austin: University of Texas Press, 1988, pp.259-422.

# 4. 智能补全 (AI Logic)
- **双重责任**：遇到《世说新语笺疏》等注本，必须完整写出 原作者 与 注者。
- **自动推断**：若缺失出版社城市，不需补全(文学遗产体例不强制写城市，只写出版社)。
-外国出版单位及作者须加国名（籍），作者需全名，规范要求使用方括号[]
请直接输出结果，不要废话。
"""

# 【仓库3】简单通用 Prompt
SIMPLE_TEXT_PROMPT = """
# Role
学术文献格式调整助手。
# Rules
1. **去代码化**：严禁输出 [M], [J] 等代码。
2. **智能补全**：利用知识库补全缺失的作者、朝代、国籍。
3. **中文保护**：中文作者必须保持汉字，禁止转拼音。
"""

# ================= 3. 页面布局与逻辑 =================
st.markdown("<h2 style='text-align: center; color: #1f2d3d;'>📚 参考文献 AI 排版</h2>", unsafe_allow_html=True)

# 侧边栏 Key
with st.sidebar:
    st.header("⚙️ 设置")
    try:
        if "DEEPSEEK_API_KEY" in st.secrets:
            api_key = st.secrets["DEEPSEEK_API_KEY"]
            st.success("✅ 已自动加载 Key")
        else:
            api_key = st.text_input("DeepSeek API Key", type="password")
    except:
        api_key = st.text_input("DeepSeek API Key", type="password")

# 主模式选择
mode = st.radio(
    "模式选择", 
    ["通用国标 (GB/T 7714)", "专业期刊", "自定义规则"], 
    horizontal=True,
    label_visibility="collapsed"
)

# 子选项逻辑
system_prompt = ""
placeholder_text = ""

# --- 1. 通用国标模式 (已删除古籍开关) ---
if mode == "通用国标 (GB/T 7714)":
    # 直接展示格式选择，不再分栏
    gb_type = st.radio("输出格式", ["文末参考文献 (去页码)", "页下注 (保留页码)"], horizontal=True)
    
    placeholder_text = "支持古今混排，例如：\n[宋]苏轼撰;孔凡礼点校.苏轼诗集.中华书局,1982.\n鲁迅.中国小说史略.上海古籍出版社,1998."
    
    # 动态构建 Prompt：只根据“页下注/参考文献表”进行微调
    task_adjust = "\n# Task Adjustment: 用户需要[页下注]格式，必须在末尾保留引文页码。" if "页下注" in gb_type else "\n# Task Adjustment: 用户需要[参考文献表]格式，必须去除专著页码。"
    
    # 【注意】这里直接使用你原来定义好的 Prompt，不再拼接 is_ancient 判断
    system_prompt = GB_FULL_PROMPT + task_adjust

# --- 2. 专业期刊模式 ---
elif mode == "专业期刊":
    target_journal = st.selectbox("选择目标期刊", ["文学遗产", "历史研究", "其他"])
    placeholder_text = "请输入原始引用..."
    
    if target_journal == "文学遗产":
        # 直接使用你的文学遗产 Prompt，它本身就包含古籍处理逻辑
        system_prompt = WXYC_FULL_PROMPT
        
    elif target_journal == "历史研究":
        system_prompt = SIMPLE_TEXT_PROMPT + "\n# Target Style: 《历史研究》体例：作者：《书名》，出版社年份版。"
    else:
        other_name = st.text_input("输入期刊名", placeholder="例如：文学评论")
        system_prompt = SIMPLE_TEXT_PROMPT + f"\n# Target Style: 遵循《{other_name}》体例。"

# --- 3. 自定义模式 ---
else: 
    custom_req = st.text_input("特殊要求", placeholder="例如：年份加粗，作者不缩写")
    placeholder_text = "输入内容..."
    system_prompt = SIMPLE_TEXT_PROMPT + f"\n# User Requirement: {custom_req}"

# 输入区域
user_input = st.text_area("输入", height=200, placeholder=placeholder_text, label_visibility="collapsed")

# 按钮与执行
if st.button("✨ 立即排版"):
    if not api_key:
        st.error("请先设置 API Key")
    elif not user_input:
        st.warning("请输入文本")
    else:
        try:
            with st.spinner("正在排版中..."):
                client = OpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
                
                response = client.chat.completions.create(
                    model="deepseek-ai/DeepSeek-V3",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ],
                    temperature=0.8, 
                    stream=False
                )
                result = response.choices[0].message.content.strip()
                
                # 结果展示
                st.markdown("### 📄 排版结果")
                st.text_area("结果", value=result, height=250, label_visibility="collapsed")
                st.caption("提示：点击框内 -> Ctrl+A 全选 -> Ctrl+C 复制 -> 粘贴到 Word")
                
        except Exception as e:
            st.error(f"出错啦：{e}")

st.markdown("<div style='text-align: center; color: #ccc; font-size: 12px; margin-top: 50px;'>Powered by DeepSeek</div>", unsafe_allow_html=True)