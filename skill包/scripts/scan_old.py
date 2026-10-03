#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_old.py —— 知识库体检：找出「旧版 / 重复 / 极短 / 散文件」

用法：
    python scan_old.py "你的 vault 路径"
    不传参数则扫描当前目录。

体检五项：
    1) 名字或路径带「旧 / 备份 / 归档」标记的文件
    2) 同名文件（出现在不同目录，容易内容分叉）
    3) 内容疑似重复（正文开头 300 字完全相同）
    4) 极短文件（< 300 字节，可能是占位或残留）
    5) 顶层散文件（未归入任何子目录的 md；库级约定文件 AGENTS.md / hot.md / 00_总目录.md 等不算）

依赖：标准库，无需安装任何包。Python 3.8+ 可用。
"""
import os
import re
import sys
import argparse
import hashlib
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

SKIP_DIRS = {'.obsidian', '.git', 'node_modules', '.smart-env', 'copilot',
             '.claude', '.agents', '.opencode', '.trash'}

MARK_FILE = ['旧', '备份', '归档', '废弃', '草稿', '过时', '作废', '待删']
MARK_WORD = ['old', 'backup', 'bak', 'draft', 'deprecated', 'obsolete']


def rel(p, root):
    return os.path.relpath(p, root)


def main():
    parser = argparse.ArgumentParser(description='知识库体检：旧版 / 重复 / 残留 / 散文件')
    parser.add_argument('root', nargs='?', default=os.getcwd(),
                        help='要扫描的 vault 路径，默认当前目录')
    args = parser.parse_args()
    ROOT = os.path.abspath(args.root)
    if not os.path.isdir(ROOT):
        print("❌ 路径不存在：%s" % ROOT)
        sys.exit(1)

    files = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.lower().endswith('.md'):
                files.append(os.path.join(dp, fn))

    print("=" * 70)
    print("扫描范围：%s" % ROOT)
    print("md 文件总数：%d" % len(files))
    print("=" * 70)

    # ---------- 1. 名字或路径带标记 ----------
    print("\n【1】名字或路径带「旧 / 备份 / 归档」标记的文件")
    print("-" * 70)
    hit1 = []
    for p in files:
        r = rel(p, ROOT)
        base = os.path.basename(p)
        low = base.lower()
        if any(m in r for m in MARK_FILE) or any(w in low for w in MARK_WORD):
            hit1.append(r)
    for r in sorted(hit1):
        print("  " + r)
    print("  → 合计 %d 个" % len(hit1))

    # ---------- 2. 同名文件 ----------
    print("\n【2】同名文件（出现在不同目录）")
    print("-" * 70)
    by_name = defaultdict(list)
    for p in files:
        by_name[os.path.basename(p)].append(rel(p, ROOT))
    hit2 = {k: v for k, v in by_name.items() if len(v) > 1}
    if not hit2:
        print("  （无）")
    for k in sorted(hit2):
        print("  ● %s  ×%d" % (k, len(hit2[k])))
        for v in hit2[k]:
            print("      " + v)
    print("  → 合计 %d 组" % len(hit2))

    # ---------- 3. 内容疑似重复（首 300 字 hash 相同） ----------
    print("\n【3】内容疑似重复（正文开头 300 字完全相同）")
    print("-" * 70)
    by_hash = defaultdict(list)
    for p in files:
        try:
            with open(p, encoding='utf-8', errors='ignore') as f:
                t = f.read(3000)
        except Exception:
            continue
        t = re.sub(r'\s+', '', t)[:300]
        if len(t) < 100:
            continue
        by_hash[hashlib.md5(t.encode('utf-8')).hexdigest()].append(rel(p, ROOT))
    hit3 = {k: v for k, v in by_hash.items() if len(v) > 1}
    if not hit3:
        print("  （无 —— 没有正文开篇完全一致的文件）")
    for k, v in hit3.items():
        print("  ● 开头相同：")
        for x in v:
            print("      " + x)
    print("  → 合计 %d 组" % len(hit3))

    # ---------- 4. 空文件 / 极短文件 ----------
    print("\n【4】极短文件（< 300 字节，可能是占位或残留）")
    print("-" * 70)
    hit4 = []
    for p in files:
        try:
            sz = os.path.getsize(p)
        except Exception:
            continue
        if sz < 300:
            hit4.append((sz, rel(p, ROOT)))
    for sz, r in sorted(hit4):
        print("  %5d B  %s" % (sz, r))
    print("  → 合计 %d 个" % len(hit4))

    # ---------- 5. 顶层散文件 ----------
    print("\n【5】顶层散文件（未归入任何子目录的 md；库级约定文件不算）")
    print("-" * 70)
    # 这些是本 skill 约定放在库根的文件，不算散文件
    LOOSE_EXCLUDE = {'AGENTS.md', 'CLAUDE.md', 'hot.md', '00_总目录.md',
                     '00_目录.md', '00_导航.md', 'README.md'}
    loose = [f for f in os.listdir(ROOT)
             if f.lower().endswith('.md') and os.path.isfile(os.path.join(ROOT, f))
             and f not in LOOSE_EXCLUDE]
    if loose:
        for f in sorted(loose):
            print("  " + f)
        print("  → 合计 %d 个" % len(loose))
    else:
        print("  （无）")

    print("\n扫描结束。以上仅为清单，未改动任何文件。")


if __name__ == '__main__':
    main()
