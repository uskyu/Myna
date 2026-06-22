<div align="center">

# 🐦 Myna

**複数の AI エージェントがグループチャットで連携して作業するプラットフォーム**

タスクを一つ投稿するだけで、開発・テスト・レビュー・運用エージェントが自動的に @メンションでバトンを渡し合い、実際のツールを呼び出して結果を出力します。  
セルフホスト型、Hermes Agent ベース、メモリ・スキル・完全なツール実行に対応。

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Vue 3](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](docker-compose.yml)
[![オンラインデモ](https://img.shields.io/badge/🎬_オンラインデモ-見る-2d6a4f?style=flat)](https://uskyu.github.io/myna-demo/)
[![Windows](https://img.shields.io/badge/Windows-ポータブル版_(ベータ)-0078D4?logo=windows)](https://github.com/uskyu/myna/releases/latest)

</div>

---

## これは何？

**Myna = AI エージェントがグループチャット内で協力して作業するプラットフォーム**

「また別の ChatGPT ラッパー」ではありません。代わりに：

- 開発・テスト・レビュー・運用エージェントを一つのグループチャットルームに招待
- 一言送るだけ：「サーバーのバージョンを確認して更新して」
- 開発エージェントが自動的に運用エージェントを @メンション → 運用エージェントが SSH でバージョンを確認 → 報告エージェントが結果をまとめて返信
- 全自動リレー、ツールは実際に実行（terminal / file / browser / cron）

[Hermes Agent](https://github.com/NousResearch/hermes-agent) をベースに構築し、Hermes のツール呼び出し・メモリ・スキル・委譲機能を活用した上で、以下を追加拡張：

- グループチャット形式の協調 UI、@メンションリレー
- 自動引き継ぎルール：誰が次に担当するか、いつ引き継ぐか、ノイズをどう抑制するか
- 自律進化：複数ステップの操作後に自動でスキルを抽出、使えば使うほど賢くなる
- Docker ワンコマンドデプロイ + Windows ポータブル版

---

## コア機能

**一言送るだけで、複数の AI エージェントが自動的に役割分担し、バトンを渡し、ツールを呼び出し、結果を出します。**

<div align="center">
  <img src="docs/architecture.svg" width="700" alt="エージェントチェーン協調フロー" />
</div>

---

## 実際の動作

### チェーン協調：開発 → テスト → 修正

![チェーン協調](docs/screenshots/chain-workflow.jpg)

### チェーンチャットのトリガー

![チェーンチャット](docs/screenshots/chain-chat.jpg)

### 自律進化：スキルの自動抽出

![自律進化](docs/screenshots/self-improve.jpg)

---

## 機能一覧

> **🎬 [オンラインデモ](https://uskyu.github.io/myna-demo/)** — チェーン協調・自動引き継ぎルール・リアルタイムストリーミング出力の動的デモを確認

- <img src="docs/icons/chain.svg" width="16" align="absmiddle"/> **エージェントチェーン協調** — @メンションで次のエージェントを自動トリガー、無限リレー
- <img src="docs/icons/brain.svg" width="16" align="absmiddle"/> **自律進化学習** — 複数ステップ操作後にスキルを自動抽出、重複除去＋品質フィルタリングで使うほど賢くなる
- <img src="docs/icons/globe.svg" width="16" align="absmiddle"/> **完全カスタム API** — 任意の OpenAI 互換エンドポイントに対応、モデルとプロバイダーを自由に選択
- <img src="docs/icons/tool.svg" width="16" align="absmiddle"/> **完全なツール機能** — ターミナルコマンド、ファイル読み書き、HTTP リクエスト、コード検索
- <img src="docs/icons/zap.svg" width="16" align="absmiddle"/> **Hermes Agent エンジン** — tools / memory / skills / delegation フルスタック
- <img src="docs/icons/lock.svg" width="16" align="absmiddle"/> **パスワード保護** — 公開デプロイに安全、JWT セッション＋セルフサービスパスワード変更
- <img src="docs/icons/check.svg" width="16" align="absmiddle"/> **承認モード** — auto / confirm / manual の 3 段階実行モード
- <img src="docs/icons/activity.svg" width="16" align="absmiddle"/> **リアルタイムストリーミング** — WebSocket プッシュ、ツール呼び出しプロセスを可視化
- <img src="docs/icons/package.svg" width="16" align="absmiddle"/> **Docker ワンコマンドデプロイ** — SQLite、ゼロ設定、`docker compose up -d` で完了
- <img src="docs/icons/monitor.svg" width="16" align="absmiddle"/> **デスクトップ＋モバイル** — レスポンシブレイアウト、両プラットフォームで一貫した体験

---

## クイックスタート

### 方法 1：Windows ポータブル版（Windows ユーザー推奨）

> ⚠️ **現在ベータ版** — Windows 版は引き続き改善中で、パス互換性や依存関係の読み込みに問題が生じる場合があります。本番環境には Docker デプロイを推奨します。

**ダウンロード：** [GitHub Releases](https://github.com/uskyu/myna/releases/latest)

2 種類のパッケージを提供：
- **`Myna-Setup-x64.exe`** — インストーラー、データディレクトリとデスクトップショートカットを自動設定
- **`Myna-Windows-x64.zip`** — ポータブル版、解凍してすぐ使える、インストール不要

**インストーラーの使い方：**
1. `Myna-Setup-x64.exe` をダウンロードして実行
2. インストールパスを選択（デフォルト：`%LOCALAPPDATA%\Programs\Myna`）
3. インストール完了後に自動起動、ブラウザで `http://localhost:3456` を開く
4. 初回ログインパスワード：`admin123`

**ポータブル版の使い方：**
1. `Myna-Windows-x64.zip` をダウンロードして任意のディレクトリに解凍
2. `start-myna.bat` をダブルクリックして起動
3. ブラウザが自動的に `http://localhost:3456` を開く
4. 初回ログインパスワード：`admin123`

**サービスの停止：** `stop-myna.bat` をダブルクリック、または起動ウィンドウで `Ctrl+C` を押す

**データディレクトリ：** `%APPDATA%\Myna`（データベース、アップロードファイル、ワークスペース、ログを含む）

---

### 方法 2：Docker Compose（Linux / macOS 推奨）

```bash
git clone https://github.com/uskyu/myna.git
cd myna
docker compose up -d
```

Myna コンテナ（SQLite）を自動起動、`http://localhost:3456` でアクセス

Docker デプロイはデフォルトで名前付きボリュームでデータを永続化：
- `app_db`：チャット履歴、グループチャット、エージェント設定、ログインセッション
- `app_data`：アップロードされた添付ファイル、グループチャット共有ワークスペース `/app/data/workspaces`
- `hermes_profiles`：各エージェントの Hermes メモリ、スキル、設定

オンライン更新は成熟した外部アップデーターパターンを採用：Myna は設定ページからアップデートリクエストを送るだけで、実際のイメージ取得とコンテナの再構築は Watchtower が行い、アプリコンテナが「自分自身を置き換える」問題を回避。

イメージのアップグレード・コンテナの再構築では、Docker volumes を手動で削除しない限りデータは消去されません。

> MySQL が必要な場合は `docker compose -f docker-compose.mysql.yml up -d` を使用

### 方法 3：ローカル実行（開発・ソースデプロイ）

```bash
git clone https://github.com/uskyu/myna.git
cd myna/backend
pip install -r requirements.txt
PORT=3456 python3 main.py
```

フロントエンドはビルド済み、`http://localhost:3456` に直接アクセス

**デフォルトパスワード：** `admin123`（ログイン後に設定で変更可能）

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド | Python 3.11 + FastAPI |
| フロントエンド | Vue 3 + Vite |
| データベース | SQLite（デフォルト）/ MySQL 8.0（Docker） |
| AI エンジン | [Hermes Agent](https://github.com/NousResearch/hermes-agent) |
| 通信 | WebSocket（リアルタイムストリーミング） |
| 認証 | Session Token + SHA-256 |
| デプロイ | Docker Compose + GHCR / Windows ポータブル版 |

---

## プロジェクト構造

```
myna/
├── backend/          # FastAPI バックエンド
│   ├── main.py       # エントリーポイント + WebSocket + Auth ミドルウェア
│   ├── ai_engine.py  # Hermes Agent + チェーン呼び出し + 自律進化
│   ├── db.py         # SQLite / MySQL デュアルエンジンアダプター
│   └── routes/       # API ルート
├── frontend/         # Vue 3 ソース
│   └── src/
├── src/web/public/   # ビルド済みフロントエンドアセット
├── docker-compose.yml
├── Dockerfile
└── docs/             # ドキュメント + スクリーンショット
```

---

## ライセンス

本プロジェクトは [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) でオープンソース公開されています。

これが意味すること：
- ✅ 自由に使用・修正・デプロイできます
- ✅ 商用利用も可能です
- ⚠️ 修正したコードは同じライセンスでオープンソース化する必要があります
- ⚠️ ネットワーク経由でサービスを提供する場合もソースコードの公開が必要です

### 商用ライセンス

AGPL-3.0 の条件があなたの使用ケースに合わない場合（クローズドソース商用デプロイ、SaaS 統合など）、WeChat QR コードをスキャンして作者に連絡してください：

<div align="center">
  <img src="docs/wechat-qr.jpg" width="200" alt="WeChat で作者に連絡" />
</div>

### コミュニティ

<div align="center">
  <img src="docs/screenshots/wechat-group.jpg" width="200" alt="WeChat コミュニティグループ" />
</div>

---

<div align="center">
  <sub>Built with ❤️ by <a href="https://github.com/uskyu">uskyu</a></sub>
</div>
