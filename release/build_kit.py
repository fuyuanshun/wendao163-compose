"""从上次脱敏安装包和当前后台源码构建 1.63 组合版候选。"""
import argparse
from pathlib import Path, PurePosixPath
import os
import shutil
import subprocess
import zipfile

KIT_NAME = 'wendao163-compose'
HERE = Path(__file__).resolve().parent
FRONTEND_INPUTS = ('src', 'index.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'vite.config.ts')


def extract_baseline(baseline: Path, work: Path) -> Path:
    """校验上次发布的 ZIP 条目，只允许在本次目录内解压。"""
    with zipfile.ZipFile(baseline) as archive:
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            if not path.parts or path.parts[0] != KIT_NAME or '..' in path.parts or '\\' in item.filename:
                raise ValueError('基线包存在异常路径')
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('基线包存在符号链接')
            archive.extract(item, work)
        # ZIP 解压不会恢复权限，MySQL 初始化脚本必须可被容器读取。
    kit = work / KIT_NAME
    for script in kit.rglob('*.sh'):
        script.chmod(0o755)
    return kit


def copy_frontend(gm: Path, workspace: Path, kit: Path) -> None:
    """在空前端目录构建，避免把个人的 Vite 环境和下载站地址编译进去。"""
    target = workspace / 'frontend'
    target.mkdir()
    source = gm / 'frontend'
    for name in FRONTEND_INPUTS:
        path = source / name
        if path.is_dir():
            shutil.copytree(path, target / name, ignore=shutil.ignore_patterns('.DS_Store', '*.env', '.env.*'))
        else:
            shutil.copyfile(path, target / name)
    env = {key: value for key, value in os.environ.items() if not key.startswith('VITE_')}
    env['VITE_DOWNLOAD_SITE_URL'] = ''
    subprocess.run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=target, env=env, check=True)
    subprocess.run(['npm', 'run', 'build'], cwd=target, env=env, check=True)
    dest = kit / 'gm/frontend/dist'
    shutil.rmtree(dest)
    shutil.copytree(target / 'dist', dest)


def refresh_backend(gm: Path, kit: Path) -> None:
    """只从后端源码、1.63 资源目录和依赖声明更新管理台。"""
    public = kit / 'gm'
    for directory, pattern in (('app', '*.py'), ('data/catalog', '163*'), ('data/equipment', '163*')):
        for path in sorted((gm / directory).glob(pattern)):
            if path.is_file() and not path.is_symlink():
                shutil.copyfile(path, public / directory / path.name)
    # 任务页的共用门派历史读取旧版规则表，独立 1.63 安装也需要它。
    shutil.copyfile(gm / 'data/catalog/141-tasks.json', public / 'data/catalog/141-tasks.json')
    shutil.copyfile(gm / 'requirements.txt', public / 'requirements.txt')


def install_migration(kit: Path) -> None:
    """让新安装初始化大飞 SQL，旧卷可用相同脚本补装。"""
    for name in ('install-full-flight.sh', 'install-full-flight.sql'):
        dest = kit / 'database' / name
        shutil.copyfile(HERE / 'database' / name, dest)
        if name.endswith('.sh'):
            dest.chmod(0o755)
    init = kit / 'database/init/40-gm-web.sh'
    text = init.read_text()
    command = '/entry/install-full-flight.sh'
    if command not in text:
        init.write_text(text.rstrip() + f'\nbash {command}\n')
    compose = kit / 'compose.yaml'
    text = compose.read_text()
    mount = '      - ./database/init:/docker-entrypoint-initdb.d:ro\n'
    if mount not in text:
        raise ValueError('基线 Compose 缺少 MySQL 初始化挂载')
    if command not in text:
        extra = ''.join(f'      - ./database/{name}:/entry/{name}:ro\n'
                        for name in ('install-full-flight.sh', 'install-full-flight.sql'))
        compose.write_text(text.replace(mount, mount + extra, 1))


def package(kit: Path, output: Path) -> None:
    """对组合包逐项压缩并重新测 CRC，跳过桌面生成的临时文件。"""
    files = sorted(path for path in kit.rglob('*') if path.is_file() and path.name != '.DS_Store')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
        for path in files:
            archive.write(path, path.relative_to(kit.parent).as_posix())
    with zipfile.ZipFile(output) as archive:
        if (damaged := archive.testzip()) is not None:
            raise ValueError(f'组合压缩包无法完整解压：{damaged}')


def main() -> None:
    """使用上次的无状态数据和明确指定的后台源码准备候选，不触碰运行卷。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--gm', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    workspace = args.work.resolve()
    output = args.output.resolve()
    try:
        workspace.mkdir(parents=True)
        output.mkdir(parents=True, exist_ok=True)
        kit = extract_baseline(args.baseline.resolve(), workspace)
        refresh_backend(args.gm.resolve(), kit)
        install_migration(kit)
        shutil.copyfile(HERE / 'kit-readme.md', kit / 'README.md')
        copy_frontend(args.gm.resolve(), workspace, kit)
        package(kit, output / (KIT_NAME + '.zip'))
        print(f'组合版候选已生成，可从 {kit} 启动隔离验证。', flush=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'组合版打包失败：{error}\n')


if __name__ == '__main__':
    main()
