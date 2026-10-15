# 蓝队细则：日志字段 / 检测规则 / 取证 / 时间线 / 加固

本文件是 `lushibo-bluesec` 的字段与命令参考。

## 1. Windows 安全日志关键事件

| EventID | 含义 | 关键字段 | 检测价值 |
|---|---|---|---|
| 4624 | 登录成功 | LogonType、IpAddress、TargetUserName、LogonProcessName | 基线比对、异常时段 |
| 4625 | 登录失败 | Status、SubStatus、IpAddress | 爆破、密码喷洒 |
| 4648 | 显式凭据登录 | TargetServerName、SubjectUserName | 横向移动 |
| 4672 | 授予特权 | SubjectUserName、PrivilegeList | 提权 |
| 4688 | 进程创建 | NewProcessName、CommandLine、ParentProcessName | 执行链（需开启命令行审计） |
| 4698 | 计划任务创建 | TaskName、TaskContent | 持久化 |
| 4720 | 创建账户 | TargetUserName、SubjectUserName | 后门账号 |
| 4728/4732 | 加入特权组 | MemberName、GroupName | 提权 |
| 7045 | 服务安装 | ServiceName、ImagePath、ServiceType | 持久化 |
| 1102 | 审计日志被清除 | SubjectUserName | 反取证 |

Sysmon 补充：1 进程创建、3 网络连接、7 镜像加载、8 远程线程创建、10 进程访问、11 文件创建、12/13 注册表、22 DNS 查询。

## 2. Linux 日志字段

| 来源 | 行样例 | 提取字段 |
|---|---|---|
| sshd 失败 | `Failed password for invalid user root from 1.2.3.4 port 55123 ssh2` | 用户、来源 IP、端口、是否 invalid |
| sshd 成功 | `Accepted publickey for deploy from 1.2.3.4 port 40222 ssh2` | 用户、来源 IP、认证方式 |
| sudo | `sudo: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash` | 主体、目标用户、命令 |
| su | `su: pam_unix(su:session): session opened for user root by alice(uid=1000)` | 提权链 |
| auditd execve | `type=EXECVE ... argc=3 a0="curl" a1="-s" a2="http://..."` | 命令行重组 |

审计规则建议（auditd）：

```
-a always,exit -F arch=b64 -S execve -k exec_track
-w /etc/passwd -p wa -k identity
-w /etc/cron.d/ -p wa -k cron
-w /root/.ssh/ -p wa -k sshkey
-a always,exit -F arch=b64 -S connect -k net_conn
```

## 3. 检测规则模板（可直接改字段）

**BL-001 暴力破解**

```yaml
title: SSH 暴力破解
id: BL-001
logsource: {product: linux, service: sshd}
detection:
  sel: {message: 'Failed password'}
  timeframe: 60s
  condition: sel | count() by src_ip > 5
level: medium
```

**BL-004 特权命令执行（Linux）**

```yaml
title: sudo 执行下载或临时目录命令
id: BL-004
logsource: {product: linux, service: sudo}
detection:
  sel:
    COMMAND|contains:
      - 'curl '
      - 'wget '
      - 'chmod +x'
      - 'base64 -d'
      - '/tmp/'
      - 'nc -e'
  condition: sel
level: high
```

**BL-007 可疑服务安装（Windows）**

```yaml
title: 服务二进制位于用户可写目录
id: BL-007
logsource: {product: windows, service: security}
detection:
  sel:
    EventID: 7045
    ImagePath|contains:
      - '\Users\'
      - '\ProgramData\'
      - '\Temp\'
      - '\Public\'
  condition: sel
level: critical
```

## 4. 取证采集清单

**易失性数据（先做，顺序即优先级）**

1. 系统时间、时区、运行时长
2. 进程列表：PID、PPID、用户、命令行、启动时间、可执行路径
3. 网络：连接、监听端口、ARP、路由、DNS 缓存
4. 登录会话：who、last、logon sessions
5. 内核模块与服务状态
6. 计划任务、启动项、WMI 订阅
7. 剪贴板、最近打开文件、浏览器历史（按授权）

**非易失性数据**

- 磁盘镜像（或至少：系统目录、临时目录、Web 根目录、用户目录、日志目录）
- 注册表导出（Run、Services、WMI、IFEO）
- 事件日志原始 evtx
- Web 与应用日志、数据库审计日志
- 内存镜像（若未在易失阶段完成）

**证据登记表字段**：编号、文件名、来源主机、采集时间（含时区）、采集人、工具与版本、大小、SHA-256、存放路径、是否原件。

## 5. 时间线字段口径

| 字段 | 口径 | 注意 |
|---|---|---|
| 时间 | 统一转 UTC+8 展示，同时保留原始时区标记 | 跨时区证据必转 |
| 来源 | 主机名 + 日志类型 + 行号 | 便于回溯 |
| 主体 | 账号 / 进程（含 PID）/ IP | 三者都要 |
| 动作 | 登录、执行、写入、连接、创建、删除 | 用动词 |
| 证据 | 哈希或日志原文片段 | 可复现 |
| 判定 | 确认（≥2 独立来源）/ 疑似（1 来源）/ 待验证 | 不许含糊 |

## 6. 持久化点核查命令

| 类型 | Windows | Linux |
|---|---|---|
| 服务 | `Get-Service` + 注册表 Services 键 | `systemctl list-units --type=service` |
| 计划任务 | `schtasks /query /fo LIST /v` | `crontab -l`、`/etc/cron*`、systemd timer |
| 启动项 | Run/RunOnce 键、启动目录 | `~/.bashrc`、`/etc/profile.d/`、rc.local |
| WMI | `Get-WmiObject -Namespace root\subscription -Class __EventFilter` | 不适用 |
| 账号 | `net user`、`Get-LocalUser` | `/etc/passwd`、`/etc/shadow` 修改时间 |
| 密钥 | 授权密钥文件、证书存储 | `~/.ssh/authorized_keys` |
| Web 后门 | IIS 模块、应用目录新增文件 | Web 根目录新增文件、`.htaccess` |

## 7. 加固检查命令（可判定）

| 项 | 检查命令 | 合格判据 |
|---|---|---|
| Windows 审计策略 | `auditpol /get /category:*` | 登录、账户管理、进程创建为"成功和失败" |
| 命令行审计 | 注册表 ProcessCreationIncludeCmdLine_Enabled | 值为 1 |
| 日志保留 | `wevtutil gl Security` | maxSize ≥ 1GB 且 retention 合理 |
| SSH 配置 | `sshd -T` | PermitRootLogin no、PasswordAuthentication no |
| 内核参数 | `sysctl -a` | 无 IP 转发（除非路由器）、无 core dump |
| 账户审计 | `awk -F: '$3>=1000' /etc/passwd` | 与人员名单一一对应 |
| 时钟同步 | `timedatectl status` | 已同步，偏差 <1 秒 |
| 出站限制 | 防火墙规则导出 | 默认拒绝出站或白名单模式 |

## 8. 使用边界

本 skill 面向自有或已获授权的资产做检测与响应。取证与处置需遵守所在司法辖区的证据规则与隐私法规。
