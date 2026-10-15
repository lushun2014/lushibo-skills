# 代理链路工程细节：协议 / 参数 / 调优 / 特征 / 排障

本文件是 `lushibo-proxy` 的技术参考。所有参数以 Xray-core 与 sing-box 的现行字段命名为准。

## 1. 协议握手与报文特征

### 1.1 VLESS + XTLS-Vision（TCP + TLS）

- 传输：TCP，外层标准 TLS，内层 VLESS。
- 关键参数：`flow` 必须为 `xtls-rprx-vision`，仅在 TCP + TLS/Reality 下有效；配 WS/gRPC 时该字段必须留空。
- 优势：Vision 在检测到内层为 TLS 时做"拼接透传"，避免二次加密带来的额外拷贝，吞吐提升明显（实测同机 20%-40%）。
- 暴露点：握手后前几个包的尺寸与真实 TLS 应用略有差异；启用 `xtls-rprx-vision` 但客户端版本不一致会直接断连。

### 1.2 VLESS + Reality

- 原理：客户端发起 ClientHello 时携带真实目标站点的 SNI，服务端把该站点的证书链与握手过程转发/借用，使探测者看到的是真实站点。
- 关键参数：`dest`（借用的真实站点，建议同区域、支持 TLS1.3、HTTP/2）、`serverNames`（与 dest 一致）、`privateKey`/`publicKey`（x25519 密钥对）、`shortIds`（客户端与服务端必须有一个交集）、`fingerprint`（建议 chrome）。
- 常见错误：`dest` 用 Cloudflare 背后站点导致握手异常；`shortId` 为空字符串时部分客户端拒绝；系统时间偏差导致握手失败。

### 1.3 Trojan

- 原理：外层标准 TLS，认证信息放在首个应用数据包的头部，认证失败则回落到真实站点。
- 关键参数：密码、SNI、`fallbacks`（回落目标，通常指向本机 Web 服务或 nginx）。
- 暴露点：回落站点若返回 502/空响应，主动探测即可识别。

### 1.4 Shadowsocks-2022

- 原理：AEAD-2022 加密，含时间戳与重放保护；无 TLS 外观。
- 关键参数：`method`（如 `2022-blake3-aes-128-gcm`）、`password`（base64 形式，长度需匹配 method）。
- 暴露点：无 TLS 外观，DPI 依据"高熵流量 + 无握手"特征即可标记；仅适合内层隧道。

### 1.5 Hysteria2 / TUIC（QUIC/UDP）

- 原理：基于 QUIC，自带拥塞控制（Hysteria2 使用 Brutal，可配置固定速率）。
- 关键参数：`up`/`down` 带宽声明（Brutal 必须填真实值，虚报会加剧丢包）、`obfs`（如 salamander，加一层混淆密码）、端口范围（端口跳跃）。
- 优势：丢包 5%-15% 的链路上吞吐显著优于 TCP 类协议。
- 暴露点：UDP 大流量本身易被 QoS；需端口跳跃 + obfs 降低识别率。

### 1.6 传输层对比

| 传输 | 依赖 | 过 CDN | 多路复用 | 备注 |
|---|---|---|---|---|
| TCP 裸 | 无 | 否 | 否 | 性能最好，特征最明显 |
| WS | HTTP/1.1 | 是 | 否 | 兼容性最好 |
| gRPC | HTTP/2 | 是 | 是 | serviceName 需两端一致 |
| HTTPUpgrade | HTTP/1.1 | 是 | 否 | WS 的替代，握手更简单 |
| mKCP | UDP | 否 | 否 | 抗丢包，流量放大 10%-30% |
| QUIC | UDP | 部分 | 是 | 需 CDN 支持 HTTP/3 |

## 2. 内核与系统调优参数

```
# 拥塞控制
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr

# 长肥管道缓冲
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# 连接队列
net.core.somaxconn = 32768
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_fastopen = 3

# 连接回收（高并发短连接场景）
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# 文件描述符（systemd 服务里另配 LimitNOFILE=65535）
fs.file-max = 1000000
```

