#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_links.py —— 扫描知识库里的断链 / 孤岛引用

用法：
    python check_links.py "你的 vault 路径"
    不传参数则扫描当前目录。
    --wide   同时扫描「库的上一级目录」，识别跨库引用（如引用了 vault 之外的笔记）。
             默认关闭（大多数人只在单库内引用）。

扫描四类：
    1) 双链 [[X]]            —— Obsidian 按文件名解析，移动文件夹不影响
    2) md 链接 [文字](路径)  —— 按路径解析，移动 / 改名会断
    3) 图片附件 ![](路径)    —— 同上
    4) 反引号里的路径 `x.md`  —— 点不动但被引用，文件名在库里找不到就提示

依赖：标准库，无需安装任何包。Python 3.8+ 可用。
"""
import os
import re
import sys
import argparse
import urllib.parse
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.git', 'node_modules', '.smart-env', 'copilot',
             '.claude', '.agents', '.opencode', '.trash'}

P_WIKI = re.compile(r'\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]')
P_MD = re.compile(r'(?<!\!)\[([^\]]*)\]\(([^)]+)\)')
P_IMG = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
# 反引号里的路径 `xxx.md`：这类点不动，但被引用；文件名在库里找不到就提示
P_BQ = re.compile(r'`([^`\n]*?\.md)`')


def main():
    parser = argparse.ArgumentParser(description='扫描知识库断链')
    parser.add_argument('root', nargs='?', default=os.getcwd(),
                        help='要扫描的 vault 路径，默认当前目录')
    parser.add_argument('--wide', action='store_true',
                        help='同时扫描库的上一级目录，识别跨库引用')
    args = parser.parse_args()
    ROOT = os.path.abspath(args.root)
    if not os.path.isdir(ROOT):
        print("❌ 路径不存在：%s" % ROOT)
        sys.exit(1)

    by_stem = {}
    all_md = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.lower().endswith('.md'):
                all_md.append(os.path.join(dp, fn))
                by_stem.setdefault(fn[:-3], []).append(os.path.join(dp, fn))

    # 跨库索引（可选，叠加在库自身之上）：库的上一级目录里的所有 md 文件名
    if args.wide:
        WIDE_ROOT = os.path.dirname(ROOT)
        for dp, dns, fns in os.walk(WIDE_ROOT):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for fn in fns:
                if fn.lower().endswith('.md'):
                    by_stem.setdefault(fn[:-3], []).append(os.path.join(dp, fn))

    issues = []
    for full in all_md:
        rel = os.path.relpath(full, ROOT).replace('\\', '/')
        try:
            text = open(full, encoding='utf-8', errors='ignore').read()
        except Exception:
            continue

        # 1) 双链 [[X]]
        for m in P_WIKI.finditer(text):
            t = m.group(1).strip()
            if not t:
                continue
            stem = os.path.basename(t.replace('\\', '/'))
            if stem not in by_stem:
                issues.append(('wiki', rel, t, '双链目标不存在'))

        # 2) md 链接 [文字](路径)
        for m in P_MD.finditer(text):
            link = m.group(2).strip()
            if link.startswith(('http://', 'https://', 'mailto:', '#', 'tel:')):
                continue
            link = link.split('#')[0]
            if not link:
                continue
            tgt = os.path.normpath(os.path.join(os.path.dirname(full), urllib.parse.unquote(link)))
            if not os.path.exists(tgt):
                issues.append(('md', rel, m.group(2), '路径不存在'))

        # 3) 图片 / 附件 ![](路径)
        for m in P_IMG.finditer(text):
            link = m.group(2).strip()
            if link.startswith(('http://', 'https://', 'data:')):
                continue
            link = link.split('#')[0]
            tgt = os.path.normpath(os.path.join(os.path.dirname(full), urllib.parse.unquote(link)))
            if not os.path.exists(tgt):
                issues.append(('img', rel, m.group(2), '附件不存在'))

        # 4) 反引号里的路径 `xxx.md`（提示级，只查文件名在不在）
        for m in P_BQ.finditer(text):
            link = m.group(1).strip()
            if not link or link.startswith(('http://', 'https://')):
                continue
            if any(ch in link for ch in ('*', '{', '}', '…', ' ')):   # 泛指 / 通配 / 占位
                continue
            link = link.split('#')[0].strip()
            if not link or '/' not in link:      # 纯文件名不判（多为泛指）
                continue
            base = os.path.basename(urllib.parse.unquote(link))
            if base.endswith('.md') and base[:-3] not in by_stem:
                issues.append(('bq', rel, m.group(1), '⚠️ 文件名在库里找不到'))

    c = Counter(k for k, _, _, _ in issues)
    print("扫描范围：%s%s" % (ROOT, "（含跨库）" if args.wide else ""))
    print("md 文件：%d 个" % len(all_md))
    print("=" * 70)
    print("断链统计： 双链 %d  ｜  md 链接 %d  ｜  图片 %d  ｜  反引号 %d  ｜  合计 %d" % (
        c['wiki'], c['md'], c['img'], c['bq'], len(issues)))
    print("=" * 70)
    if not issues:
        print("（无断链）")
    for k, rel, tgt, why in issues:
        print("[%-4s] %s\n         → %s   (%s)" % (k, rel, tgt, why))


if __name__ == '__main__':
    main()
