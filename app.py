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
    
    # 【修正】ttl=0 を指定してキャッシュを無効化し、常に最新のスプレッドシートを読み込む
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 重複列の削除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        
        # 【修正】名前で列を特定する（位置がズレても大丈夫なように）
        # スプレッドシートの列名に含まれるキーワードで探します
        def find_col(keywords, default_idx):
            for col in df.columns:
                if any(k in str(col) for k in keywords):
                    return col
            return df.columns[default_idx] if len(df.columns) > default_idx else None

        col_map = {
            'timestamp': find_col(['タイムスタンプ'], 0),
            'date': find_col(['日付'], 1),
            'name': find_col(['名前'], 2),
            'salary': find_col(['時給'], 3),
            'hours': find_col(['勤務時間'], 4),
            'sales': find_col(['個人売上'], 5),
            'rate': find_col(['歩合率'], 6)
        }

        # 新しいデータフレームの構築
        final_df = pd.DataFrame()
        final_df['名前'] = df[col_map['name']]
        
        # 日付の確定（「日付」列を最優先、空なら「タイムスタンプ」）
        date_col = pd.to_datetime(df[col_map['date']], errors='coerce')
        time_col = pd.to_datetime(df[col_map['timestamp']], errors='coerce')
        final_df['確定日付'] = date_col.fillna(time_col)
        
        # 数値変換
        final_df['時給'] = pd.to_numeric(df[col_map['salary']], errors='coerce').fillna(0)
        final_df['勤務時間'] = pd.to_numeric(df[col_map['hours']], errors='coerce').fillna(0)
        final_df['個人売上'] = pd.to_numeric(df[col_map['sales']], errors='coerce').fillna(0)
        final_df['歩合率'] = pd.to_numeric(df[col_map['rate']], errors='coerce').fillna(0)

        # 日付がない行を削除
        final_df = final_df.dropna(subset=['確定日付']).copy()

        # 週のラベル作成
        final_df['週開始'] = final_df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
        final_df['週ラベル'] = final_df['週開始'].dt.strftime('%Y-%m-%d (日)〜')

        week_list = sorted(final_df['週ラベル'].unique(), reverse=True)
        
        if not week_list:
            st.warning("集計できる日付データがスプレッドシートに見つかりません。")
            # デバッグ用に読み込んだ列名を表示
            st.write("現在認識している列名:", list(df.columns))
        else:
            selected_week = st.selectbox("集計する週を選択してください", week_list)
            week_df = final_df[final_df['週ラベル'] == selected_week].copy().reset_index(drop=True)

            if not week_df.empty:
                st.write(f"### {selected_week} の集計")

                # 計算
                week_df['時給計算'] = week_df['時給'] * week_df['勤務時間']
                week_df['歩合計算'] = week_df['個人売上'] * week_df['歩合率']
                
                summary = week_df.groupby('名前').agg({
                    '勤務時間': 'sum', '個人売上': 'sum', '時給計算': 'sum', '歩合計算': 'sum'
                }).reset_index()

                summary['最終支給額'] = summary.apply(lambda x: max(x['時給計算'], x['歩合計算']), axis=1)
                summary['計算方法'] = summary.apply(lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1)

                st.dataframe(summary)

                st.divider()
                target_staff = st.selectbox("詳細を確認するスタッフ", summary['名前'])
                p = summary[summary['名前'] == target_staff].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("実働合計", f"{p['勤務時間']}h")
                c2.metric("売上合計", f"{int(p['個人売上']):,}円")
                c3.metric("確定給料", f"{int(p['最終支給額']):,}円")
    else:
        st.warning("スプレッドシートからデータが読み込めません。")
