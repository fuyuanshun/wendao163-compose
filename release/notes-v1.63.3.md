## 下载

- **`wendao163-compose.zip`** 包含 1.63 一线游戏服、MySQL 空服种子与 Web 管理台。解压后运行 `docker compose up -d --build`。
- **`wendao163-windows.7z.001` 至 `.003`** 是可选的 Windows 1.63 客户端。下载全部分卷，放在一起，用 7-Zip 从 `.001` 解压，双击 `Start-Client.cmd`。
- **`SHA256SUMS`** 用于核对以上附件。

## 连接和功能

同一台电脑部署时客户端默认连到 `127.0.0.1:18101`。局域网部署时，把服务端的 `SERVER_PUBLIC_IP` 设置为玩家可访问的 IPv4，按压缩包内 README 配置客户端与端口。

「角色管理」集中提供角色属性、已有宠物、任务管理、日常重置、好友亲密度和物品发放。任务管理支持一键补齐大飞前置，已有元婴或血婴的角色会沿用原形态。

已有安装可在原目录升级并沿用原卷。升级后执行一次 `docker compose exec mysql bash /entry/install-full-flight.sh`，即可为旧卷补装大飞所需过程。新安装自动完成这一步。
