#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iptv-bridge
===========
把多个上游订阅聚合成 SenPlayer 能直接订阅的地址，并随上游自动更新。

产物：
  dist/live.m3u      -> SenPlayer「IPTV 直播」订阅这个（M3U 格式）
  dist/live.txt      -> 同上，TXT 格式（部分播放器只认这个）
  dist/tvbox.json    -> TVBox / 影视仓 / 猫影视 的点播订阅（SenPlayer 用不了）
  dist/README.md     -> 本次运行的统计报告

上游加速：直连 GitHub 失败时自动依次尝试 jsDelivr、ghproxy 镜像。
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
CONFIG = os.path.join(ROOT, "config.json")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# --------------------------------------------------------------------------
# 抓取
# --------------------------------------------------------------------------
def mirror_variants(url: str):
    """为一个 GitHub/Gitee 原始链接生成多个可尝试的镜像地址。"""
    out = [url]
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)$", url)
    if m:
        user, repo, ref, path = m.groups()
        out.append(f"https://cdn.jsdelivr.net/gh/{user}/{repo}@{ref}/{path}")
        out.append(f"https://ghproxy.net/https://raw.githubusercontent.com/{user}/{repo}/{ref}/{path}")
        out.append(f"https://raw.fastgit.org/{user}/{repo}/{ref}/{path}")
    m2 = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/(.+)$", url)
    if m2 and not m:
        user, repo, path = m2.groups()
        out.append(f"https://cdn.jsdelivr.net/gh/{user}/{repo}@HEAD/{path}")
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def fetch(url: str, timeout: int = 40, retries: int = 2) -> str:
    """带镜像回退 + 重试的文本抓取。"""
    last_err = None
    for candidate in mirror_variants(url):
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(candidate, headers={
                    "User-Agent": UA,
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                })
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                for enc in ("utf-8", "gbk", "latin-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", "ignore")
            except Exception as e:                      # noqa: BLE001
                last_err = e
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"抓取失败 {url}：{last_err}")


# --------------------------------------------------------------------------
# M3U / TXT 解析
# --------------------------------------------------------------------------
EXTINF_RE = re.compile(r'^#EXTINF:\s*(-?\d+)\s*(.*)$', re.I)


def parse_attrs(blob: str) -> dict:
    """从 EXTINF 的属性段里抠出 tvg-name / tvg-logo / group-title。"""
    attrs = {}
    for k, v in re.findall(r'([\w-]+)\s*=\s*"([^"]*)"', blob):
        attrs[k.lower()] = v
    return attrs


def parse_playlist(text: str, default_group: str = ""):
    """
    同时兼容三种写法：
      1) 标准 M3U：  #EXTINF:-1 tvg-name="CCTV1" group-title="央视",CCTV-1 综合
                     http://xxx.m3u8
      2) TXT 逗号式： CCTV-1 综合,http://xxx.m3u8
      3) TXT 逗号式（反序）：http://xxx.m3u8,CCTV-1 综合
    返回 [(name, url, logo, group), ...]
    """
    items, pending = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            m = EXTINF_RE.match(line)
            if m:
                rest = m.group(2)
                attrs = parse_attrs(rest)
                # 逗号之后才是显示名；若没有逗号，就用 tvg-name
                if "," in rest:
                    name = rest.rsplit(",", 1)[1].strip()
                else:
                    name = (attrs.get("tvg-name") or "").strip()
                pending = {
                    "name": name or attrs.get("tvg-name") or "未命名",
                    "logo": attrs.get("tvg-logo", ""),
                    "group": attrs.get("group-title", "") or default_group,
                }
            elif "x-tvg-url" in line.lower():
                continue
            continue

        url = line
        if pending:
            name, logo, group = pending["name"], pending["logo"], pending["group"]
            pending = None
        else:
            # 逗号式 TXT
            if "," in line:
                a, b = line.split(",", 1)
                a, b = a.strip(), b.strip()
                if a.lower().startswith(("http://", "https://", "rtmp://", "rtsp://")):
                    url, name = a, b
                else:
                    name, url = a, b
            else:
                continue
            logo, group = "", default_group

        if url.lower().startswith(("http://", "https://", "rtmp://", "rtsp://", "rtp://")):
            items.append((name, url, logo, group))
    return items


