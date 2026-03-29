# Network-NINJA

- Netwok-NINJAはネットワーク内に設置したセンターにより、特定の通信（主に不正な通信）を検知するシステムです
- ネットワーク機器の余剰リソースでの実現を目指しています
- 検知にあたっては、ネットワークの設計から組み込む必要があります（セキュリティバイデザイン）

```
[ネットワーク機器A]          [ネットワーク機器B]
 └─ ninja-agent               └─ ninja-agent
      │ Heartbeat (30s)             │ Heartbeat (30s)
      │ Config poll (60s)           │ Config poll (60s)
      │ ICMP → syslog UDP           │ ICMP → syslog UDP
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
ninja-manager/
├── manager/
│   ├── app.py              # Flask アプリ本体
│   ├── Dockerfile
│   └── docker-compose.yml
└── agent/
    ├── agent.sh            # Agent エントリポイント
    ├── Dockerfile
    └── docker-compose.yml
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
DB_PATH=./ninja.db WEB_PORT=8080 SYSLOG_PORT=5514 python3 app.py
```

> ポート514はroot権限が必要です。非rootの場合は `SYSLOG_PORT=5514` を使用してください。

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
| SYSLOG_SERVER | ✓ | syslog 送信先 IP | `192.168.1.100` |
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

## REST API リファレンス

| Method | Path | 説明 |
|--------|------|------|
| POST   | /api/heartbeat | Agent からの死活報告 |
| GET    | /api/nodes | ノード一覧取得 |
| DELETE | /api/nodes/:id | ノード削除 |
| GET    | /api/syslogs | syslogログ取得（?q=検索&source=IP&limit=件数） |
| GET    | /api/syslogs/count | ログ総件数 |
| POST   | /api/config/deploy | 設定一括配布 |
| GET    | /api/config/:node_id | Agent が設定をポーリング |

### 設定一括配布の例

```bash
curl -X POST http://manager:8080/api/config/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "node_ids": ["agent-sw01", "agent-sw02"],
    "syslog_ip": "192.168.1.200",
    "syslog_port": 514
  }'
```

---

## 設定変更の仕組み

1. Manager の Web UI で新しい Syslog IP/Port を入力し「Deploy」
2. Manager DB に新設定が保存される
3. 各 Agent は 60 秒ごとに `GET /api/config/<node_id>` をポーリング
4. 変更を検知したら `icmp-watcher` を新設定で再起動

---

## ノードのステータス判定

| 状態 | 条件 |
|------|------|
| ONLINE  | 最終ハートビートから2分以内 |
| OFFLINE | 最終ハートビートから2分超過 |

---

## データ永続化

SQLite（`/data/ninja.db`）に以下を保存します。

- `nodes` テーブル: ノード情報・最終確認時刻・設定
- `syslogs` テーブル: 受信ログ全件
- `config_templates` テーブル: 配布履歴
