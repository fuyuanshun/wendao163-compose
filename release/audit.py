"""检查待发布目录、嵌套归档和脱敏来源中的已知私有值，输出资产校验清单。"""
import argparse
from hashlib import sha256
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
import gzip
import json
import re
import tarfile

PRIVATE_KEY = re.compile(r'password|secret|token|hash|salt|public_ip|public_host|download_site_url', re.I)
FORBIDDEN = {'.git', '.env', 'private', 'node_modules', '__pycache__', 'crash', 'lastlogins.ini',
             'user.db', 'log', 'cptid.txt'}
CREDENTIAL = re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----')


def remember(values: dict[bytes, str], name: str, value: str) -> None:
    """仅记录足够长的实际值，测试失败只显示标签。"""
    if len(value) >= 8 and value not in ('127.0.0.1', '0.0.0.0'):
        values[value.encode()] = name
        hostname = urlsplit(value).hostname if value.startswith(('http://', 'https://')) else None
        if hostname and len(hostname) >= 8:
            values[hostname.encode()] = name


def known_values(gm: Path, game: Path) -> dict[bytes, str]:
    """从现用配置读取比对材料，不把任何私有值写进发布文件。"""
    values: dict[bytes, str] = {}
    for env in (game / '.env', game.parents[1] / '1.41/docker/.env', gm / 'frontend/.env.local'):
        if env.is_file():
            for line in env.read_text().splitlines():
                name, equal, value = line.partition('=')
                if equal and PRIVATE_KEY.search(name):
                    remember(values, name, value.strip().strip('"').strip("'"))
    config = json.loads((gm / 'private/config.json').read_text())

    def visit(item: object) -> None:
        """遍历分版本配置并收集敏感字段。"""
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(value, str) and PRIVATE_KEY.search(key):
                    remember(values, key, value)
                else:
                    visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)

    visit(config)
    for token in (gm / 'private').glob('*.token'):
        remember(values, token.name, token.read_text().strip())
    private_home = str(gm.resolve().parents[2])
    remember(values, '本地绝对路径', private_home + '/')
    # 系统配置可能使用不在当前 .env 中的宿主机地址，可额外指定拒绝匹配的值。
    return values


def inspect_tree(root: Path, needles: dict[bytes, str]) -> None:
    """对目录和内层 tar/gzip 成员扫描，发现私有内容即停止。"""
    def scan(name: str, stream) -> None:
        """块间保留足够前缀，避免跨块的凭据漏检。"""
        tail = b''
        overlap = max(256, max(map(len, needles), default=0))
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            chunk = tail + block
            hits = sorted({label for token, label in needles.items() if token in chunk})
            if len(chunk) < 16 * 1024 * 1024 and name.endswith(('.json', '.js', '.py', '.html', '.ini', '.sh', '.yaml', '.txt', '.md')):
                if CREDENTIAL.search(chunk):
                    hits.append('凭据格式')
            if hits:
                raise ValueError(f'{name} 匹配私有字段 {", ".join(hits)}')
            tail = chunk[-overlap:]

    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink() or FORBIDDEN.intersection(part.lower() for part in PurePosixPath(rel).parts):
            raise ValueError(f'发布目录包含禁止项：{rel}')
        if not path.is_file():
            continue
        if path.suffix.lower() in ('.token', '.pem', '.log', '.dmp', '.sqlite', '.sqlite3'):
            raise ValueError(f'发布目录包含私有文件类型：{rel}')
        if path.name.endswith('.tar.gz'):
            with tarfile.open(path, mode='r|gz') as archive:
                for member in archive:
                    inner = PurePosixPath(member.name)
                    if inner.is_absolute() or '..' in inner.parts:
                        raise ValueError(f'归档成员路径异常：{rel}')
                    if member.isfile() and (stream := archive.extractfile(member)):
                        with stream:
                            scan(f'{rel}!{member.name}', stream)
        else:
            opener = gzip.open if path.name.endswith('.gz') else open
            with opener(path, 'rb') as stream:
                scan(rel, stream)


def main() -> None:
    """同时检查发布的两棵目录及资产分卷大小，输出可公开的 SHA-256。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', required=True, type=Path)
    parser.add_argument('--client-stage', required=True, type=Path)
    parser.add_argument('--gm', required=True, type=Path)
    parser.add_argument('--server-source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reject-file', type=Path, help='可选，额外私有值每行一条，文件保留在本机')
    args = parser.parse_args()
    try:
        needles = known_values(args.gm.resolve(), args.server_source.resolve())
        if args.reject_file:
            for line in args.reject_file.read_text().splitlines():
                remember(needles, '额外私有值', line.strip())
        for stage in (args.kit, args.client_stage):
            if not stage.is_dir():
                raise ValueError(f'缺少已构建目录：{stage.name}')
            inspect_tree(stage, needles)
            print(f'{stage.name} 隐私扫描通过', flush=True)
        assets = [args.output / 'wendao163-compose.zip', *sorted(args.output.glob('wendao163-windows.7z.*'))]
        if len(assets) < 2 or any(not 0 < p.stat().st_size < 2**31 for p in assets):
            raise ValueError('缺少必需发行文件，或某分卷达到 GitHub 附件上限')
        with (args.output / 'SHA256SUMS').open('x', encoding='ascii') as checksums:
            for asset in assets:
                with asset.open('rb') as stream:
                    digest = sha256()
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        digest.update(block)
                checksums.write(f'{digest.hexdigest()}  {asset.name}\n')
        print('资产 SHA-256 清单已生成', flush=True)
    except (OSError, ValueError) as error:
        parser.exit(1, f'发行审计失败：{error}\n')


if __name__ == '__main__':
    main()
