#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_index.py —— 自动生成知识库目录

用法：
    python gen_index.py "你的 vault 路径"
    不传参数则扫描脚本运行时的当前目录。

做什么：
    1. 在库根生成 00_总目录.md（只到「分类」级）
    2. 在每个子目录生成 00_目录.md（只列直接子项，递归到每一层）
    3. 每篇摘要来自首行的「> 一句话：…」；分类 / 文件夹描述来自各自的 00_导航.md
    —— 人工写的目录文件（不含「本文件由脚本生成」标记）不会被覆盖。

依赖：标准库，无需安装任何包。Python 3.8+ 可用。
"""
import os
import re
import sys
import datetime
import argparse

sys.stdout.reconfigure(encoding='utf-8')

# ---------- 可配置项（一般不用改） ----------
SELF_NAME = "00_总目录.md"      # 库根总目录
SUB_NAME = "00_目录.md"         # 每层自动生成的「本层清单」
NAV_NAME = "00_导航.md"         # 人工写的导航（脚本不动它，但会读它的描述）
GEN_MARK = "本文件由脚本生成"    # 脚本生成的文件都带这句；没有 = 人工写的，不覆盖
ARCHIVE_PREFIX = ('_归档', '_备份', '_旧版')
SKIP_DIRS = {'.obsidian'}

SKIP_HEADS = ['建档', '创建', '建立', '归属', '记录日期', '状态', '来源', '所属', '日期',
              '迁移时间', '本文件位置', '最后', '层级', '适用范围', '适用', '定位',
              '触发时间', '更新', '版本', '说明']
WEAK_HEADS = ['依据', '性质', '关联', '存放说明', '前提', '对应', '备注', '补充',
              '起因', '目的', '为什么写']
USE_HEADS = ('什么时候看', '什么时候用', '有什么用', '用途', '用在', '服务于')

P_ONELINE = re.compile(r'^>\s*一句话[：:]\s*(.+)$')
P_ANYQUOTE = re.compile(r'^>\s*(.+)$')

ROOT = ''   # 由 main() 通过命令行参数设置


def clean(s):
    s = s.strip()
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)   # md 链接只留文字
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)            # 去粗体
    s = s.replace('`', '')
    s = re.sub(r'^[-—·\s]+', '', s)
    s = re.sub(r'^[^0-9A-Za-z\u4e00-\u9fff]+', '', s)  # 去开头 emoji / 符号
    return s.strip()


def extract(path):
    """返回 (一句话, 来源标记)  来源: 'new' 新格式 / 'old' 老格式 / 'weak' 弱 / None 缺"""
    try:
        lines = open(path, encoding='utf-8', errors='ignore').read().split('\n')
    except Exception:
        return None, None

    # 1) 新格式优先：首行「> 一句话：…」
    for l in lines[:30]:
        m = P_ONELINE.match(l.strip())
        if m:
            t = clean(m.group(1))
            if len(t) >= 6:
                return t[:120], 'new'

    # 2) 老格式：优先非元信息；元信息先存着当兜底
    weak_hit = None
    for l in lines[:30]:
        m = P_ANYQUOTE.match(l.strip())
        if not m:
            continue
        t = clean(m.group(1))
        if len(t) < 8:
            continue
        if any(t.startswith(h) for h in SKIP_HEADS):
            continue
        if any(t.startswith(h) for h in WEAK_HEADS):
            if weak_hit is None:
                weak_hit = t[:120]
            continue
        return t[:120], 'old'
    if weak_hit:
        return weak_hit, 'weak'

    # 3) 兜底：任何引用行
    for l in lines[:30]:
        m = P_ANYQUOTE.match(l.strip())
        if m:
            t = clean(m.group(1))
            if len(t) >= 4:
                return t[:120], 'weak'
    return None, None


def enc(p):
    return p.replace('\\', '/').replace(' ', '%20')


def extract_use(path):
    """返回「什么时候看 / 有什么用」那一行（没有就 None）"""
    try:
        lines = open(path, encoding='utf-8', errors='ignore').read().split('\n')
    except Exception:
        return None
    for l in lines[:40]:
        s = l.strip()
        if not s.startswith('>'):
            continue
        s = s.lstrip('>').strip()
        s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
        s = s.lstrip('⭐ ').strip()
        for head in USE_HEADS:
            if s.startswith(head):
                t = clean(s[len(head):].lstrip('：: 　'))
                if len(t) >= 4:
                    return t[:120]
    return None


def collect():
    """遍历整库，按顶层分类分组；归档 / 备份目录单列。"""
    normal, archive = {}, {}
    for dp, dns, fns in os.walk(ROOT):
        # 跳过 _ 开头目录，但保留归档前缀（_归档/_备份/_旧版）
        dns[:] = [d for d in dns if d not in SKIP_DIRS
                  and (not d.startswith('_') or d.startswith(ARCHIVE_PREFIX))]
        for fn in sorted(fns):
            if not fn.endswith('.md'):
                continue
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, ROOT).replace('\\', '/')
            if rel == SELF_NAME or fn == SUB_NAME:
                continue
            top = rel.split('/')[0] if '/' in rel else '(根目录)'
            is_arch = any(seg.startswith(ARCHIVE_PREFIX) for seg in rel.split('/')[:-1])
            one, kind = extract(full)
            use = extract_use(full)
            rec = (rel, fn, one, kind, os.path.getsize(full), use)
            (archive if is_arch else normal).setdefault(top, []).append(rec)
    return normal, archive


def section_info(k):
    """从 k/00_导航.md 读「这一节是干嘛的 / 什么时候看 / 入口」"""
    info = {}
    navp = os.path.join(ROOT, k, NAV_NAME)
    if not os.path.exists(navp):
        return info
    try:
        for l in open(navp, encoding='utf-8', errors='ignore').read().split('\n')[:60]:
            s = l.strip()
            if not s.startswith('>'):
                continue
            s = clean(s.lstrip('>').strip())
            if s.startswith('这一节是干嘛的') or s.startswith('是干嘛的'):
                info['what'] = s.split('：', 1)[-1].split(':', 1)[-1][:200]
            elif any(s.startswith(h) for h in ('什么时候看', '什么时候用')):
                info['when'] = s[4:][:200]
            elif s.startswith('入口'):
                info['entry'] = s.split('：', 1)[-1].split(':', 1)[-1].strip()
    except Exception:
        pass
    return info


def render_main(normal, archive):
    total = sum(len(v) for v in normal.values()) + sum(len(v) for v in archive.values())
    miss = [r for v in normal.values() for r in v if not r[2]]
    weak = [r for v in normal.values() for r in v if r[3] == 'weak']
    keys = sorted(normal)
    L = []
    A = L.append
    A("# 知识库 · 总目录")
    A("")
    A("> **这是什么**：你的知识库总入口。")
    A("> **怎么用**：先看这里（只到分类）→ 点进想看的分类 → 看那个分类的 `00_目录.md`（它只列下一层）→ 一层层往下钻。")
    A("> **本文件由脚本生成** ｜ 最后生成：%s ｜ 共 **%d 篇** / **%d 个分类**" % (
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), total, len(normal)))
    if miss or weak:
        A("> ⚠️ **摘要质量待提升：%d 篇**（在各层的 `00_目录.md` 里带标记）" % (len(miss) + len(weak)))
    A("")
    A("---")
    A("")
    A("## 目录（按分类）")
    A("")
    for i, k in enumerate(keys, 1):
        info = section_info(k)
        n_sub = len(scan_direct(k)[0]) if os.path.isdir(os.path.join(ROOT, k)) else 0
        A("### %d. %s ｜ %d 篇%s" % (i, k, len(normal[k]), ("（含 %d 个子文件夹）" % n_sub) if n_sub else ""))
        A("")
        if info.get('what'):
            A("> **这一节是干嘛的**：%s" % info['what'])
        if info.get('when'):
            A("> **什么时候看**：%s" % info['when'])
        if k == '(根目录)':
            A("")
            A("| 文件 | 装的是什么 | 什么时候用 |")
            A("|---|---|---|")
            for rel, fn, one, kind, size, use in normal[k]:
                link = "[%s](%s)" % (rel[:-3], enc(rel))
                mark = "" if kind in ('new', 'old') else (" ⚠️" if one else "")
                A("| %s | %s | %s |" % (link, (one + mark) if one else "❓ **待补**", use or "—"))
            A("")
        else:
            if info.get('entry'):
                A("> **入口**：先看 [`%s`](%s/%s)" % (info['entry'], enc(k), enc(info['entry'])))
            A("> **本层清单** → [`%s/00_目录.md`](%s/00_目录.md)" % (k, enc(k)))
            A("")
        A("")
    if archive:
        A("---")
        A("")
        A("## ⚠️ 归档与备份（不在分层目录里，只在这里列）")
        A("")
        for k in sorted(archive):
            A("- **%s** ｜ %d 篇" % (k, len(archive[k])))
        A("")
    return "\n".join(L), total, len(miss) + len(weak)


def scan_direct(rel_dir):
    """返回该目录的「直接子项」：(子目录名列表, 本层 md 文件名列表, 本层其他附件列表)"""
    full = os.path.join(ROOT, rel_dir) if rel_dir else ROOT
    dirs, files, others = [], [], []
    if not os.path.isdir(full):
        return dirs, files, others
    for name in sorted(os.listdir(full)):
        p = os.path.join(full, name)
        if os.path.isdir(p):
            if name in SKIP_DIRS or name.startswith('_') or name.startswith('.'):
                continue
            dirs.append(name)
        elif name.endswith('.md'):
            if name in (SELF_NAME, SUB_NAME):
                continue
            files.append(name)
        elif not name.startswith('.'):
            others.append(name)
    return dirs, files, others


def count_md(rel_dir):
    """递归数该目录下所有 md（排除目录文件、排除 _ 开头）"""
    full = os.path.join(ROOT, rel_dir) if rel_dir else ROOT
    n = 0
    for dp, dns, fns in os.walk(full):
        dns[:] = [d for d in dns if not d.startswith('_') and d not in SKIP_DIRS and not d.startswith('.')]
        for fn in fns:
            if fn.endswith('.md') and fn not in (SELF_NAME, SUB_NAME):
                n += 1
    return n


def folder_desc(sub_rel):
    """子文件夹「是干嘛的」：先读它自己的 00_导航.md 首行描述，没有就留空。"""
    navp = os.path.join(ROOT, sub_rel, NAV_NAME)
    if os.path.exists(navp):
        try:
            for l in open(navp, encoding='utf-8', errors='ignore').read().split('\n')[:40]:
                m = re.match(r'^>\s*(?:一句话|什么时候看|这一节是干嘛的)[：:]\s*(.+)$', l.strip())
                if m:
                    t = clean(m.group(1))
                    if len(t) >= 4:
                        return t[:70]
        except Exception:
            pass
    return ''


EXT_KIND = {
    '.svg': '矢量图', '.png': '图片', '.jpg': '图片', '.jpeg': '图片',
    '.gif': '动图', '.webp': '图片', '.pdf': 'PDF', '.xlsx': '表格',
    '.xls': '表格', '.csv': '表格', '.docx': '文档', '.pptx': '演示',
    '.mp4': '视频', '.mov': '视频', '.zip': '压缩包', '.canvas': 'Obsidian 画布',
    '.json': '数据', '.txt': '文本',
}


def ext_kind(fn):
    """非 md 附件的类型标签（给目录里「类型」列用）"""
    ext = os.path.splitext(fn)[1].lower()
    return EXT_KIND.get(ext, (ext.lstrip('.') or '文件').upper())


def render_dir(rel_dir):
    title = rel_dir.split('/')[-1]
    dirs, files, others = scan_direct(rel_dir)
    L = []
    A = L.append
    A("# %s · 文件目录" % title)
    A("")
    navp = os.path.join(ROOT, rel_dir, NAV_NAME)
    if os.path.exists(navp):
        A("> ⭐ **先看这个** → [`%s`](%s)（人工写的导航：按问题找文件）" % (NAV_NAME, NAV_NAME))
    A("> **本文件由脚本生成** ｜ 最后生成：%s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
    A("> **⭐ 本层只列「直接子项」** —— 子文件夹点进去看它自己的 `00_目录.md`，**不往下平铺**。")
    A("> **维护规则**：**新文件开头写一行 `> 一句话：…`**，重跑本脚本自动更新（**不要手动改本文件**）。")
    A("")
    A("---")
    A("")
    if dirs:
        A("## 📁 子文件夹（%d）" % len(dirs))
        A("")
        A("| 文件夹 | 是干嘛的 | 篇数 |")
        A("|---|---|---|")
        for d in dirs:
            sub_rel = rel_dir + '/' + d
            A("| [%s/](%s/%s) | %s | %d 篇 |" % (
                d, enc(d), SUB_NAME, folder_desc(sub_rel), count_md(sub_rel)))
        A("")
    if files:
        A("## 📄 本层文件（%d）" % len(files))
        A("")
        A("| 文件 | 装的是什么 | 什么时候用 |")
        A("|---|---|---|")
        for fn in files:
            full = os.path.join(ROOT, rel_dir, fn)
            one, kind = extract(full)
            use = extract_use(full)
            mark = "" if kind in ('new', 'old') else (" ⚠️" if one else "")
            A("| [%s](%s) | %s | %s |" % (
                fn[:-3], enc(fn), (one + mark) if one else "❓ **待补**", use or "—"))
        A("")
    if others:
        A("## 🖼️ 本层附件（%d）" % len(others))
        A("")
        A("| 文件 | 类型 |")
        A("|---|---|")
        for fn in others:
            A("| %s | %s |" % (fn, ext_kind(fn)))
        A("")
    if not dirs and not files and not others:
        A("（本层暂无文件）")
        A("")
    return "\n".join(L)


def all_dirs():
    """所有需要生成 00_目录.md 的目录（相对路径，不含根）"""
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if not d.startswith('_') and d not in SKIP_DIRS and not d.startswith('.')]
        rel = os.path.relpath(dp, ROOT).replace('\\', '/')
        if rel == '.':
            continue
        out.append(rel)
    return sorted(out)


def main():
    global ROOT
    parser = argparse.ArgumentParser(description='自动生成知识库目录')
    parser.add_argument('root', nargs='?', default=os.getcwd(),
                        help='要扫描的 vault 路径，默认当前目录')
    args = parser.parse_args()
    ROOT = os.path.abspath(args.root)
    if not os.path.isdir(ROOT):
        print("❌ 路径不存在：%s" % ROOT)
        sys.exit(1)

    OUT = os.path.join(ROOT, SELF_NAME)
    normal, archive = collect()
    text, total, missn = render_main(normal, archive)
    open(OUT, 'w', encoding='utf-8').write(text)

    made, skipped, empties = 0, 0, []
    for rel_dir in all_dirs():
        out_path = os.path.join(ROOT, rel_dir, SUB_NAME)
        if os.path.exists(out_path):
            try:
                if GEN_MARK not in open(out_path, encoding='utf-8', errors='ignore').read():
                    skipped += 1
                    continue          # 人工写的，保留
            except Exception:
                pass
        dirs, files, others = scan_direct(rel_dir)
        if not dirs and not files and not others:
            empties.append(rel_dir)  # 真·空文件夹也生成占位目录
        open(out_path, 'w', encoding='utf-8').write(render_dir(rel_dir))
        made += 1

    print("✅ 已生成：%s" % OUT)
    print("   另生成 %d 份分层目录（00_目录.md）｜ 跳过人工 %d 份 ｜ 空目录 %d 个" % (
        made, skipped, len(empties)))
    if empties:
        print("   📁 真·空目录（已生成占位目录，以后往里放东西即可）：%s" % "、".join(empties))
    print("   共 %d 篇（现行 %d / 归档备份 %d）" % (
        total, sum(len(v) for v in normal.values()), sum(len(v) for v in archive.values())))
    print("   ⚠️ 待补摘要：%d 篇" % missn)
    print()
    print("--- 各分类篇数 ---")
    for k in sorted(normal, key=lambda x: -len(normal[x])):
        print("   %3d 篇  %s" % (len(normal[k]), k))


if __name__ == '__main__':
    main()
