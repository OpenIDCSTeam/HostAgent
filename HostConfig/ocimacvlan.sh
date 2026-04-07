#!/bin/bash
set -e
MACVLAN_IF="macvlan_forward"
PHYS_IF="enp6s18"
HOST_IP="192.168.6.30/24"
DOCKER_NET_NAME="macvlan"

echo "------ macvlan自动路由事件监听脚本启动 ------"
echo "[DEBUG] MACVLAN_IF=macvlan_forward"
echo "[DEBUG] PHYS_IF=enp6s18"
echo "[DEBUG] HOST_IP=192.168.6.30/24"
echo "[DEBUG] DOCKER_NET_NAME=macvlan"
if ip link show "$MACVLAN_IF" >/dev/null 2>&1; then
  echo "macvlan接口 $MACVLAN_IF 已存在"
else
  echo "创建macvlan接口: ip link add $MACVLAN_IF link $PHYS_IF type macvlan mode bridge"
  ip link add "$MACVLAN_IF" link "$PHYS_IF" type macvlan mode bridge
fi

if ip addr show dev "$MACVLAN_IF" | grep -q "${HOST_IP%/*}"; then
  echo "macvlan接口 $MACVLAN_IF 已配置IP ${HOST_IP%/*}"
else
  echo "为 $MACVLAN_IF 添加IP $HOST_IP"
  ip addr add "$HOST_IP" dev "$MACVLAN_IF"
fi

ip link set "$MACVLAN_IF" up

sync_routes() {
  # 用awk从docker network inspect获取所有容器的IPv4地址，并去除掩码部分
  CONTAINER_IPS_WITH_MASK=$(docker network inspect "$DOCKER_NET_NAME" -f '{{range .Containers}}{{.IPv4Address}} {{end}}')
  CONTAINER_IPS=""
  for ip in $CONTAINER_IPS_WITH_MASK; do
    CONTAINER_IPS="$CONTAINER_IPS ${ip%%/*}"
  done
  ROUTE_IPS=$(ip route | grep "dev $MACVLAN_IF" | awk '{print $1}')
  for ip in $CONTAINER_IPS; do
    if echo "$ROUTE_IPS" | grep -qx "$ip"; then
      echo "路由 $ip 已存在，跳过"
    else
      echo "添加路由 $ip 到 $MACVLAN_IF"
      ip route add "$ip" dev "$MACVLAN_IF"
    fi
  done
  for ip in $ROUTE_IPS; do
    # 只删除形式为纯IP（没有/的），不删除类似192.168.6.0/24网段路由
    if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && ! echo "$CONTAINER_IPS" | grep -qx "$ip"; then
      echo "删除已失效路由 $ip from $MACVLAN_IF"
      ip route del "$ip" dev "$MACVLAN_IF" || true
    fi
  done
}

echo "启动时同步所有容器的路由..."
sync_routes

docker events --filter event=start --filter event=connect --filter event=disconnect --filter event=die --filter event=destroy --filter network="$DOCKER_NET_NAME" | \
while read -r event; do
  echo "检测到docker网络事件，重新同步所有路由..."
  sync_routes
done