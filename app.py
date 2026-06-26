import streamlit as st
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

from salary import add_week_columns, build_submission_url, normalize_work_records, summarize_salary

# --- Googleスプレッドシートへの接続設定 ---
conn = st.connection("google_sheets", type=GSheetsConnection)

# --- サイドバー (ここが抜けていたためエラーになっていました) ---
st.sidebar.title("メニュー")
mode = st.sidebar.radio("機能を選択", ["日々の入力をする", "1週間の集計を出す"])

# ---------------------------------------------------------
# モード1：日々の入力をする
# ---------------------------------------------------------
if mode == "日々の入力をする":
    st.title("📝 勤務データ入力 (最新版)")

    with st.form("input_form"):
        input_date = st.date_input("日付", datetime.now())
        name = st.text_input("名前")
        hourly_rate = st.number_input("基本時給", value=1200)
        hours = st.number_input("勤務時間", value=0.0, step=0.5)
        sales = st.number_input("売上", value=0)
        comm_rate = st.number_input("歩合率", value=0.1)

        submitted = st.form_submit_button("データを送信する")

        if submitted:
            if not name.strip():
                st.error("名前を入力してください")
            else:
                complete_url = build_submission_url(
                    input_date,
                    name,
                    hourly_rate,
                    hours,
                    sales,
                    comm_rate,
                )
                st.success("✅ 送信準備が整いました！")
                st.link_button("🚀 スプレッドシートに保存（ここを必ずクリック）", complete_url)
# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    # データを最新状態で読み込み
    df_raw = conn.read(ttl=0)

    if df_raw is not None and not df_raw.empty:
        final_df = add_week_columns(normalize_work_records(df_raw))

        if not final_df.empty:
            all_weeks = sorted(final_df['週ラベル'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", all_weeks)

            week_df = final_df[final_df['週ラベル'] == selected_week].copy()

            if not week_df.empty:
                summary = summarize_salary(week_df)

                # 結果表示
                st.subheader(f"📅 {selected_week} の集計結果")
                st.dataframe(summary[['名前', '勤務時間', '個人売上', '最終支給額', '計算方法']])
                
                st.divider()
                # 個別詳細
                target_staff = st.selectbox("詳細を確認するスタッフ", summary['名前'])
                p = summary[summary['名前'] == target_staff].iloc[0]
                c1, c2, c3 = st.columns(3)
                c1.metric("実働合計", f"{p['勤務時間']}h")
                c2.metric("売上合計", f"{int(p['個人売上']):,}円")
                c3.metric("確定給料", f"{int(p['最終支給額']):,}円")
    else:
        st.info("データが読み込めませんでした。スプレッドシートを確認してください。")
