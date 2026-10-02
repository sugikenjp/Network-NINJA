# Network-NINJA

- Network-NINJA はネットワーク内に設置したセンターにより、特定の通信（主に不正な通信）を検知するシステムです
- ネットワーク機器の余剰リソースでの実現を目指しています
- 検知にあたっては、ネットワークの設計から組み込む必要があります（セキュリティバイデザイン）

```
[ネットワーク機器A]          [ネットワーク機器B]
 └─ ninja-agent               └─ ninja-agent
      │ Heartbeat (30s)             │ Heartbeat (30s)
      │ Filter poll (60s)           │ Filter poll (60s)
      │ Captured traffic → syslog UDP │ Captured traffic → syslog UDP
      └──────────────┬──────────────┘
                     ▼
             [Manager サーバ]
              ninja-manager
              ├─ Web UI   :8080
              ├─ REST API :8080
              └─ Syslog   :514/udp
```

---

## ディレクトリ構成

```
Network-NINJA/
├── manager/
│   ├── NN-Manager.py       # Flask アプリ本体
│   ├── Dockerfile
│   └── Docker-compose
└── agent/
    ├── nn-agent.sh         # Agent エントリポイント
    └── Dockerfile
```

---

## Manager の起動

### Docker で起動（推奨）

```bash
cd manager/
docker compose up -d
```

Web UI: http://<manager-ip>:8080

### bare metal / VM で起動

```bash
pip install flask
DB_PATH=./ninja.db WEB_PORT=8080 SYSLOG_PORT=5514 python3 NN-Manager.py
```

> ポート 514 は root 権限が必要です。非 root の場合は `SYSLOG_PORT=5514` を使用してください。

---

## Agent の起動

各ネットワーク機器で以下を実行します。

### 1. イメージをビルド

```bash
cd agent/
docker build -t ninja-agent .
```

### 2. コンテナを起動

```bash
docker run -d \
  --name ninja-agent \
  --restart unless-stopped \
  --cap-add=NET_RAW \
  --cap-add=NET_ADMIN \
  --network=host \
  -e MANAGER_URL="http://192.168.1.100:8080" \
  -e SYSLOG_SERVER="192.168.1.100" \
  -e SYSLOG_PORT="514" \
  -e NODE_ID="agent-sw01" \
  -e NODE_LABEL="Switch-01 (1F)" \
  ninja-agent
```

> `--network=host` を使うとホストの全インターフェースを監視できます。  
> macvlan で特定 NIC に参加させたい場合は `--network=<macvlan_network_name>` に変更してください。

### 環境変数一覧

| 変数 | 必須 | 説明 | 例 |
|------|------|------|----|
| MANAGER_URL   | ✓ | Manager の URL | `http://192.168.1.100:8080` |
| SYSLOG_SERVER | ✓ | syslog 送信先 IP（通常は Manager と同じ） | `192.168.1.100` |
| SYSLOG_PORT   |   | syslog 送信先ポート（省略時 514） | `514` |
| NODE_ID       |   | ノード識別子（省略時: hostname） | `agent-sw01` |
| NODE_LABEL    |   | Manager UI の表示名 | `Switch-01 (1F)` |

### ログ確認・停止

```bash
# ログ確認
docker logs -f ninja-agent

# 停止
docker stop ninja-agent

# 削除
docker rm ninja-agent
```

---

## キャプチャフィルタの設定

Manager の Web UI **[ FILTER CONFIG ]** タブから、Agent がキャプチャするトラフィックを選択できます。

| プロトコル | 説明 |
|------------|------|
| ICMP | Ping（Echo Request / Echo Reply） |
| 80/tcp | HTTP |
| 443/tcp | HTTPS |
| 445/tcp | SMB |

選択後に **「Apply to All Agents」** を押すと設定が保存されます。  
各 Agent は 60 秒以内に設定を取得し、tcpdump フィルタを自動更新・再起動します。

何も選択しない場合は ICMP のみキャプチャします（デフォルト動作）。

---

## REST API リファレンス

| Method | Path | 説明 |
|--------|------|------|
| POST   | /api/heartbeat | Agent からの死活報告 |
| GET    | /api/nodes | ノード一覧取得 |
| DELETE | /api/nodes/:id | ノード削除 |
| GET    | /api/syslogs | syslog ログ取得（?q=検索&source=IP&limit=件数） |
| GET    | /api/syslogs/count | ログ総件数 |
| GET    | /api/filter | 現在のキャプチャフィルタ設定を取得 |
| POST   | /api/filter | キャプチャフィルタ設定を更新 |
| GET    | /api/config/:node_id | Agent がフィルタ設定をポーリング |

### フィルタ設定の例

```bash
# 現在の設定を確認
curl http://manager:8080/api/filter

# ICMP + HTTPS を有効にする
curl -X POST http://manager:8080/api/filter \
  -H "Content-Type: application/json" \
  -d '{"icmp": true, "tcp80": false, "tcp443": true, "tcp445": false}'
```

---

## フィルタ変更の仕組み

1. Manager の Web UI で対象プロトコルを選択し「Apply to All Agents」
2. Manager DB（`settings` テーブル）にフィルタ設定が保存される
3. 各 Agent は 60 秒ごとに `GET /api/config/<node_id>` をポーリング
4. 変更を検知したら tcpdump を新しい BPF フィルタで再起動

---

## ノードのステータス判定

| 状態 | 条件 |
|------|------|
| ONLINE  | 最終ハートビートから 2 分以内 |
| OFFLINE | 最終ハートビートから 2 分超過 |

---

## データ永続化

SQLite（`/data/ninja.db`）に以下を保存します。

- `nodes` テーブル: ノード情報・最終確認時刻
- `syslogs` テーブル: 受信ログ全件
- `settings` テーブル: キャプチャフィルタ設定
