#!/usr/bin/env python3
"""
Generate updated config files into Cfg.
"""

import os
import re
import sys
import datetime
import subprocess

# Environment / config (defaults)
UPSTREAM_REPO = os.environ.get("UPSTREAM_REPO", "Repcz/Tool")
TARGET_REPO = os.environ.get("TARGET_REPO", "Dawneng/StrangeTools")
SOURCE_BRANCH = os.environ.get("SOURCE_BRANCH", "X")   # used in generated raw URLs
TARGET_BRANCH = os.environ.get("TARGET_BRANCH", "main")  # push destination branch

# Use UTC+8 for timestamp
now_utc = datetime.datetime.utcnow()
now = now_utc + datetime.timedelta(hours=8)
time_str = f"{now.year}-{now.month}-{now.day} {now.hour:02d}:{now.minute:02d}"

# Regex to match upstream raw URLs:
# e.g. https://github.com/Repcz/Tool/raw/X/{client}/Rules/{rulefile}
upstream_escaped = re.escape(UPSTREAM_REPO)
url_pattern = re.compile(
    rf"https://github\.com/{upstream_escaped}/raw/{re.escape(SOURCE_BRANCH)}/([^/\s]+)/Rules/([^\s\"')]+)"
)

# Patterns for comment lines to remove / keep and time line
author_re = re.compile(r"^#\s*Author:", re.I)
tg_re = re.compile(r"^#\s*TG:", re.I)
time_line_re = re.compile(r"^#\s*最后更新时间:.*$", re.M)

# Filenames to search for (basenames)
basenames = {
    "Surge.conf", "Surge_lite.conf", "Shadowrocket.conf", "LanceX.conf",
    "Surfboard.conf", "Loon.conf", "QuantumultX.conf", "Stash.yaml",
    "Stash_lite.yaml", "Stash.stoverride", "config.yaml", "Override.js",
    "sing-box.json", "Egern.yaml"
}

Cfg_root = "Cfg"

def should_skip_path(path):
    parts = path.split(os.sep)
    if ".git" in parts:
        return True
    if parts and parts[0] == ".github":
        return True
    if parts and parts[0] == Cfg_root:
        return True
    return False

changed = []

for root, dirs, files in os.walk("."):
    # Normalize root and avoid descending into .git/.github/Cfg
    r = root.lstrip("./")
    # prune dirs to avoid walking into .git, .github, Cfg
    dirs[:] = [d for d in dirs if d not in (".git", ".github", Cfg_root)]
    if should_skip_path(r):
        continue
    for fn in files:
        if fn in basenames:
            src_path = os.path.join(root, fn)
            # avoid touching workflow files explicitly
            if ".github" in src_path and "workflows" in src_path:
                continue
            # also ensure we don't process files that are already under Cfg/
            # (defensive)
            if os.path.normpath(src_path).split(os.sep)[0] == Cfg_root:
                continue
            try:
                with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                    original = f.read()
            except Exception as e:
                print("skip unreadable", src_path, e)
                continue

            # 1) Replace upstream URLs -> use SOURCE_BRANCH in the generated raw URL
            new = url_pattern.sub(
                lambda m: f"https://raw.githubusercontent.com/{TARGET_REPO}/{SOURCE_BRANCH}/{m.group(1)}/Rules/{m.group(2)}",
                original
            )

            # 2) Process lines:
            lines = new.splitlines(keepends=True)

            author_lines = []
            body_lines = []
            for line in lines:
                if author_re.match(line):
                    author_lines.append(line.rstrip("\n") + "\n")  # normalize newline
                    continue
                if tg_re.match(line):
                    # drop TG lines
                    continue
                if time_line_re.match(line):
                    # drop existing time lines (we will insert an updated one)
                    continue
                # otherwise keep as body
                body_lines.append(line)

            # 3) Build final content: author lines (if any), then updated time line, then body
            time_line = f"# 最后更新时间: {time_str}\n"
            final_content = "".join(author_lines) + time_line + "".join(body_lines)

            # Ensure file ends with newline
            if not final_content.endswith("\n"):
                final_content += "\n"

            # 4) Write to Cfg/<relative-path> if changed
            if final_content != original:
                rel_path = os.path.relpath(src_path, ".")
                dest_path = os.path.join(Cfg_root, rel_path)
                dest_dir = os.path.dirname(dest_path)
                os.makedirs(dest_dir, exist_ok=True)
                try:
                    # Overwrite existing file if present
                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(final_content)
                    changed.append(dest_path)
                    print("generated", dest_path)
                except Exception as e:
                    print("failed write", dest_path, e)

if not changed:
    print("No configuration files changed; nothing generated under Cfg/.")
    sys.exit(0)

# Commit & push generated Cfg files
try:
    # Stage only the generated files
    subprocess.check_call(["git", "add"] + changed)
    commit_msg = "Generate updated configs"
    # commit may fail if nothing to commit (unlikely since changed non-empty), handle gracefully
    try:
        subprocess.check_call(["git", "commit", "-m", commit_msg])
    except subprocess.CalledProcessError:
        print("No changes to commit (git commit returned non-zero).")
    # Push to target branch
    subprocess.check_call(["git", "push", "origin", f"HEAD:{TARGET_BRANCH}"])
    print("Pushed generated Cfg files:", changed)
except subprocess.CalledProcessError as e:
    print("Git push/commit failed:", e)
    sys.exit(2)