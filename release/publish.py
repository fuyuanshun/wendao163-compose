"""把已校验的组合包和客户端上传到 GitHub 草稿，核对后公开并可选清理旧 Release。"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
import argparse
import json
import os
import re
import subprocess

REPO = 'fuyuanshun/wendao163-compose'
API = f'https://api.github.com/repos/{REPO}'


def git(*args: str) -> str:
    """只读取本地 Git 元信息，不将认证信息放进命令参数。"""
    return subprocess.check_output(['git', *args], text=True).strip()


def credentials() -> dict[str, str]:
    """使用既有 GitHub 凭据存储，仅在 API 请求头中传送令牌。"""
    result = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, text=True,
                            capture_output=True, check=True)
    fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if not fields.get('password'):
        raise ValueError('现有 Git 凭据存储没有可用的 GitHub 凭据')
    return {'Authorization': 'Bearer ' + fields['password'], 'Accept': 'application/vnd.github+json',
            'User-Agent': 'wendao-compose-release', 'X-GitHub-Api-Version': '2022-11-28'}


def request(headers: dict, method: str, url: str, body: dict | None = None) -> object:
    """发送管理 API 请求，错误只记录状态和 GitHub 公开消息。"""
    head = {**headers, 'Content-Type': 'application/json'} if body is not None else headers
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urlopen(Request(url, data=data, headers=head, method=method), timeout=60) as response:
            return None if response.status == 204 else json.load(response)
    except HTTPError as error:
        try:
            message = json.load(error).get('message', '')
        except ValueError:
            message = ''
        raise ValueError(f'GitHub 返回 HTTP {error.code} {message}') from None


def releases(headers: dict) -> list[dict]:
    """读取完整列表，避免清理或续传时遗漏分页中的 Release。"""
    outcome = []
    for page in range(1, 101):
        group = request(headers, 'GET', f'{API}/releases?per_page=100&page={page}')
        outcome.extend(group)
        if len(group) < 100:
            return outcome
    raise ValueError('Release 列表超过可核对范围')


def digest(path: Path) -> str:
    """流式计算哈希，客户端分卷无需整块读入内存。"""
    with path.open('rb') as stream:
        return sha256_file(stream)


def sha256_file(stream) -> str:
    """计算文件流摘要。"""
    value = sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def checked_assets(folder: Path) -> dict[str, str]:
    """只接受审计清单中的固定发布文件，并逐个比对实际字节。"""
    sums = folder / 'SHA256SUMS'
    found = {}
    pattern = re.compile(r'[a-f0-9]{64}  (wendao163-compose\.zip|wendao163-windows\.7z\.[0-9]{3})')
    for line in sums.read_text(encoding='ascii').splitlines():
        match = pattern.fullmatch(line)
        if not match:
            raise ValueError('SHA256SUMS 含非法条目')
        name = match[1]
        if name in found:
            raise ValueError('SHA256SUMS 含重复条目')
        source = folder / name
        if source.is_symlink() or not 0 < source.stat().st_size < 2**31 or digest(source) != line[:64]:
            raise ValueError(f'资产已变化或尺寸超限：{name}')
        found[name] = 'sha256:' + line[:64]
    if 'wendao163-compose.zip' not in found or 'wendao163-windows.7z.001' not in found:
        raise ValueError('需包含组合 ZIP 和 Windows 客户端')
    found[sums.name] = 'sha256:' + digest(sums)
    return found


def check_asset(asset: dict, file: Path, expected: str) -> None:
    """服务端存档必须与本地同名、同长度和同摘要。"""
    if (asset['name'], asset['size'], asset['state'], asset.get('digest')) != (
            file.name, file.stat().st_size, 'uploaded', expected):
        raise ValueError(f'GitHub 文件未通过核对：{file.name}')


def upload_asset(headers: dict, release_id: int, file: Path, expected: str, existing: dict | None) -> None:
    """续传时复用已验证的附件，只有草稿中的占位文件才可清理重传。"""
    if existing and existing['state'] == 'uploaded':
        check_asset(existing, file, expected)
        print(f'已核对草稿中的 {file.name}', flush=True)
        return
    if existing:
        request(headers, 'DELETE', f'{API}/releases/assets/{existing["id"]}')
    print(f'正在上传 {file.name} ({file.stat().st_size:,} 字节)', flush=True)
    url = f'https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets?name={quote(file.name)}'
    head = {**headers, 'Content-Type': 'application/octet-stream', 'Content-Length': str(file.stat().st_size)}
    try:
        with file.open('rb') as stream:
            with urlopen(Request(url, data=stream, method='POST', headers=head), timeout=900) as response:
                asset = json.load(response)
    except HTTPError as error:
        raise ValueError(f'{file.name} 上传返回 HTTP {error.code}') from None
    check_asset(asset, file, expected)
    print(f'{file.name} 上传及 SHA-256 核对通过', flush=True)


def publish(args: argparse.Namespace) -> None:
    """把所有附件写入同一草稿，核对链接后才删除此前的 Release。"""
    folder = args.assets.resolve()
    assets = checked_assets(folder)
    headers = credentials()
    branch_commit = request(headers, 'GET', API + '/branches/main')['commit']['sha']
    if git('rev-parse', 'HEAD') != branch_commit:
        raise ValueError('当前 HEAD 与 GitHub main 不一致，请先提交并推送说明')
    tag = args.tag
    release_list = releases(headers)
    selected = next((item for item in release_list if item['tag_name'] == tag), None)
    if args.stage_only and selected and not selected['draft']:
        raise ValueError('该版本已经公开')
    target = {'tag_name': tag, 'target_commitish': branch_commit,
              'name': f'问道 1.63 Docker Compose 与 Windows 客户端 {tag}',
              'body': args.notes.read_text(), 'prerelease': False}
    release = selected or request(headers, 'POST', API + '/releases', {**target, 'draft': True})
    release_id = release['id']
    url = API + f'/releases/{release_id}'
    existing = {row['name']: row for row in release['assets']}
    if set(existing) - set(assets):
        raise ValueError('目标 Release 有清单外的附件，请先核对')
    if release['draft']:
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [pool.submit(upload_asset, headers, release_id, folder / name, expected, existing.get(name))
                    for name, expected in assets.items()]
            for job in jobs:
                job.result()
    elif set(existing) != set(assets):
        raise ValueError('已公开 Release 附件不完整')
    release = request(headers, 'GET', url)
    uploaded = {row['name']: row for row in release['assets']}
    if uploaded.keys() != assets.keys():
        raise ValueError('草稿附件与校验清单不一致')
    for name, expected in assets.items():
        check_asset(uploaded[name], folder / name, expected)
    if args.stage_only:
        print('草稿已验证，保持未公开。', flush=True)
        return
    if release['draft']:
        branch_commit = request(headers, 'GET', API + '/branches/main')['commit']['sha']
        if branch_commit != target['target_commitish']:
            raise ValueError('上传期间 main 已变化，暂不公开 Release')
        release = request(headers, 'PATCH', url, {**target, 'draft': False, 'make_latest': 'true'})
    if request(headers, 'GET', API + '/releases/latest')['id'] != release_id:
        raise ValueError('GitHub 最新 Release 尚未指向新版本')
    for name, row in uploaded.items():
        # 读一个字节，同时核对公开下载入口可达并避免重复下载整个客户端。
        with urlopen(Request(row['browser_download_url'], headers={'Range': 'bytes=0-0'}), timeout=90) as response:
            if not response.read(1):
                raise ValueError(f'公开下载未生效：{name}')
    if args.prune_older:
        for old in release_list:
            if old['id'] == release_id or old['created_at'] >= release['created_at']:
                continue
            request(headers, 'DELETE', API + '/releases/' + str(old['id']))
            print('已删除旧 Release', old['tag_name'], flush=True)
        if [row['id'] for row in releases(headers)] != [release_id]:
            raise ValueError('仍有其他 Release，请核对并行发布的记录')
    print(release['html_url'], flush=True)


def main() -> None:
    """默认以新版本发布，明确传入参数才会移除旧 Release。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--notes', required=True, type=Path)
    parser.add_argument('--stage-only', action='store_true')
    parser.add_argument('--prune-older', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'v1\.63\.\d+', args.tag) or (args.stage_only and args.prune_older):
        parser.error('仅支持 v1.63.x 版本，暂存草稿与清理旧版本不可同时使用')
    try:
        publish(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'发行未完成：{error}\n')


if __name__ == '__main__':
    main()
