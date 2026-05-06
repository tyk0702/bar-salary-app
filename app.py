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
    
    df = conn.read(ttl=0) 
    
    if df is not None and not df.empty:
        # 【修正】列名を強制的に整える（1列目:タイムスタンプ, 2列目:名前 ...）
        # 列数が足りない場合のエラーを回避
        new_cols = ['タイムスタンプ', '名前', '時給', '勤務時間', '個人売上', '歩合率']
        current_cols = list(df.columns)
        
        # 存在する列数分だけ名前を上書きする
        rename_dict = {current_cols[i]: new_cols[i] for i in range(min(len(current_cols), len(new_cols)))}
        df = df.rename(columns=rename_dict)

        # 日付変換
        df['タイムスタンプ'] = pd.to_datetime(df['タイムスタンプ'], errors='coerce')
        df = df.dropna(subset=['タイムスタンプ']) # 日付がない行は消す
        
        # 週の計算
        df['週'] = df['タイムスタンプ'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
        df['週'] = df['週'].dt.strftime('%Y-%m-%d (日)〜')

        week_list = sorted(df['週'].unique(), reverse=True)
        selected_week = st.selectbox("集計する週を選択してください", week_list)
        week_df = df[df['週'] == selected_week].copy()

        st.write(f"### {selected_week} の集計")

        # 【重要修正】数値変換を安全に行う
        for col in ['時給', '勤務時間', '個人売上', '歩合率']:
            if col in week_df.columns:
                # 1列ずつ確実にシリーズ（列データ）として渡す
                week_df[col] = pd.to_numeric(week_df.loc[:, col], errors='coerce').fillna(0)
            else:
                week_df[col] = 0  # 列がなければ0で埋める

        # 集計計算
        week_df['時給計算'] = week_df['時給'] * week_df['勤務時間']
        week_df['歩合計算'] = week_df['個人売上'] * week_df['歩合率']
        
        # 名前がない行を除外して集計
        if '名前' in week_df.columns:
            staff_summary = week_df.groupby('名前').agg({
                '勤務時間': 'sum', '個人売上': 'sum', '時給計算': 'sum', '歩合計算': 'sum'
            }).reset_index()

            staff_summary['最終支給額'] = staff_summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
            staff_summary['計算方法'] = staff_summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

            st.dataframe(staff_summary[['名前', '勤務時間', '個人売上', '最終支給額', '計算方法']])

            st.divider()
            target_staff = st.selectbox("詳細を確認するスタッフ", staff_summary['名前'])
            personal_data = staff_summary[staff_summary['名前'] == target_staff].iloc[0]
                
            st.write(f"#### {target_staff} さんの詳細")
            c1, c2, c3 = st.columns(3)
            c1.metric("実働合計", f"{personal_data['勤務時間']}h")
            c2.metric("売上合計", f"{int(personal_data['個人売上']):,}円")
            c3.metric("確定給料", f"{int(personal_data['最終支給額']):,}円")
        else:
            st.error("スプレッドシートに '名前' のデータが見つかりません。")

    else:
        st.warning("まだデータが読み込めません。フォームから1件テスト送信してみてください。")
