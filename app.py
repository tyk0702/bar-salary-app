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
    
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 重複削除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        
        # --- デバッグ情報 ---
        st.info(f"スプレッドシートから {len(df)} 行のデータを読み込みました。")

        # 列の位置固定（0:TS, 1:日付, 2:名前, 3:時給, 4:時間, 5:売上, 6:歩合）
        cols_count = len(df.columns)
        final_df = pd.DataFrame()
        
        # 1. タイムスタンプと日付の取得（形式を問わず無理やり変換）
        ts_raw = pd.to_datetime(df.iloc[:, 0], errors='coerce')
        
        if cols_count > 1:
            # B列を日付として変換。dayfirst=False, yearfirst=Trueなど柔軟に対応
            date_raw = pd.to_datetime(df.iloc[:, 1], errors='coerce')
            # B列が空ならA列（タイムスタンプ）を使う
            final_df['確定日付'] = date_raw.fillna(ts_raw)
        else:
            final_df['確定日付'] = ts_raw
            
        # 2. その他の列を位置で取得
        final_df['名前'] = df.iloc[:, 2].fillna("不明") if cols_count > 2 else "不明"
        final_df['時給'] = pd.to_numeric(df.iloc[:, 3], errors='coerce').fillna(0) if cols_count > 3 else 0
        final_df['勤務時間'] = pd.to_numeric(df.iloc[:, 4], errors='coerce').fillna(0) if cols_count > 4 else 0
        final_df['個人売上'] = pd.to_numeric(df.iloc[:, 5], errors='coerce').fillna(0) if cols_count > 5 else 0
        final_df['歩合率'] = pd.to_numeric(df.iloc[:, 6], errors='coerce').fillna(0) if cols_count > 6 else 0

        # 日付がどうしても取れない行を除外（ここでデータが消えていないかチェック）
        final_df = final_df.dropna(subset=['確定日付']).copy()
        st.write(f"📅 日付が正しく認識されたデータ: {len(final_df)} 行")

        if len(final_df) == 0:
            st.error("スプレッドシートの1列目または2列目から日付が読み取れませんでした。形式（2026/05/10など）を再確認してください。")
        else:
            # 週の計算（日曜始まり）
            final_df['週開始'] = final_df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
            final_df['週ラベル'] = final_df['週開始'].dt.strftime('%Y-%m-%d (日)〜')

            # 全週のリストを表示
            all_weeks = sorted(final_df['週ラベル'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", all_weeks)
            
            week_df = final_df[final_df['週ラベル'] == selected_week].copy().reset_index(drop=True)

            if not week_df.empty:
                st.write(f"### {selected_week} の集計")
                
                # 計算
                week_df['時給計算'] = week_df['時給'].values * week_df['勤務時間'].values
                week_df['歩合計算'] = week_df['個人売上'].values * week_df['歩合率'].values
                
                # 集計処理
                summary = week_df.groupby('名前').agg({
                    '勤務時間': 'sum', '個人売上': 'sum', '時給計算': 'sum', '歩合計算': 'sum'
                }).reset_index()

                summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
                summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

                st.dataframe(summary)
            else:
                st.info("この週に該当するデータはありません。")

        # 生データ確認用（トラブル時のみ展開）
        with st.expander("詳細な読み込み状況を確認"):
            st.write("スプレッドシートの生のカラム名:", list(df.columns))
            st.write("加工後のデータプレビュー:", final_df.head())
    else:
        st.warning("スプレッドシートからデータが読み込めません。")
