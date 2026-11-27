# 维护者发布流程

准备 Python 3.10 或更新版本、Node.js、Docker Compose 和 7-Zip 命令行 `7zz`。传入上一版已经脱敏的组合 ZIP、当前 GM 源码、游戏部署源码和匹配的 Windows 客户端目录。当前脚本通过 Git 凭据存储访问本仓库的 GitHub Release。

## 准备并自检

```sh
python3 release/prepare.py \
  --baseline <上版组合ZIP> --gm <后台源码目录> \
  --server-source <服务端Docker源码目录> --client <Windows客户端目录> \
  --work <本次新的工作目录>
```

如有额外的正式主机名或地址，使用 `--reject-file <本机私有文件>`，每行一个值。脚本用当前配置和该文件做精确扫描，只把脱敏文件及 SHA-256 写入输出目录。客户端名单、启动器和 Compose 库初始化模板位于本目录。

在新的 Compose 项目名和空卷上启动 `<本次新的工作目录>/kit/wendao163-compose`，为后台、登录和一线指定空闲端口。验证空服、角色工具和可达的游戏端口。客户端先用 7-Zip 测试全套分卷，再在 Windows 上使用 `Start-Client.cmd -ShowConnection` 核对配置并做实际登录。测试账号只建立在隔离项目中。

## 上传和公开

检查 README 和本次发布说明，提交并推送到 GitHub 的 `main`，然后运行下面的命令。先用 `--stage-only` 可只上传草稿。上传超时会单独重试该分卷，已核验的附件会在重试时复用。慢速网络可用 `--jobs 1` 逐卷上传。

```sh
python3 release/publish.py --tag v1.63.3 --assets <本次工作目录>/dist --notes <本次发布说明.md>
```

明确需要只留最新 Release 时再加 `--prune-older`。脚本会等新 Release 全部附件发布、摘要与公开下载链接均可核对后才清理先前 Release。Git 标签和历史提交可继续用于追踪。

服务器程序或种子有变更时，先独立制作并验证新的脱敏服务端基线，再把该版本的 ZIP 传给 `--baseline`。普通后台变更沿用上次基线即可。
