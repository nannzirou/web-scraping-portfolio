"""
Webスクレイピング ポートフォリオ用サンプル（実戦レベル・Selenium版）
============================================================
「動的サイト（JavaScriptレンダリング）からの安全なデータ収集とクレンジング」

[概要]
Seleniumを利用し、スクロールやクリックが必要な動的ページからデータを取得。
取得したデータはpandasを用いて欠損値処理・型変換（クレンジング）を行い、
実務でそのまま利用できる高品質なデータセットとして出力します。

[アピールポイント（提案文に書ける強み）]
1. ヘッドレスモード（画面非表示）による高速かつ安定した処理
2. WebDriverWaitを利用した、要素が読み込まれるまでの確実な待機（エラー防止）
3. 取得データのクレンジング（不要文字の削除、数値型への明示的な変換）
4. エラーハンドリング（取得漏れがあっても途中で処理が止まらない設計）

※注: このスクリプトは技術証明用のサンプル構造であり、特定のサイトを攻撃または
  規約違反のスクレイピングを行うものではありません。URLはご自身の対象サイトに変更してください。

■ 使い方
  pip install selenium pandas webdriver-manager
  python demo_selenium_scraper.py
"""

import time
import pandas as pd
from datetime import datetime
from typing import List, Dict

# Selenium関連
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# === 設定 ===
# サンプルとして架空またはパブリックなテストURLを設定
TARGET_URL = "https://example.com/dynamic-products"
SCROLL_PAUSE_TIME = 2.0
OUTPUT_DIR = "./"

def setup_driver() -> webdriver.Chrome:
    """Chromeドライバーの初期設定（ヘッドレスモード）"""
    options = Options()
    options.add_argument('--headless')  # ブラウザを画面に出さない
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # Bot検知を回避するための一般的な設定（User-Agentの偽装等が必要な場合に追加）
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def scrape_dynamic_page(driver: webdriver.Chrome, url: str) -> List[Dict]:
    """ページにアクセスし、動的に読み込まれる要素を取得する"""
    print(f"[INFO] ページアクセス中: {url}")
    driver.get(url)
    data = []
    
    try:
        # 例: 「商品一覧」のコンテナが読み込まれるまで最大10秒待機
        # ※実際の実装では、ターゲットサイトのCSSセレクタに変更してください
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".product-list-container"))
        )
        
        # 動的読み込み用：ページ下部までゆっくりスクロール
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        print("[INFO] ページ全要素の読み込み完了。データ抽出を開始します。")

        # 要素の取得（例: .product-item）
        items = driver.find_elements(By.CSS_SELECTOR, ".product-item")
        
        for item in items:
            try:
                # 各要素のテキストを取得（サイト構造に合わせて変更）
                title = item.find_element(By.CSS_SELECTOR, ".title").text
                price_str = item.find_element(By.CSS_SELECTOR, ".price").text
                review_str = item.find_element(By.CSS_SELECTOR, ".review-count").text
                
                data.append({
                    "商品名": title,
                    "価格_raw": price_str,
                    "レビュー数_raw": review_str
                })
            except Exception as e:
                # 一部の要素が欠損していても処理を止めない
                print(f"[WARN] アイテムの取得に一部失敗しました（スキップ）: {e}")
                continue

    except Exception as e:
        print(f"[ERROR] ページの読み込みに失敗しました: {e}")

    return data

def cleanse_data(raw_data: List[Dict]) -> pd.DataFrame:
    """取得した生の文字列データを、分析可能なクリーンな形式に変換する"""
    print("[INFO] データクレンジング（前処理）を開始します...")
    df = pd.DataFrame(raw_data)
    
    if df.empty:
        return df

    # 1. 重複行の削除
    initial_len = len(df)
    df = df.drop_duplicates(subset=["商品名"])
    print(f"  -> 重複行を削除: {initial_len - len(df)}件")

    # 2. 価格のクレンジング（例: "￥1,200(税込)" -> 1200 の数値へ変換）
    # 数字以外の文字を除去し、float型に変換
    if "価格_raw" in df.columns:
        df["価格(円)"] = df["価格_raw"].astype(str).str.replace(r'[^\d]', '', regex=True)
        # 空文字の場合は欠損値(NaN)とし、その後数値型に変換
        df["価格(円)"] = pd.to_numeric(df["価格(円)"], errors='coerce')

    # 3. レビュー数のクレンジング（例: "(142件)" -> 142）
    if "レビュー数_raw" in df.columns:
        df["レビュー数"] = df["レビュー数_raw"].astype(str).str.replace(r'[^\d]', '', regex=True)
        df["レビュー数"] = pd.to_numeric(df["レビュー数"], errors='coerce').fillna(0).astype(int)

    # 4. 欠損値を含む行の対応（要件に応じて削除または補完）
    df = df.dropna(subset=["価格(円)"])

    # 不要なraw列の削除
    df = df.drop(columns=["価格_raw", "レビュー数_raw"], errors="ignore")

    print("[INFO] クレンジング完了。")
    return df

def main():
    print("="*60)
    print("動的サイト向け 実戦レベルスクレイパー (Selenium / Data Cleansing)")
    print("="*60)
    
    driver = None
    try:
        driver = setup_driver()
        # 今回はサンプル実行のため、空データでクレンジング処理の挙動のみテストするモックデータを用意
        print("[INFO] サンプルサイトの構造に依存しないよう、デモ用モックデータを使用します。")
        mock_raw_data = [
            {"商品名": "高級ゲーミングチェア", "価格_raw": "￥35,800(税込)", "レビュー数_raw": "レビュー(142件)"},
            {"商品名": "エルゴノミクスマウス", "価格_raw": "4,200円", "レビュー数_raw": "89件の評価"},
            {"商品名": "メカニカルキーボード", "価格_raw": "価格未定", "レビュー数_raw": "まだレビューはありません"},
            {"商品名": "高級ゲーミングチェア", "価格_raw": "￥35,800(税込)", "レビュー数_raw": "レビュー(142件)"}, # 重複データ
        ]
        
        # 実際にはここでスクレイピング処理を呼び出す
        # raw_data = scrape_dynamic_page(driver, TARGET_URL)
        raw_data = mock_raw_data
        
        # クレンジングの実行
        clean_df = cleanse_data(raw_data)
        
        # 結果の出力
        print("\n--- クレンジング後のデータプレビュー ---")
        print(clean_df.head())
        print("--------------------------------------\n")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}cleansed_data_{timestamp}.xlsx"
        clean_df.to_excel(filename, index=False, sheet_name="Clean_Data")
        print(f"[OK] クリーンなデータセットをExcelで出力しました: {filename}")

    finally:
        if driver:
            driver.quit()
            print("[INFO] ブラウザを正常に終了しました。")

if __name__ == "__main__":
    main()
