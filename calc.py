import argparse

import pandas as pd

from salary import calculate_salary, to_number


def main() -> None:
    parser = argparse.ArgumentParser(description="BARの給料CSVを計算します。")
    parser.add_argument("input", nargs="?", default="bar_history.csv", help="入力CSV")
    parser.add_argument("-o", "--output", default="salary_result.csv", help="出力CSV")
    args = parser.parse_args()

    df = pd.read_csv(args.input, encoding="utf-8")
    required_columns = ["名前", "時給", "勤務時間", "個人売上", "歩合率"]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise SystemExit(f"必要な列がありません: {', '.join(missing_columns)}")

    for column in ["時給", "勤務時間", "個人売上", "歩合率"]:
        df[column] = df[column].apply(to_number)

    df["支給額"] = df.apply(
        lambda row: calculate_salary(row["時給"], row["勤務時間"], row["個人売上"], row["歩合率"]),
        axis=1,
    )

    print("--- 個別計算結果 ---")
    if df.empty:
        print("データがありません。")
    else:
        print(df[["名前", "勤務時間", "個人売上", "支給額"]])

    print("\n--- 合計 ---")
    print(f"総勤務時間: {df['勤務時間'].sum()} 時間")
    print(f"総個人売上: {int(df['個人売上'].sum()):,} 円")
    print(f"総支給額: {int(df['支給額'].sum()):,} 円")

    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n計算結果を '{args.output}' に保存しました。")


if __name__ == "__main__":
    main()
