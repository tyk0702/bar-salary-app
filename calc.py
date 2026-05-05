import pandas as pd

# 1. CSVファイルを読み込む（ファイル名は適宜変えてください）
# encoding='utf-8' でエラーが出る場合は 'shift-jis' に変えてみてください
df = pd.read_csv('bar.csv', encoding='utf-8')

# 2. 給料計算のロジックを作成
def calculate_salary(row):
    # A案：時給計算（時給 × 勤務時間）
    hourly_pay = row['時給'] * row['勤務時間']
    
    # B案：売上歩合（個人売上 × 歩合率）
    # 歩合率は 0.1 (10%) のような数値を想定
    commission_pay = row['個人売上'] * row['歩合率']
    
    # 高い方を採用
    final_pay = max(hourly_pay, commission_pay)
    return final_pay

# 3. 新しい列「支給額」を追加して計算を実行
df['支給額'] = df.apply(calculate_salary, axis=1)

# 4. 結果を表示
print("--- 個別計算結果 ---")
print(df[['名前', '勤務時間', '個人売上', '支給額']])

print("\n--- 1週間の合計 ---")
print(f"総勤務時間: {df['勤務時間'].sum()} 時間")
print(f"総個人売上: {df['個人売上'].sum()} 円")
print(f"総支給額: {df['支給額'].sum()} 円")

# 5. 結果を新しいCSVとして保存（オーナーに渡す用）
df.to_csv('salary_result.csv', index=False, encoding='utf-8-sig')
print("\n計算結果を 'salary_result.csv' に保存しました！")