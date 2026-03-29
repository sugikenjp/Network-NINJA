FROM alpine:3.21

# tcpdump: パケットキャプチャ
# util-linux: GNU logger (--server / --port / --udp)
# wget: Manager への HTTP 通信（curl より軽量）
RUN apk add --no-cache tcpdump util-linux wget

COPY nn-agent.sh /usr/local/bin/nn-agent.sh
RUN chmod +x /usr/local/bin/nn-agent.sh

# 必須環境変数
# MANAGER_URL  : http://<manager-ip>:8080
# SYSLOG_SERVER: syslog 送信先 IP
# SYSLOG_PORT  : syslog 送信先ポート (default: 514)
# NODE_ID      : ノード識別子 (default: hostname)
# NODE_LABEL   : 表示名 (default: NODE_ID)

ENTRYPOINT ["/usr/local/bin/nn-agent.sh"]
