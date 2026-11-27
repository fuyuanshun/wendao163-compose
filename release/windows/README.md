# 问道 1.63 Windows 客户端

把同一 Release 的全部 `wendao163-windows.7z.*` 放在同一目录，用 7-Zip 打开 `.001` 解压。双击 `Start-Client.cmd`。默认连接本机 `127.0.0.1:18101`。

服务端在同一台电脑且两个包解压在同一个父目录时，启动器会读取相邻 `wendao163-compose/.env` 中的 `SERVER_PUBLIC_IP` 和 `LOGIN_PORT`。服务端在另一台电脑时，把 `server.env.example` 另存为 `server.env`，填入 Windows 可访问的服务器 IPv4 和登录端口。第一个服务端连接会下发线路地址及端口，请按服务端 README 配置。

请先在管理台「账号与元宝」创建游戏账号，再通过客户端登录。连接错误时，可以在 PowerShell 中执行 `.\Start-Client.cmd -ShowConnection` 查看启动器会使用的地址。
