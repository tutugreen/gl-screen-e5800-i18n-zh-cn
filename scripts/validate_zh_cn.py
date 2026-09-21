# -*- coding: utf-8 -*-
"""校验 zh_cn 与 en：行数/键名一致，且每行格式为 KEY "value" 单行。"""
from collections import Counter
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

KEY_RE = re.compile(r'^([A-Za-z0-9_@]+)\s+(.+)$')
PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[-+0 #]*(?:\d+)?(?:\.\d+)?[a-zA-Z]")


def parse_logical_lines(path: Path) -> list[tuple[int, str, str | None, str | None]]:
    """返回 (物理行号, 原始行, key, value_or_ref)。"""
    text = path.read_text(encoding="utf-8")
    physical = text.splitlines()
    logical = []
    i = 0
    while i < len(physical):
        start = i + 1
        line = physical[i]
        if not line.strip() or line.startswith("//"):
            logical.append((start, line, None, None))
            i += 1
            continue
        m = KEY_RE.match(line)
        if not m:
            logical.append((start, line, "__BAD__", None))
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        if rest.startswith('"'):
            buf = [line]
            combined = line
            while not _quoted_value_complete(combined) and i + 1 < len(physical):
                i += 1
                combined += "\n" + physical[i]
                buf.append(physical[i])
            logical.append((start, "\n".join(buf), key, rest))
            i += 1
            continue
        logical.append((start, line, key, rest))
        i += 1
    return logical


def _quoted_value_complete(line: str) -> bool:
    """判断 KEY "..." 形式的引号是否在同一物理行内闭合（简化）。"""
    rest = line.split(None, 1)[1] if len(line.split(None, 1)) == 2 else line
    if rest == '"""' or (
        len(rest) == 3 and rest[0] == '"' and rest[1] == "\\" and rest[2] == '"'
    ):
        return True
    idx = line.find('"')
    if idx < 0:
        return True
    i = idx + 1
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == '"':
            tail = line[i + 1 :].strip()
            return tail == "" or tail.startswith("//")
        i += 1
    return False


def extract_key_only(line: str) -> str | None:
    s = line.strip()
    if not s or s.startswith("//"):
        return None
    m = KEY_RE.match(s)
    return m.group(1) if m else "__BAD__"


def main() -> None:
    from repo_paths import SOURCES_EN, SOURCES_ZH_CN

    en_path = SOURCES_EN
    zh_path = SOURCES_ZH_CN
    en_lines = en_path.read_text(encoding="utf-8").splitlines()
    zh_lines = zh_path.read_text(encoding="utf-8").splitlines()

    print(f"物理行数: en={len(en_lines)}, zh_cn={len(zh_lines)}")
    has_error = False

    en_keys = [extract_key_only(l) for l in en_lines]
    zh_keys = [extract_key_only(l) for l in zh_lines]

    malformed = {}
    for name, lines in (("en", en_lines), ("zh_cn", zh_lines)):
        issues = []
        for i, line in enumerate(lines, 1):
            if not line.strip() or line.startswith("//"):
                continue
            match = KEY_RE.match(line)
            if not match or (
                match.group(2).startswith('"') and not _quoted_value_complete(line)
            ):
                issues.append(i)
        malformed[name] = issues
        print(f"{name} 格式错误/跨行条目起始行: {len(issues)}")
        if issues:
            print("  示例:", issues[:15])
            has_error = True

    # 按 en 的键序列对齐（仅非注释行）
    def key_sequence(keys):
        return [k for k in keys if k is not None]

    en_seq = key_sequence(en_keys)
    zh_seq = key_sequence(zh_keys)

    print(f"逻辑条目数(有键): en={len(en_seq)}, zh_cn={len(zh_seq)}")

    if len(en_seq) != len(zh_seq):
        print("ERROR: 逻辑条目数量不一致")
        has_error = True
    else:
        mismatches = []
        for n, (ek, zk) in enumerate(zip(en_seq, zh_seq), 1):
            if ek != zk:
                mismatches.append((n, ek, zk))
        if mismatches:
            print(f"ERROR: 键名不一致 {len(mismatches)} 处")
            for item in mismatches[:20]:
                print(" ", item)
            has_error = True
        else:
            print("OK: 所有键名与 en 顺序一致")

    if len(en_lines) != len(zh_lines):
        print(f"ERROR: 物理行数不一致，差 {len(zh_lines) - len(en_lines)} 行（多为 \\n 被写成真实换行）")
        has_error = True
    elif not malformed["en"] and not malformed["zh_cn"]:
        print("OK: 物理行数一致且无格式错误")

    en_entries = [line for line in en_lines if extract_key_only(line) is not None]
    zh_entries = [line for line in zh_lines if extract_key_only(line) is not None]
    placeholder_issues = []
    for en_line, zh_line in zip(en_entries, zh_entries):
        en_key = extract_key_only(en_line)
        en_placeholders = Counter(PLACEHOLDER_RE.findall(en_line))
        zh_placeholders = Counter(PLACEHOLDER_RE.findall(zh_line))
        if en_placeholders != zh_placeholders:
            placeholder_issues.append((en_key, en_placeholders, zh_placeholders))
    if placeholder_issues:
        print(f"ERROR: 占位符不一致 {len(placeholder_issues)} 处")
        for issue in placeholder_issues[:20]:
            print(" ", issue)
        has_error = True
    else:
        print("OK: 所有格式化占位符一致")

    if has_error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