MSS/MTU：隧道内层建议 `tcp_mss_clamp` 到 1380-1420；PPPoE 拨号环境取 1400 以下。判断方法：`ping -M do -s 1472 <target>` 逐级下降找到不分片的临界值，再减 40。

## 3. 性能诊断命令表

| 目的 | 命令 | 看什么 |
|---|---|---|
| 时延与丢包 | `mtr -rwzc 100 <host>` | 每跳丢包率与抖动 |
| 吞吐 | `iperf3 -c <host> -t 20 -P 4` | 单流/多流吞吐 |
| 路径 MTU | `ping -M do -s <size> <host>` | 何时开始分片 |
| 拥塞算法 | `sysctl net.ipv4.tcp_congestion_control` | 是否为 bbr |
| 连接状态 | `ss -s` 与 `ss -tn state established` | TIME_WAIT 与连接数 |
| 队列丢弃 | `tc -s qdisc show dev eth0` | dropped 计数是否增长 |
| TLS 握手 | `openssl s_client -connect <host>:443 -servername <sni>` | 证书链、协议版本、ALPN |
| 证书有效期 | `openssl x509 -enddate -noout -in <cert>` | 是否临近过期 |

## 4. 流量特征指标

用于自评链路"像不像正常流量"：

| 指标 | 采集方式 | 正常范围 | 异常信号 |
|---|---|---|---|
| 包长分布 | tcpdump 抓头部，按长度分桶 | 与应用协议匹配的双峰分布 | 大量固定长度包 |
| 握手扩展 | 抓 ClientHello 解析扩展列表 | 含 SNI/ALPN/密钥共享等常见扩展 | 扩展缺失或顺序异常 |
| JA3/JA4 | 指纹计算 | 与声称的浏览器一致 | 与 SNI 声明的客户端不符 |
| 心跳间隔 | 统计空闲期小包间隔 | 无规律 | 恒定 30/60 秒 |
| 上下行比 | 字节数统计 | 与应用一致 | 长期 1:1 且无下行请求 |
| 端口分布 | 连接目标端口统计 | 443/80 为主 | 长期固定冷门端口 |
| 首包时延 | 握手到首个数据包 | 与应用一致 | 异常稳定或异常快 |

自评流程：链路两端同时抓包 60 秒 → 导出包长与时间戳 → 与"同区域直连访问同一 SNI 站点"的流量对比 → 差异项即为整改项。

## 5. 排障命令表（按顺序）

| 步骤 | 命令 | 通过判据 |
|---|---|---|
| 1 本机直连 | `curl -sS -o /dev/null -w '%{http_code} %{time_total}' https://<目标>` | 返回 200 且时延正常 |
| 2 DNS | `dig +short <域名> @1.1.1.1` | 返回预期 IP，非污染地址 |
| 3 TCP | `nc -vz <host> <port>` | succeeded |
| 4 TLS | `openssl s_client -connect <host>:<port> -servername <sni> -brief` | 握手成功，协议与 ALPN 符合预期 |
| 5 时间同步 | `timedatectl` | 偏差 <30 秒 |
| 6 协议层 | 客户端日志开到 debug | 无"invalid user"/"unknown flow" |
| 7 路由规则 | 客户端路由日志 | 目标域名命中预期出口 |
| 8 出口 IP | 通过代理访问 IP 查询接口 | 返回落地 IP 而非本机 IP |
| 9 吞吐 | iperf3 经代理或大文件下载 | 达到 VPS 带宽的 60% 以上 |

## 6. 服务端加固清单

- SSH：禁用密码登录，改高位端口，限制来源 IP，开启 fail2ban。
- 防火墙：默认拒绝入站，仅放行 SSH 与代理端口；UDP 端口范围按需最小化。
- 服务隔离：代理进程用独立低权限用户运行，`NoNewPrivileges=true`、`ProtectSystem=strict`。
- 日志：只留连接元数据，7 天轮转；不落盘目标 URL。
- 备份：配置与证书定期备份到异地，备份中不含私钥明文时加密存放。
- 更新：内核与代理内核按月更新，更新前保留可回滚快照。

## 7. 使用边界

以上为通用网络传输工程内容。部署与使用需符合节点所在地、用户所在地的法律法规以及云服务商条款。
