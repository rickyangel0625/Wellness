import streamlit as st
import pandas as pd
import json
import time
from groq import Groq

# 1. 頁面配置
st.set_page_config(page_title="言論審核系統", layout="wide")

# 2. 自定義 CSS：更美觀的透明背景色彩
st.markdown(
    """
    <style>
    .post-card {
        padding: 20px;
        border-radius: 12px;
        border-left: 8px solid #dfe3e8;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        background-color: #ffffff;
    }
    /* 顏色樣式 (透明背景 + 實色邊框) */
    .card-T { 
        border-left-color: #ff4b4b !important; 
        background-color: rgba(255, 75, 75, 0.1) !important; 
    }
    .card-N { 
        border-left-color: #28a745 !important; 
        background-color: rgba(40, 167, 69, 0.1) !important; 
    }
    .card-Optional { 
        border-left-color: #8b4513 !important; 
        background-color: rgba(139, 69, 19, 0.1) !important; 
    }
    
    .post-text { font-size: 1.15em; line-height: 1.6; color: #1a1a1b; margin-top: 8px; }
    .id-badge { font-family: monospace; color: #555; background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
    </style>
""",
    unsafe_allow_html=True,
)

# 3. 初始化暫存
if "df" not in st.session_state:
    st.session_state.df = None

# 4. 側邊欄：設定與匯出
with st.sidebar:
    st.title("⚙️ 系統設定")
    try:
        default_key = st.secrets["GROQ_API_KEY"]
    except:
        default_key = ""

    user_api_key = st.text_input(
        "輸入 Groq API Key",
        value=default_key,
        type="password",
        help="如果此處為空，請輸入你的 Key 以啟用 AI 功能",
    )

    st.divider()
    st.header("💾 匯出結果")
    if st.session_state.df is not None:
        csv_data = st.session_state.df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 匯出並下載結果 CSV",
            data=csv_data,
            file_name="Audit_Result.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.info("💡 匯出會包含所有標籤與原始欄位內容。")

# 5. 主畫面
st.title("🛡️ 學生言論安全審核系統")
uploaded_file = st.file_uploader("上傳待審核 CSV (支援續作)", type=["csv"])


# AI 核心邏輯
def ai_analyze(text, key):
    client = Groq(api_key=key)
    system_ins = 'You are a student safety analyst. Output ONLY JSON: {"target": "T/N/Optional", "subcategory": "H/E/S/V/C/D/""}'
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_ins},
                {"role": "user", "content": str(text)},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0,
        )
        res = json.loads(chat_completion.choices[0].message.content)
        return res.get("target", "N"), res.get("subcategory", "")
    except:
        return "error", ""


# 6. 資料處理
if uploaded_file:
    if st.session_state.df is None:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig", dtype=str)
        for col in ["target", "subcategory"]:
            if col not in df.columns:
                df[col] = ""
        st.session_state.df = df

    df = st.session_state.df

    # 批量分析按鈕
    if st.button("🚀 執行 AI 自動預測 (僅針對未標籤項)"):
        if not user_api_key:
            st.warning("請先在左側輸入 API Key 才能執行 AI 分析！")
        else:
            todo_list = df[~df["target"].isin(["T", "N", "Optional"])].index
            if len(todo_list) == 0:
                st.info("目前沒有需要 AI 分析的項目。")
            else:
                pbar = st.progress(0)
                for idx, i in enumerate(todo_list):
                    t, s = ai_analyze(df.at[i, "cleaned_text"], user_api_key)
                    if t != "error":
                        df.at[i, "target"] = t
                        df.at[i, "subcategory"] = s
                    pbar.progress((idx + 1) / len(todo_list))
                st.session_state.df = df
                st.rerun()

    st.divider()

    # 7. 渲染卡片 (這部分會自動讀取暫存的內容)
    for i in range(len(df)):
        cur_t = df.at[i, "target"]
        # 決定顏色 class
        card_class = ""
        if cur_t == "T":
            card_class = "card-T"
        elif cur_t == "N":
            card_class = "card-N"
        elif cur_t == "Optional":
            card_class = "card-Optional"

        with st.container():
            st.markdown(f'<div class="post-card {card_class}">', unsafe_allow_html=True)

            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(
                    f'<span class="id-badge">ID: {df.at[i, "_id"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<p class="post-text">{df.at[i, "cleaned_text"]}</p>',
                    unsafe_allow_html=True,
                )

            with c2:
                # 標籤選項
                t_opts = ["", "T", "N", "Optional"]
                new_t = st.selectbox(
                    "標籤",
                    t_opts,
                    index=t_opts.index(cur_t) if cur_t in t_opts else 0,
                    key=f"t_{i}",
                )

                s_opts = ["", "H", "E", "S", "V", "C", "D"]
                cur_s = df.at[i, "subcategory"]
                new_s = st.selectbox(
                    "子類",
                    s_opts,
                    index=s_opts.index(cur_s) if cur_s in s_opts else 0,
                    key=f"s_{i}",
                )

                # 自動更新暫存資料
                if new_t != df.at[i, "target"] or new_s != df.at[i, "subcategory"]:
                    st.session_state.df.at[i, "target"] = new_t
                    st.session_state.df.at[i, "subcategory"] = new_s
                    st.rerun()  # 點選後立刻變色

            st.markdown("</div>", unsafe_allow_html=True)
