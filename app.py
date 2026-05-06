import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# --- スプレッドシート接続 ---
conn = st.connection("google_sheets", type=GSheetsConnection)

# --- サイドバー ---
st.sidebar.title("メニュー")
mode = st.sidebar.radio("機能を選択", ["日々の入力をする", "1週間の集計を出す"])

if mode == "日々の入力をする":
    st.title("📝 今日の出勤データを記入")
    
    # フォーム開始
    with st.form("input_form"):
        input_date = st.date_input("日付", datetime.now())
        name = st.text_input("名前（スタッフ名）")
        hourly_rate = st.number_input("基本時給", value=1200)
        hours = st.number_input("勤務時間", value=0.0, step=0.5)
        sales = st.number_input("今日の売上", value=0)
        comm_rate = st.number_input("歩合率", value=0.1)
        
        # 【重要】ここで変数を定義（これが if submitted の上にないとダメ！）
        submitted = st.form_submit_button("送信リンクを準備する")
        
        # ここから下が「送信ボタン」が押された後の処理
    if submitted:
            if name == "":
                st.error("名前を入力してください！")
            else:
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLSc8Ost1yA_FAtXskdxt_8twu6vigBE3FEXBkH8Hw8rF8FRikw/formResponse"
                
                # 最新の「記述式」用ID
                params = {
                    "entry.474978113": name,
                    "entry.223259871": hourly_rate,
                    "entry.1496582745": hours,
                    "entry.640486226": sales,
                    "entry.1975425774": comm_rate,
                    "entry.2102143015": input_date.strftime("%Y-%m-%d")
                }
                
                # ↓ここの行の先頭の空白を、上のparamsの開始位置と揃えるのがコツです
                query_string = urllib.parse.urlencode(params)
                complete_url = f"{form_url}?{query_string}&submit=Submit"
                
                st.success("✅ 送信データの準備完了！")
                st.link_button("🚀 確定してスプレッドシートに保存", complete_url)
# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    # データを最新状態で読み込み
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 列の重複を排除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        processed_rows = []
        cols_count = len(df.columns)

        for i in range(len(df)):
            try:
                # 0番目がタイムスタンプ(A列)、1番目が入力した日付(B列)
                raw_ts = str(df.iat[i, 0])
                raw_date = str(df.iat[i, 1]) if cols_count > 1 else ""
                
                # B列の日付を優先、なければA列のタイムスタンプを使用
                parsed_date = pd.to_datetime(raw_date, errors='coerce')
                if pd.isna(parsed_date):
                    parsed_date = pd.to_datetime(raw_ts, errors='coerce')
                
                if pd.isna(parsed_date): continue
                    
                processed_rows.append({
                    '確定日付': parsed_date,
                    '名前': str(df.iat[i, 2]) if cols_count > 2 else "不明",
                    '時給': pd.to_numeric(str(df.iat[i, 3]).replace(',', ''), errors='coerce') or 0,
                    '勤務時間': pd.to_numeric(str(df.iat[i, 4]).replace(',', ''), errors='coerce') or 0,
                    '個人売上': pd.to_numeric(str(df.iat[i, 5]).replace(',', ''), errors='coerce') or 0,
                    '歩合率': pd.to_numeric(str(df.iat[i, 6]).replace(',', ''), errors='coerce') or 0
                })
            except:
                continue

        final_df = pd.DataFrame(processed_rows)

        if not final_df.empty:
            # 週の開始日（日曜日）を計算
            final_df['週開始'] = final_df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
            final_df['週ラベル'] = final_df['週開始'].dt.strftime('%Y-%m-%d (日)〜')

            all_weeks = sorted(final_df['週ラベル'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", all_weeks)
            
            week_df = final_df[final_df['週ラベル'] == selected_week].copy()

            if not week_df.empty:
                # 給与計算（時給 vs 歩合 の高い方）
                week_df['時給計算'] = week_df['時給'].astype(float) * week_df['勤務時間'].astype(float)
                week_df['歩合計算'] = week_df['個人売上'].astype(float) * week_df['歩合率'].astype(float)
                
                summary = week_df.groupby('名前').agg({
                    '勤務時間': 'sum', '個人売上': 'sum', '時給計算': 'sum', '歩合計算': 'sum'
                }).reset_index()

                summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
                summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

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
