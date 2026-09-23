#!/bin/sh
# Network-NINJA Agent
# - tcpdump でパケット監視 → syslog 送信
# - Manager へのハートビート（30 秒ごと）
# - Manager からのフィルタ設定ポーリング（60 秒ごと）

# ---------- 引数チェック ----------
if [ -z "$MANAGER_URL" ]; then
  echo "Error: MANAGER_URL not set." >&2
  echo "Example: MANAGER_URL=http://192.168.1.1:8080" >&2
  exit 1
fi
if [ -z "$SYSLOG_SERVER" ]; then
  echo "Error: SYSLOG_SERVER not set." >&2
  exit 1
fi
SYSLOG_PORT="${SYSLOG_PORT:-514}"

NODE_ID="${NODE_ID:-$(hostname)}"
NODE_LABEL="${NODE_LABEL:-$NODE_ID}"

# フィルタ設定ファイル（Manager から取得したフィルタ式を保存）
FILTER_FILE="/tmp/ninja_filter"
DEFAULT_FILTER="(icmp[0] = 8 or icmp[0] = 0)"
echo "$DEFAULT_FILTER" > "$FILTER_FILE"

echo "[*] Node ID  : $NODE_ID"
echo "[*] Manager  : $MANAGER_URL"
echo "[*] Syslog   : $SYSLOG_SERVER:$SYSLOG_PORT"
echo "[*] Filter   : $DEFAULT_FILTER"

# ---------- フィルタ文字列を構築 ----------
# 引数: Manager の /api/config/<node_id> レスポンス全体
build_filter() {
  RESP="$1"
  PARTS=""

  if echo "$RESP" | grep -q '"icmp"[[:space:]]*:[[:space:]]*true'; then
    PARTS="(icmp[0] = 8 or icmp[0] = 0)"
  fi
  if echo "$RESP" | grep -q '"tcp80"[[:space:]]*:[[:space:]]*true'; then
    PARTS="${PARTS:+$PARTS or }tcp port 80"
  fi
  if echo "$RESP" | grep -q '"tcp443"[[:space:]]*:[[:space:]]*true'; then
    PARTS="${PARTS:+$PARTS or }tcp port 443"
  fi
  if echo "$RESP" | grep -q '"tcp445"[[:space:]]*:[[:space:]]*true'; then
    PARTS="${PARTS:+$PARTS or }tcp port 445"
  fi

  # 何も選択されていない場合はデフォルト（ICMP）を維持
  echo "${PARTS:-$DEFAULT_FILTER}"
}

# ---------- Heartbeat ループ ----------
heartbeat_loop() {
  while true; do
    wget -q -O /dev/null \
      --header="Content-Type: application/json" \
      --post-data="{\"node_id\":\"$NODE_ID\",\"label\":\"$NODE_LABEL\",\"ip\":\"$NODE_ID\"}" \
      "${MANAGER_URL}/api/heartbeat" 2>/dev/null || true
    sleep 30
  done
}

# ---------- フィルタ設定ポーリング ループ ----------
config_poll_loop() {
  while true; do
    sleep 60
    RESP=$(wget -q -O - "${MANAGER_URL}/api/config/${NODE_ID}" 2>/dev/null || echo "")
    if [ -z "$RESP" ]; then continue; fi

    NEW_FILTER=$(build_filter "$RESP")
    CURRENT_FILTER=$(cat "$FILTER_FILE")

    if [ "$CURRENT_FILTER" != "$NEW_FILTER" ]; then
      echo "[*] Filter updated: $NEW_FILTER"
      echo "$NEW_FILTER" > "$FILTER_FILE"
      # watcher の tcpdump を停止 → watcher_loop が新フィルタで再起動する
      kill "$(cat /tmp/watcher.pid 2>/dev/null)" 2>/dev/null || true
    fi
  done
}

# ---------- Watcher ループ ----------
watcher_loop() {
  while true; do
    CURRENT_FILTER=$(cat "$FILTER_FILE")
    echo "[*] Starting watcher: $CURRENT_FILTER -> syslog ${SYSLOG_SERVER}:${SYSLOG_PORT}"

    # named pipe でパイプライン全体を制御（PID を確実に kill するため）
    rm -f /tmp/ninja_pipe
    mkfifo /tmp/ninja_pipe

    # tcpdump を起動し named pipe へ書き込み（PID を保存）
    tcpdump -l -n -i any "$CURRENT_FILTER" > /tmp/ninja_pipe 2>/dev/null &
    echo $! > /tmp/watcher.pid

    # named pipe から読み込み → syslog 送信
    while read -r line; do
      SOURCE_IP=$(echo "$line" | grep -oE 'IP [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk '{print $2}')
      case "$line" in
        *"echo request"*) MSG_TYPE="ICMP-Echo-Request" ;;
        *"echo reply"*)   MSG_TYPE="ICMP-Echo-Reply"   ;;
        *" http "*)       MSG_TYPE="HTTP"              ;;
        *" https "*)      MSG_TYPE="HTTPS"             ;;
        *" microsoft-ds"*) MSG_TYPE="SMB"              ;;
        *)                MSG_TYPE="Traffic"           ;;
      esac
      logger --server "$SYSLOG_SERVER" \
             --port   "$SYSLOG_PORT" \
             --udp \
             --rfc3164 \
             "NINJA[$NODE_ID] ${MSG_TYPE} from ${SOURCE_IP:-?}. Full: ${line}"
    done < /tmp/ninja_pipe

    # tcpdump が終了（フィルタ変更による kill または異常終了）→ 再起動
    wait "$(cat /tmp/watcher.pid 2>/dev/null)" 2>/dev/null || true
    echo "[*] Watcher exited, restarting..."
    sleep 2
  done
}

# ---------- 起動 ----------
heartbeat_loop &
config_poll_loop &
watcher_loop
