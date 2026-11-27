"""用一条命令构建组合版和客户端，并在本地生成脱敏校验清单。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def main() -> None:
    """两个产物在不同目录准备，全部成功才进行发布审计。"""
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('baseline', 'gm', 'server-source', 'client', 'work'):
        parser.add_argument('--' + flag, required=True, type=Path)
    parser.add_argument('--seven-zip', default='7zz')
    parser.add_argument('--reject-file', type=Path)
    args = parser.parse_args()
    work = args.work.resolve()
    if work.exists():
        parser.error('请为这次发布指定一个新的 --work 目录')
    work.mkdir(parents=True)
    out = work / 'dist'
    scripts = [
        ['build_kit.py', '--baseline', args.baseline, '--gm', args.gm, '--work', work / 'kit'],
        ['build_windows.py', '--client', args.client, '--work', work / 'client', '--seven-zip', args.seven_zip],
    ]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(subprocess.run, [sys.executable, HERE / script, *flags, '--output', out], check=True)
                    for script, *flags in scripts]
            for job in jobs:
                job.result()
        command = [sys.executable, HERE / 'audit.py', '--kit', work / 'kit/wendao163-compose',
                   '--client-stage', work / 'client/wendao163-windows', '--gm', args.gm,
                   '--server-source', args.server_source, '--output', out]
        if args.reject_file:
            command.extend(['--reject-file', args.reject_file])
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f'准备发行失败，退出码 {error.returncode}。\n')
    print(f'待上传附件位于 {out}')


if __name__ == '__main__':
    main()
