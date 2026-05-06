import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- Googleスプレッドシートへの接続設定 ---
conn = st.connection("google_sheets", type=GSheetsConnection)

# --- サイドバー ---
st.sidebar.title("メニュー")
mode = st.sidebar.radio("機能を選択", ["日々の入力をする", "1週間の集計を出す"])

# ---------------------------------------------------------
# モード1：日々の入力をする
# ---------------------------------------------------------
if mode == "日々の入力をする":
    st.title("📝 今日の出勤データを記入")
    
    with st.form("input_form", clear_on_submit=True):
        # カレンダーで日付を選択（一昨日の分などもここで指定可能）
        input_date = st.date_input("日付", datetime.now())
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
                try:
                    # 1. 現在の全データを読み込む
                    existing_data = conn.read(ttl=0)
                    
                    # 2. 新しい行をデータフレームとして作成
                    new_row_df = pd.DataFrame([{
                        "タイムスタンプ": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
                        "日付": input_date.strftime("%Y/%m/%d"),
                        "名前": name,
                        "時給": hourly_rate,
                        "勤務時間": hours,
                        "売上": sales,
                        "歩合率": comm_rate
                    }])
                    
                    # 3. 既存のデータと新しい行を結合
                    updated_df = pd.concat([existing_data, new_row_df], ignore_index=True)
                    
                    # 4. スプレッドシート全体を更新（これが最もエラーが少ない方法です）
                    conn.update(data=updated_df)
                    
                    st.cache_data.clear()
                    st.success(f"{name}さんのデータを保存しました！")
                    st.balloons()
                except Exception as e:
                    st.error("保存に失敗しました。")
                    with st.expander("詳細なエラー内容"):
                        st.exception(e)
# ---------------------------------------------------------
# モード2：1週間の集計を出す
# ---------------------------------------------------------
elif mode == "1週間の集計を出す":
    st.title("📊 スタッフ別・週次集計")
    
    df_raw = conn.read(ttl=0) 
    
    if df_raw is not None and not df_raw.empty:
        # 重複削除
        df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
        
        st.info(f"スプレッドシートから {len(df)} 行読み込みました。")

        cols_count = len(df.columns)
        processed_rows = []

        for i in range(len(df)):
            try:
                # 0番目がタイムスタンプ、1番目が選択した日付
                raw_ts = str(df.iat[i, 0])
                raw_date = str(df.iat[i, 1]) if cols_count > 1 else ""
                
                # B列（日付）を優先、なければA列（TS）
                parsed_date = pd.to_datetime(raw_date, errors='coerce')
                if pd.isna(parsed_date):
                    parsed_date = pd.to_datetime(raw_ts, errors='coerce')
                
                if pd.isna(parsed_date):
                    continue
                    
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

        if final_df.empty:
            st.error("有効なデータが1件も見つかりませんでした。")
        else:
            # 週の計算（日曜始まり）
            final_df['週開始'] = final_df['確定日付'].apply(lambda x: x - pd.Timedelta(days=(x.weekday() + 1) % 7))
            final_df['週ラベル'] = final_df['週開始'].dt.strftime('%Y-%m-%d (日)〜')

            st.success(f"{len(final_df)} 件のデータを処理しました！")

            all_weeks = sorted(final_df['週ラベル'].unique(), reverse=True)
            selected_week = st.selectbox("集計する週を選択してください", all_weeks)
            
            week_df = final_df[final_df['週ラベル'] == selected_week].copy()

            if not week_df.empty:
                week_df['時給計算'] = week_df['時給'].astype(float) * week_df['勤務時間'].astype(float)
                week_df['歩合計算'] = week_df['個人売上'].astype(float) * week_df['歩合率'].astype(float)
                
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