def parse_tvbox_json(text: str):
    """TVBox 系配置：根对象下 sites / lives / parses 三个数组。"""
    try:
        data = json.loads(text)
    except Exception:                                   # noqa: BLE001
        return []
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    out = []
    for key in ("sites", "lives", "parses"):
        v = data.get(key)
        if isinstance(v, list):
            out.extend([x for x in v if isinstance(x, dict)])
    return out


# --------------------------------------------------------------------------
# 清洗 / 去重
# --------------------------------------------------------------------------
def norm_name(name: str) -> str:
    """归一化频道名，用于去重比较。"""
    s = name.strip().lower()
    s = re.sub(r'[\(\[（【].*?[\)\]）】]', '', s)          # 去括号内容
    s = re.sub(r'\b(高清|超清|标清|hd|fhd|uhd|4k|8k|1080p|720p|576p|2160p)\b', '', s, flags=re.I)
    s = re.sub(r'[^\w\u4e00-\u9fff]+', '', s)             # 只留中英文数字
    return s


def dedup(items, max_per_channel=3, excludes=(), includes=()):
    """
    items: [(name, url, logo, group, srcname), ...]
    同名的按来源顺序保留最多 max_per_channel 条，URL 去重。
    """
    buckets, order = {}, []
    for name, url, logo, group, src in items:
        if not name or not url:
            continue
        if excludes and any(x.lower() in name.lower() for x in excludes):
            continue
        if includes and not any(x.lower() in name.lower() for x in includes):
            continue
        key = norm_name(name)
        if not key:
            continue
        if key not in buckets:
            buckets[key] = {"name": name, "entries": [], "group": group}
            order.append(key)
        b = buckets[key]
        if any(e["url"] == url for e in b["entries"]):
            continue
        if len(b["entries"]) >= max_per_channel:
            continue
        b["entries"].append({"url": url, "logo": logo, "src": src})
    return [buckets[k] for k in order]


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def write_m3u(channels, path, tvg_url=""):
    lines = ["#EXTM3U"]
    if tvg_url:
        lines.append(f'x-tvg-url="{tvg_url}"')
    for ch in channels:
        for e in ch["entries"]:
            attrs = [f'tvg-name="{ch["name"]}"']
            if e["logo"]:
                attrs.append(f'tvg-logo="{e["logo"]}"')
            if ch["group"]:
                attrs.append(f'group-title="{ch["group"]}"')
            lines.append(f'#EXTINF:-1 {" ".join(attrs)},{ch["name"]}')
            lines.append(e["url"])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return sum(len(c["entries"]) for c in channels)


def write_txt(channels, path):
    lines = []
    for ch in channels:
        group = ch["group"]
        for e in ch["entries"]:
            label = f'{group}_{ch["name"]}' if group else ch["name"]
            lines.append(f'{label},{e["url"]}')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return sum(len(c["entries"]) for c in channels)


