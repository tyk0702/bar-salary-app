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
    
    # 1. データの読み込み
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 2. 【最重要】名前ではなく「列の順番」でデータを強制的に抜き出す
        # スプレッドシートの左から順に並んでいる前提で、新しいデータフレームを再構築します
        # これにより、名前の重複や化けによるエラーを物理的に回避します
        
        # 必要な列の番号（0=タイムスタンプ, 1=名前, 2=時給, 3=勤務時間, 4=個人売上, 5=歩合率）
        # 列が足りない場合に備えて、存在する分だけ取得
        num_actual_cols = len(df_raw.columns)
        temp_df = pd.DataFrame()
        
        standard_names = ['タイムスタンプ', '名前', '時給', '勤務時間', '個人売上', '歩合率']
        
        for i, name in enumerate(standard_names):
            if i < num_actual_cols:
                # df.iloc[:, i] で「i番目の列」を強制取得。これなら名前が重複していても1列しか取れません。
                temp_df[name] = df_raw.iloc[:, i]
            else:
                temp_df[name] = 0

        df = temp_df.copy()

        # 3. 型変換を「確実に1列ずつ」実行
        df['タイムスタンプ'] = pd.to_datetime(df['タイムスタンプ'], errors='coerce')
        df = df.dropna(subset=['タイムスタンプ']).copy()
        
        for col in ['時給', '勤務時間', '個人売上', '歩合率']:
            # Series（1列）であることを保証して数値化
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 4. 週の計算
        df['週'] = df['タイムスタンプ'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
        df['週'] = df['週'].dt.strftime('%Y-%m-%d (日)〜')

        week_list = sorted(df['週'].unique(), reverse=True)
        selected_week = st.selectbox("集計する週を選択してください", week_list)
        
        # 抽出（ここでも index をリセットして安全性を高める）
        week_df = df[df['週'] == selected_week].copy().reset_index(drop=True)

        if not week_df.empty:
            st.write(f"### {selected_week} の集計")

            # 5. 計算（ラベル不一致を避けるため numpy 配列として計算）
            week_df['時給計算'] = week_df['時給'].to_numpy() * week_df['勤務時間'].to_numpy()
            week_df['歩合計算'] = week_df['個人売上'].to_numpy() * week_df['歩合率'].to_numpy()
            
            # 6. スタッフごとに集計
            summary = week_df.groupby('名前').agg({
                '勤務時間': 'sum', 
                '個人売上': 'sum', 
                '時給計算': 'sum', 
                '歩合計算': 'sum'
            }).reset_index()

            # 給料の決定（時給保障 vs 歩合）
            summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
            summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

            # 表示
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
            st.info("この週にデータはありません。")
    else:
        st.warning("スプレッドシートを読み込めません。")
