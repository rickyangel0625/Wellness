import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from groq import Groq

# 1. 頁面配置
st.set_page_config(page_title="言論審核系統", layout="wide")

# 2. 自定義 CSS (修正選取器邏輯)
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
        transition: all 0.3s ease;
    }
    /* 明確定義顏色類別 */
    .card-T { border-left-color: #ff4b4b !important; background-color: rgba(255, 75, 75, 0.1) !important; }
    .card-N { border-left-color: #28a745 !important; background-color: rgba(40, 167, 69, 0.1) !important; }
    .card-Optional { border-left-color: #8b4513 !important; background-color: rgba(139, 69, 19, 0.1) !important; }
    
    .post-text { font-size: 1.15em; line-height: 1.6; color: #1a1a1b; margin-top: 8px; }
    .id-badge { font-family: monospace; color: #555; background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 0.85em; margin-right: 5px; }
    .tag-badge { font-family: sans-serif; color: #fff; background: #6c757d; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; }
    </style>
""",
    unsafe_allow_html=True,
)

# 3. 初始化暫存 (確保 df 為 None)
if "df" not in st.session_state:
    st.session_state.df = None


# AI 分析核心函式
def ai_analyze(text, key):
    client = Groq(api_key=key)
    system_ins = 'You are a student safety analyst. Output ONLY JSON: {"target": "T/N/Optional", "subcategory": "H/E/S/V/C/D"}'
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


# 4. 側邊欄渲染 (將匯出邏輯獨立出來)
with st.sidebar:
    st.title("⚙️ 系統設定")
    try:
        default_key = st.secrets["GROQ_API_KEY"]
    except:
        default_key = ""

    user_api_key = st.text_input(
        "輸入 Groq API Key", value=default_key, type="password"
    )

    st.divider()
    st.header("💾 匯出結果")

    # 修正：只要 session_state 有資料，就一定要顯示按鈕
    if st.session_state.df is not None:
        export_df = st.session_state.df.copy()
        now_tw = datetime.utcnow() + timedelta(hours=8)
        time_str = now_tw.strftime("%Y-%m-%d %H:%M:%S")

        export_df["export_time"] = ""
        # 標記匯出時間的邏輯
        mask = (export_df["target"].notna()) & (
            export_df["target"].isin(["T", "N", "Optional"])
        )
        export_df.loc[mask, "export_time"] = time_str

        orig_name = st.session_state.get("original_filename", "Audit").split(".")[0]
        timestamp = now_tw.strftime("%m%d_%H%M")
        final_filename = f"{orig_name}_{timestamp}.csv"

        csv_data = export_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 匯出並下載 CSV",
            data=csv_data,
            file_name=final_filename,
            mime="text/csv",
            use_container_width=True,
            key="download_btn",  # 固定 key 防止按鈕消失
        )
    else:
        st.write("請先上傳 CSV 以啟用匯出功能。")

# 5. 主畫面與檔案上傳
st.title("🛡️ 學生言論安全審核系統")
uploaded_file = st.file_uploader("上傳待審核 CSV", type=["csv"])

# 6. 資料處理邏輯
if uploaded_file:
    # 💡 關鍵修正：如果上傳了新檔案，但檔名跟舊的不同，就清空舊資料重新讀取
    if st.session_state.get("last_uploaded_name") != uploaded_file.name:
        st.session_state.df = None
        st.session_state.last_uploaded_name = uploaded_file.name
        st.session_state.original_filename = uploaded_file.name

    if st.session_state.df is None:
        df = None
        encodings = ["utf-8-sig", "cp950", "utf-8", "latin1"]
        for enc in encodings:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=enc, dtype=str)
                break
            except:
                continue

        if df is None:
            uploaded_file.seek(0)
            df = pd.read_csv(
                uploaded_file, encoding="utf-8", errors="replace", dtype=str
            )

        df = df.fillna("")
        for col in ["target", "subcategory"]:
            if col not in df.columns:
                df[col] = ""

        # 移除欄位前後空格避免判斷出錯
        df["target"] = df["target"].str.strip()
        st.session_state.df = df
        st.rerun()

    df = st.session_state.df

    # AI 自動預測按鈕
    if st.button("🚀 執行 AI 自動預測"):
        if not user_api_key:
            st.warning("請先輸入 API Key！")
        else:
            todo_list = df[~df["target"].isin(["T", "N", "Optional"])].index
            if len(todo_list) > 0:
                pbar = st.progress(0)
                for idx, i in enumerate(todo_list):
                    t, s = ai_analyze(df.at[i, "cleaned_text"], user_api_key)
                    if t != "error":
                        df.at[i, "target"], df.at[i, "subcategory"] = t, s
                    pbar.progress((idx + 1) / len(todo_list))
                st.session_state.df = df
                st.rerun()

    st.divider()

    # 7. 渲染介面 (修正顏色判斷邏輯)
    for i in range(len(df)):
        cur_t = str(df.at[i, "target"]).strip()
        # 💡 關鍵修正：嚴格檢查 target 值，只有在三種狀態下才賦予 CSS Class
        if cur_t in ["T", "N", "Optional"]:
            card_class = f"card-{cur_t}"
        else:
            card_class = ""  # 為空或其他值時，完全不帶顏色 class

        with st.container():
            st.markdown(f'<div class="post-card {card_class}">', unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1])

            with c1:
                raw_tags = (
                    df.at[i, "subCategories"] if "subCategories" in df.columns else ""
                )
                tag_html = (
                    f'<span class="tag-badge">{raw_tags}</span>' if raw_tags else ""
                )
                st.markdown(
                    f'<div><span class="id-badge">ID: {df.at[i, "_id"]}</span>{tag_html}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<p class="post-text">{df.at[i, "cleaned_text"]}</p>',
                    unsafe_allow_html=True,
                )

            with c2:
                # 選擇標籤
                t_opts = ["", "T", "N", "Optional"]
                try:
                    t_idx = t_opts.index(cur_t)
                except ValueError:
                    t_idx = 0

                new_t = st.selectbox("標籤", t_opts, index=t_idx, key=f"t_{i}")

                # 選擇子類
                s_opts = ["", "H", "E", "S", "V", "C", "D"]
                cur_s = str(df.at[i, "subcategory"]).strip()
                try:
                    s_idx = s_opts.index(cur_s)
                except ValueError:
                    s_idx = 0

                new_s = st.selectbox("子類", s_opts, index=s_idx, key=f"s_{i}")

                # 只有當值真的改變時才觸發 rerun
                if new_t != df.at[i, "target"] or new_s != df.at[i, "subcategory"]:
                    st.session_state.df.at[i, "target"] = new_t
                    st.session_state.df.at[i, "subcategory"] = new_s
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)