def write_tvbox(sites, path):
    seen, uniq = set(), []
    for s in sites:
        key = (s.get("name", ""), s.get("api", ""), s.get("ext", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    payload = {
        "sites": uniq,
        "_generated_at": now_str(),
        "_site_count": len(uniq),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return len(uniq)


def now_str():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S (UTC+8)")


# --------------------------------------------------------------------------
def main():
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    os.makedirs(DIST, exist_ok=True)

    excludes = cfg.get("live_exclude_keywords", [])
    includes = cfg.get("live_include_keywords", [])

    # ---- 直播源 ----
    raw_items, live_report = [], []
    for src in cfg.get("live_sources", []):
        name, url = src.get("name", "?"), src["url"]
        try:
            text = fetch(url)
            got = parse_playlist(text, default_group=name)
            raw_items.extend([(n, u, lg, g, name) for (n, u, lg, g) in got])
            live_report.append(f'| {name} | ✅ | {len(got)} |')
        except Exception as e:                          # noqa: BLE001
            live_report.append(f'| {name} | ❌ {str(e)[:60]} | 0 |')

    channels = dedup(raw_items, max_per_channel=3, excludes=excludes, includes=includes)
    n_m3u = write_m3u(channels, os.path.join(DIST, "live.m3u"))
    write_txt(channels, os.path.join(DIST, "live.txt"))

    # ---- TVBox 点播源 ----
    sites, tvbox_report = [], []
    for src in cfg.get("tvbox_sources", []):
        name, url = src.get("name", "?"), src["url"]
        try:
            text = fetch(url)
            got = parse_tvbox_json(text)
            sites.extend(got)
            tvbox_report.append(f'| {name} | ✅ | {len(got)} |')
        except Exception as e:                          # noqa: BLE001
            tvbox_report.append(f'| {name} | ❌ {str(e)[:60]} | 0 |')
    n_sites = write_tvbox(sites, os.path.join(DIST, "tvbox.json"))

    # ---- 报告 ----
    groups = {}
    for c in channels:
        groups[c["group"] or "未分组"] = groups.get(c["group"] or "未分组", 0) + 1
    top_groups = sorted(groups.items(), key=lambda x: -x[1])[:15]

    rep = [
        "# 订阅聚合报告",
        "",
        f"生成时间：{now_str()}",
        "",
        "## SenPlayer 订阅地址",
        "",
        "复制下面对应的 Raw 链接，SenPlayer → IPTV 直播 → 添加订阅 → 粘贴即可。",
        "（把 `<你的用户名>/<仓库名>/<分支>` 换成你自己的）",
        "",
        "```",
        "https://raw.githubusercontent.com/<你的用户名>/<仓库名>/<分支>/dist/live.m3u",
        "https://raw.githubusercontent.com/<你的用户名>/<仓库名>/<分支>/dist/live.txt",
        "```",
        "",
        "国内访问不畅时改用 jsDelivr：",
        "",
        "```",
        "https://cdn.jsdelivr.net/gh/<你的用户名>/<仓库名>@<分支>/dist/live.m3u",
        "```",
        "",
        "## 本次直播源统计",
        "",
        f"- 上游原始条目：{len(raw_items)}",
        f"- 去重后频道：{len(channels)}",
        f"- 输出播放线路：{n_m3u}",
        "",
        "| 上游源 | 状态 | 抓到条目 |",
        "| --- | --- | --- |",
        *live_report,
        "",
        "### 频道分组 TOP",
        "",
        "| 分组 | 频道数 |",
        "| --- | --- |",
        *[f'| {g} | {n} |' for g, n in top_groups],
        "",
        "## TVBox 点播源（SenPlayer 不可用）",
        "",
        f"- 合并去重后站点：{n_sites}",
        "",
        "| 上游源 | 状态 | 站点数 |",
        "| --- | --- | --- |",
        *tvbox_report,
        "",
        "> 这三个上游是 TVBox 的 CSP 爬虫站配置，不是播放地址，SenPlayer 无法消费。",
        "> 这里只做原样聚合，供影视仓 / 猫影视 / TVBox 使用。",
        "",
    ]
    with open(os.path.join(DIST, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep))

    print(f"[OK] 直播：{len(raw_items)} 条原始 -> {len(channels)} 频道 / {n_m3u} 线路")
    print(f"[OK] TVBox：{n_sites} 站点")
    for line in live_report:
        print("   ", line)


if __name__ == "__main__":
    sys.exit(main())
