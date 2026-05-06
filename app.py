import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests

# --- Googleスプレッドシートへの接続設定（読み込み用） ---
conn = st.connection("google_sheets", type=GSheetsConnection)

# --- サイドバー ---
st.sidebar.title("メニュー")
mode = st.sidebar.radio("機能を選択", ["日々の入力をする", "1週間の集計を出す"])

# ---------------------------------------------------------
# モード1：日々の入力をする
# ---------------------------------------------------------
if mode == "日々の入力をする":
    st.title("📝 今日の出勤データを記入")
    
    # 成功メッセージを表示するためのフラグ
    success_flag = False
    saved_name = ""

    with st.form("input_form", clear_on_submit=True):
        date = st.date_input("日付", datetime.now())
        name = st.text_input("名前（スタッフ名）")
        hourly_rate = st.number_input("基本時給", value=1200)
        hours = st.number_input("勤務時間", value=0.0, step=0.5)
        sales = st.number_input("今日の売上", value=0)
        comm_rate = st.number_input("歩合率", value=0.1)
        
        submitted = st.form_submit_button("データを保存する")
        
        if submitted:
            if name == "":
                st.error("名前を入力してください！")
            else:
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLSc8Ost1yA_FAtXskdxt_8twu6vigBE3FEXBkH8Hw8rF8FRikw/formResponse"
                
                params = {
                    "entry.474978113": name,
                    "entry.223259871": hourly_rate,
                    "entry.1496582745": hours,
                    "entry.640486226": sales,
                    "entry.1975425774": comm_rate,
                }
                
                try:
                    response = requests.post(form_url, data=params)
                    if response.status_code == 200:
                        success_flag = True
                        saved_name = name
                        # 送信直後にキャッシュをクリア
                        st.cache_data.clear()
                    else:
                        st.error("送信に失敗しました。フォームの設定を確認してください。")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

    # エラー回避のため、フォームの外でメッセージとバルーンを出す
    if success_flag:
        st.success(f"{saved_name}さんのデータを保存しました！")
        st.balloons()

# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    # 最新データを取得
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 重複削除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        
        st.info(f"スプレッドシートから {len(df)} 行読み込みました。")

        # 列の位置を固定（0:タイムスタンプ, 1:日付, 2:名前...）
        cols_count = len(df.columns)
        processed_rows = []

        for i in range(len(df)):
            row = df.iloc[i]
            
            # --- 日付の解析 (B列を優先、ダメならA列) ---
            raw_date = str(row[1]) if cols_count > 1 else ""
            raw_ts = str(row[0])
            
            # どんな形式でも日付に変える魔法の関数
            parsed_date = pd.to_datetime(raw_date, errors='coerce')
            if pd.isna(parsed_date):
                parsed_date = pd.to_datetime(raw_ts, errors='coerce')
            
            # 日付が取れなかったらその行は捨てる
            if pd.isna(parsed_date):
                continue
                
            # --- データの抽出 ---
            try:
                processed_rows.append({
                    '確定日付': parsed_date,
                    '名前': str(row[2]) if cols_count > 2 else "不明",
                    '時給': pd.to_numeric(str(row[3]).replace(',', ''), errors='coerce') or 0,
                    '勤務時間': pd.to_numeric(str(row[4]).replace(',', ''), errors='coerce') or 0,
                    '個人売上': pd.to_numeric(str(row[5]).replace(',', ''), errors='coerce') or 0,
                    '歩合率': pd.to_numeric(str(row[6]).replace(',', ''), errors='coerce') or 0
                })
            except:
                continue

        final_df = pd.DataFrame(processed_rows)

        if final_df.empty:
            st.error("有効なデータが1件も見つかりませんでした。スプレッドシートの形式を確認してください。")
            with st.expander("生データの中身"):
                st.write(df.head())
        else:
            # 週の計算（日曜始まり）
            final_df['週開始'] = final_df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
            final_df['週ラベル'] = final_df['週開始'].dt.strftime('%Y-%m-%d (日)〜')

            st.success(f"{len(final_df)} 件の日付を認識しました！")

            all_weeks = sorted(final_df['週ラベル'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", all_weeks)
            
            week_df = final_df[final_df['週ラベル'] == selected_week].copy()

            if not week_df.empty:
                # 計算
                week_df['時給計算'] = week_df['時給'] * week_df['勤務時間']
                week_df['歩合計算'] = week_df['個人売上'] * week_df['歩合率']
                
                summary = week_df.groupby('名前').agg({
                    '勤務時間': 'sum', '個人売上': 'sum', '時給計算': 'sum', '歩合計算': 'sum'
                }).reset_index()

                summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
                summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

                st.dataframe(summary)
            else:
                st.info("データがありません。")
