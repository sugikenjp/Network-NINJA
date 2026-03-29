#!/bin/sh
# Network-NINJA Agent
# - ICMPパケット監視 → syslog送信
# - Managerへのハートビート（30秒ごと）
# - Managerからの設定変更ポーリング（60秒ごと）

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

# NODE_ID を設定（未指定ならホスト名）
NODE_ID="${NODE_ID:-$(hostname)}"
NODE_LABEL="${NODE_LABEL:-$NODE_ID}"

# 設定ファイル（Manager配布設定の保存先）
CONFIG_FILE="/tmp/ninja_config"
echo "${SYSLOG_SERVER}:${SYSLOG_PORT}" > "$CONFIG_FILE"

export SYSLOG_SERVER SYSLOG_PORT NODE_ID NODE_LABEL MANAGER_URL CONFIG_FILE

echo "[*] Node ID    : $NODE_ID"
echo "[*] Manager    : $MANAGER_URL"
echo "[*] Syslog     : $SYSLOG_SERVER:$SYSLOG_PORT"

# ---------- Heartbeat ループ ----------
heartbeat_loop() {
  while true; do
    # 現在の設定を取得して送信
    CURRENT_IP=$(cut -d: -f1 "$CONFIG_FILE")
    CURRENT_PORT=$(cut -d: -f2 "$CONFIG_FILE")
    wget -q -O /dev/null \
      --header="Content-Type: application/json" \
      --post-data="{\"node_id\":\"$NODE_ID\",\"label\":\"$NODE_LABEL\",\"ip\":\"$NODE_ID\",\"syslog_ip\":\"$CURRENT_IP\",\"syslog_port\":$CURRENT_PORT}" \
      "${MANAGER_URL}/api/heartbeat" 2>/dev/null || true
    sleep 30
  done
}

# ---------- Config ポーリング ループ ----------
config_poll_loop() {
  while true; do
    sleep 60
    RESP=$(wget -q -O - "${MANAGER_URL}/api/config/${NODE_ID}" 2>/dev/null || echo "")
    if [ -z "$RESP" ]; then continue; fi

    # JSON パース（busybox の awk で軽量処理）
    NEW_IP=$(echo "$RESP"   | grep -oE '"syslog_ip"\s*:\s*"[^"]+"' | grep -oE '"[^"]+"\s*$' | tr -d '"' | tr -d ' ')
    NEW_PORT=$(echo "$RESP" | grep -oE '"syslog_port"\s*:\s*[0-9]+' | grep -oE '[0-9]+$')

    if [ -z "$NEW_IP" ] || [ -z "$NEW_PORT" ]; then continue; fi

    CURRENT=$(cat "$CONFIG_FILE")
    NEW="${NEW_IP}:${NEW_PORT}"

    if [ "$CURRENT" != "$NEW" ]; then
      echo "[*] Config updated: $CURRENT -> $NEW"
      echo "$NEW" > "$CONFIG_FILE"
      export SYSLOG_SERVER="$NEW_IP"
      export SYSLOG_PORT="$NEW_PORT"
      # tcpdump プロセスを再起動（PID を kill してメインループが再起動）
      kill "$(cat /tmp/watcher.pid 2>/dev/null)" 2>/dev/null || true
    fi
  done
}

# ---------- ICMP Watcher ループ ----------
watcher_loop() {
  while true; do
    CURRENT_IP=$(cut -d: -f1 "$CONFIG_FILE")
    CURRENT_PORT=$(cut -d: -f2 "$CONFIG_FILE")

    echo "[*] Starting watcher → syslog ${CURRENT_IP}:${CURRENT_PORT}"
    tcpdump -l -n -i any 'icmp[0] = 8 or icmp[0] = 0' 2>/dev/null &
    TCPDUMP_PID=$!
    echo "$TCPDUMP_PID" > /tmp/watcher.pid

    tcpdump -l -n -i any 'icmp[0] = 8 or icmp[0] = 0' 2>/dev/null | while read -r line; do
      SOURCE_IP=$(echo "$line" | grep -oE 'IP [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | awk '{print $2}')
      case "$line" in
        *"echo request"*) ICMP_TYPE="Echo Request" ;;
        *"echo reply"*)   ICMP_TYPE="Echo Reply"   ;;
        *)                ICMP_TYPE="Unknown"       ;;
      esac

      CUR_IP=$(cut -d: -f1 "$CONFIG_FILE")
      CUR_PORT=$(cut -d: -f2 "$CONFIG_FILE")
      logger --server "$CUR_IP" \
             --port   "$CUR_PORT" \
             --udp \
             --rfc3164 \
             "NINJA[$NODE_ID] ICMP ${ICMP_TYPE} from ${SOURCE_IP}. Full: ${line}"
    done

    # tcpdump が終了したら少し待って再起動
    echo "[*] Watcher exited, restarting..."
    sleep 2
  done
}

# ---------- 起動 ----------
heartbeat_loop &
config_poll_loop &
watcher_loop
