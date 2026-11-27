"""白名单打包 1.63 Windows 客户端，生成 GitHub 可接受的 7z 分卷。"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess

TOP_EXTENSIONS = {'.dll', '.exe', '.mod', '.manifest', '.dbfs', '.dat', '.xmf'}
TOP_FILES = {'pwd32.sys', 'misc_res_text.ini', 'Wendao.ico', 'WebStarter.ini'}
ASSETS = {'data/autoui', 'data/char', 'data/swf', 'nf'}
REQUIRED = {'asktao.mod', 'char.dbfs', 'client.dbfs', 'data/team.html'}


def copy_file(source: Path, destination: Path) -> None:
    """只复制普通文件，源目录里的链接和用户状态不会跟随打包。"""
    if source.is_symlink() or not source.is_file():
        raise ValueError(f'不是可打包的普通文件：{source.name}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def prepare_client(source: Path, stage: Path) -> None:
    """复制固定类型的游戏资源，生成空白登录和更新配置。"""
    (stage / 'data').mkdir(parents=True)
    (stage / 'userdata').mkdir()
    for name in REQUIRED:
        if not (source / name).is_file():
            raise ValueError(f'缺少客户端必要文件：{name}')
    for path in sorted(source.iterdir()):
        if path.name in TOP_FILES or path.suffix.lower() in TOP_EXTENSIONS:
            copy_file(path, stage / path.name)
    for relative in sorted(ASSETS):
        directory = source / relative
        if directory.is_symlink():
            raise ValueError(f'资源目录不能是符号链接：{relative}')
        for path in sorted(directory.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'资源含符号链接：{path.relative_to(source)}')
            if path.is_file() and not any(part.startswith('.') for part in path.relative_to(source).parts):
                if path.suffix.lower() in {'.ini', '.txt', '.png', '.bmp',
                                             '.hi', '.gbits', '.cinfo', '.swf', '.dat', '.spr', '.dds', '.jpg', '.tga'}:
                    copy_file(path, stage / path.relative_to(source))
                else:
                    raise ValueError(f'资源目录出现未知文件类型：{path.relative_to(source)}')
    copy_file(source / 'data/team.html', stage / 'data/team.html')
    # 客户端由本包启动器传递地址、版本与端口，静态配置仅提供原始界面所需的空值。
    version = re.search(rb'(?m)^ver[ \t]*=[ \t]*([0-9.]+)[ \t]*\r?$', (source / 'data/Login.ini').read_bytes())
    if not version or not version[1].startswith(b'1.63'):
        raise ValueError('客户端配置未标明 1.63 版本')
    (stage / 'data/Login.ini').write_bytes(
        b'[USER]\r\nAddress=\r\nIP=127.0.0.1\r\nPortEx=8000\r\n[ErrorReport]\r\nFTPAddress=\r\n'
        b'[URL]\r\nNUM=0\r\nHelpHttp=\r\n[VERSION]\r\nver=' + version[1] + b'\r\n'
    )
    (stage / 'data/config.ini').write_bytes(b'[AutoUpdate]\r\nMustUpdate=0\r\n')
    (stage / 'Pages.ini').write_bytes(b'[Pages]\r\n')
    for path in sorted(Path(__file__).with_name('windows').iterdir()):
        if path.suffix in ('.cmd', '.ps1', '.example'):
            (stage / path.name).write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        else:
            copy_file(path, stage / path.name)


def main() -> None:
    """从显示指定的客户端目录生成可续传、可核验的独立归档。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seven-zip', default='7zz')
    args = parser.parse_args()
    stage = args.work.resolve() / 'wendao163-windows'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if stage.exists() or list(output.glob('wendao163-windows.7z.*')):
        parser.error('请使用新的客户端准备目录和输出目录')
    try:
        prepare_client(args.client.resolve(), stage)
        archive = output / 'wendao163-windows.7z'
        subprocess.run([args.seven_zip, 'a', '-t7z', '-m0=lzma2', '-mx=3', '-mmt=8', '-ms=off',
                        '-v1400m', '-bsp0', str(archive), stage.name], cwd=stage.parent, check=True)
        subprocess.run([args.seven_zip, 't', '-bsp0', str(archive) + '.001'], check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'客户端打包失败：{error}\n')


if __name__ == '__main__':
    main()
