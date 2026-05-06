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
        # 重複列を削除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        
        # 【重要】列名を強制指定（2列目の「日付」を計算の主役にします）
        standard_names = ['タイムスタンプ', '選択日付', '名前', '時給', '勤務時間', '個人売上', '歩合率']
        rename_map = {df.columns[i]: standard_names[i] for i in range(min(len(df.columns), len(standard_names)))}
        df = df.rename(columns=rename_map)

        # 1. ユーザーが選んだ「選択日付」を日付形式に変換
        # もし空なら「タイムスタンプ」で補完する
        df['確定日付'] = pd.to_datetime(df['選択日付'], errors='coerce')
        df['確定日付'] = df['確定日付'].fillna(pd.to_datetime(df['タイムスタンプ'], errors='coerce'))
        
        # 2. 日付が取れなかった行を除外
        df = df.dropna(subset=['確定日付']).copy()
        
        # 3. 数値変換
        for col in ['時給', '勤務時間', '個人売上', '歩合率']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 4. 【週の計算ロジック】日曜から土曜を一つの塊にする
        # 日曜始まり：(x.weekday() + 1) % 7 を引くことで、その週の日曜日の日付を算出
        df['週開始日'] = df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
        df['週ラベル'] = df['週開始日'].dt.strftime('%Y-%m-%d (日)〜')

        # プルダウンの作成
        week_list = sorted(df['週ラベル'].unique(), reverse=True)
        
        if not week_list:
            st.warning("集計可能な日付データが見つかりません。")
        else:
            selected_week = st.selectbox("集計する週を選択してください", week_list)
            week_df = df[df['週ラベル'] == selected_week].copy().reset_index(drop=True)

            if not week_df.empty:
                st.write(f"### {selected_week} の集計")

                # 5. 計算（numpy形式で安全に）
                week_df['時給計算'] = week_df['時給'].to_numpy() * week_df['勤務時間'].to_numpy()
                week_df['歩合計算'] = week_df['個人売上'].to_numpy() * week_df['歩合率'].to_numpy()
                
                # 6. スタッフごとに集計
                summary = week_df.groupby('名前').agg({
                    '勤務時間': 'sum', 
                    '個人売上': 'sum', 
                    '時給計算': 'sum', 
                    '歩合計算': 'sum'
                }).reset_index()

                summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
                summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

                st.dataframe(summary[['名前', '勤務時間', '個人売上', '最終支給額', '計算方法']])

                st.divider()
                if not summary.empty:
                    target_staff = st.selectbox("詳細を確認するスタッフ", summary['名前'])
                    personal = summary[summary['名前'] == target_staff].iloc[0]
                    
                    st.write(f"#### {target_staff} さんの詳細")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("実働合計", f"{personal['勤務時間']}h")
                    c2.metric("売上合計", f"{int(personal['個人売上']):,}円")
                    c3.metric("確定給料", f"{int(personal['最終支給額']):,}円")
            else:
                st.info("データがありません。")
    else:
        st.warning("スプレッドシートを読み込めません。")
