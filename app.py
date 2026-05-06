import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import requests  # ← フォーム送信に必要

# --- Googleスプレッドシートへの接続設定（読み込み用） ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- サイドバー ---
st.sidebar.title("メニュー")
mode = st.sidebar.radio("機能を選択", ["日々の入力をする", "1週間の集計を出す"])

# ---------------------------------------------------------
# モード1：日々の入力をする
# ---------------------------------------------------------
if mode == "日々の入力をする":
    st.title("📝 今日の出勤データを記入")
    
    with st.form("input_form"):
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
                # --- フォーム送信による書き込み処理 ---
                # あなたが取得したURLをもとに設定
                form_url = "https://docs.google.com/forms/d/e/1FAIpQLSc8Ost1yA_FAtXskdxt_8twu6vigBE3FEXBkH8Hw8rF8FRikw/formResponse"
                
                params = {
                    "entry.474978113": name,           # 名前
                    "entry.223259871": hourly_rate,    # 時給
                    "entry.1496582745": hours,          # 勤務時間
                    "entry.640486226": sales,          # 個人売上
                    "entry.1975425774": comm_rate,     # 歩合率
                    # 日付はフォーム側に項目がない場合はスプレッドシート側の「タイムスタンプ」で代用するか、
                    # フォームに日付項目を追加してIDを紐付けてください
                }
                
                try:
                    response = requests.post(form_url, data=params)
                    if response.status_code == 200:
                        st.success(f"{name}さんのデータを送信しました！")
                        st.balloons()
                        # キャッシュをクリアして最新データが読み込まれるようにする
                        st.cache_data.clear()
                    else:
                        st.error("送信に失敗しました。")
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    # スプレッドシートから読み込む（ttl=0で常に最新を取得）
    df = conn.read(ttl=0) 
    
    if not df.empty:
        # スプレッドシートの「タイムスタンプ」列を「日付」として使う設定
        # もしスプレッドシートに「日付」という列が別にあるなら、適宜書き換えてください
        date_column = 'タイムスタンプ' if 'タイムスタンプ' in df.columns else '日付'
        
        df[date_column] = pd.to_datetime(df[date_column])
        
        # 週の開始日（日曜日）を計算
        df['週'] = df[date_column].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
        df['週'] = df['週'].dt.strftime('%Y-%m-%d (日)〜')

        week_list = sorted(df['週'].unique(), reverse=True)
        selected_week = st.selectbox("集計する週を選択してください", week_list)
        week_df = df[df['週'] == selected_week].copy()

        st.write(f"### {selected_week} の集計")

        # 列名がフォーム送信で日本語になっている場合を想定
        # df.columnsを確認して、必要に応じて修正してください
        col_name = '名前' if '名前' in df.columns else 'entry.474978113' # 以下同様
        
        # 集計計算
        week_df['時給計算'] = week_df['時給'] * week_df['勤務時間']
        week_df['歩合計算'] = week_df['個人売上'] * week_df['歩合率']
        
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
        c2.metric("売上合計", f"{personal_data['個人売上']:,}円")
        c3.metric("確定給料", f"{personal_data['最終支給額']:,}円")
            
        st.write(f"※ 時給合計({personal_data['時給計算']:,}円) と 歩合合計({personal_data['歩合計算']:,}円) を比較して高い方を採用しています。")

    else:
        st.warning("まだデータがありません。")
