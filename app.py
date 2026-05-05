import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 共通設定：データの保存先
DATA_FILE = 'bar_history.csv'

# ファイルがなければ作成
if not os.path.exists(DATA_FILE):
    df_init = pd.DataFrame(columns=['日付', '名前', '時給', '勤務時間', '個人売上', '歩合率'])
    df_init.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- サイドバーで機能を切り替え ---
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
                new_row = pd.DataFrame([[date, name, hourly_rate, hours, sales, comm_rate]], 
                                       columns=['日付', '名前', '時給', '勤務時間', '個人売上', '歩合率'])
                new_row.to_csv(DATA_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
                st.success(f"{name}さんのデータを記録しました！")

# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # 日付データをPythonが理解できる「日付型」に変換
        df['日付'] = pd.to_datetime(df['日付'])
        
        if not df.empty:
            # --- 週（日〜土）のラベルを作る ---
            # 日曜日を週の始まり(0)として、その週の「日曜日」の日付を計算
            df['週'] = df['日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
            df['週'] = df['週'].dt.strftime('%Y-%m-%d (日)〜')

            # --- 画面で「週」を選択 ---
            week_list = sorted(df['週'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", week_list)
            
            # 選択された週のデータだけに絞り込む
            week_df = df[df['週'] == selected_week].copy()

            st.write(f"### {selected_week} の集計")

            # --- スタッフごとにグループ化して計算 ---
            week_df['時給計算'] = week_df['時給'] * week_df['勤務時間']
            week_df['歩合計算'] = week_df['個人売上'] * week_df['歩合率']
            
            # スタッフごとに集計（groupby）
            staff_summary = week_df.groupby('名前').agg({
                '勤務時間': 'sum',
                '個人売上': 'sum',
                '時給計算': 'sum',
                '歩合計算': 'sum'
            }).reset_index()

            # 最終的な支給額を判定（週の合計で比較）
            staff_summary['最終支給額'] = staff_summary.apply(
                lambda x: max(x['時給計算'], x['歩合計算']), axis=1
            )
            staff_summary['計算方法'] = staff_summary.apply(
                lambda x: "歩合" if x['歩合計算'] > x['時給計算'] else "時給保障", axis=1
            )

            # 結果を表示
            st.dataframe(staff_summary[['名前', '勤務時間', '個人売上', '最終支給額', '計算方法']])

            # スタッフを個別に詳しく見る
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