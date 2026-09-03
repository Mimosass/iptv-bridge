# iptv-bridge

把散落在各处的上游订阅，聚合成 **SenPlayer 能直接订阅的一个地址**，并随上游自动更新。

---

## 先说结论：你给的那三个链接，SenPlayer 用不了

```
https://raw.githubusercontent.com/cysk003/XPTV/refs/heads/main/VOD/AV.json
https://raw.githubusercontent.com/fangkuia/XPTV/refs/heads/main/VOD/XPTV.json
https://raw.githubusercontent.com/xiaobaitulele/xptv/refs/heads/main/main/all_direct.json
```

抓下来看，三个文件的结构完全一样，都是 TVBox 的点播站配置：

```json
{
  "sites": [
    {
      "name": "哔滴影视",
      "type": 3,
      "api": "csp_bde4",
      "ext": "https://.../js/bdys.js"
    }
  ]
}
```

- 频道数分别是 **21 / 25 / 29** 个站点，全部是 `type: 3`
- `type: 3` + `api: "csp_xxx"` 意味着它是 **CSP 爬虫脚本**，不是播放地址
- `ext` 指向的是 `.js` 爬虫文件，需要 TVBox 内核执行后才能拿到真正的视频链接

而 SenPlayer 的 IPTV 只认 **M3U / M3U8 / TXT**，里面必须是 `频道名 + 真实可播放地址`（`.m3u8` / `.flv` / 直链）。它不会执行 JS，也不认识 `csp_` 这种爬虫协议。

所以：**不是格式不兼容，是数据性质不兼容。** 转格式救不了它，硬转出来每个"频道"点开都是一段 JS 文本，必然播放失败。

> 这三个源的正确用法是填进 **TVBox / 影视仓 / 猫影视 / Fongmi** 这类点播壳子。
> 另外提醒：这三个源里有相当比例是成人站点，别往家庭共用设备上放。

---

## 这套东西能给你什么

### 1. 直播源聚合 —— SenPlayer 真正能用的部分

`config.json` 里预置了 5 个公开直播源，脚本把它们抓下来、按频道名去重、每个频道最多保留 3 条备用线路，输出两个文件：

| 文件 | 用途 |
| --- | --- |
| `dist/live.m3u` | SenPlayer 订阅这个（推荐） |
| `dist/live.txt` | 备选，TXT 格式 |

本次实测：699 条原始 → 530 个频道 / 627 条线路。

### 2. 点播源聚合 —— 给你手里的 TVBox 用

你那三个 JSON 我也没浪费，原样合并去重后输出 `dist/tvbox.json`（75 个站点），喂给影视仓这类 App 即可。

### 3. 自动更新 —— 不用再手动管

GitHub Actions 每 6 小时自动重跑一次，上游改了这边跟着变。上游某个源挂了会自动跳过，不会中断整个流程。

---

## 三步搞定

### 第一步：Fork / 上传

把整个目录传到一个你自己的 GitHub 仓库（公开仓库才能用 Raw 订阅）。

### 第二步：开 Actions 权限

`Settings → Actions → General → Workflow permissions` 选 **Read and write permissions**。

然后进 `Actions → 更新订阅 → Run workflow` 手动跑一次，`dist/` 目录下就会生成文件。

### 第三步：SenPlayer 订阅

SenPlayer → IPTV 直播 → 添加订阅，粘贴：

```
https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/dist/live.m3u
```

国内直连 GitHub 不畅的话，换成 jsDelivr（同一份内容，CDN 加速，有约 12 小时缓存延迟）：

```
https://cdn.jsdelivr.net/gh/<你的用户名>/<仓库名>@main/dist/live.m3u
```

> jsDelivr 有缓存，改完源不会立刻生效，急的话就手动 purge：`https://purge.jsdelivr.net/gh/<用户名>/<仓库名>@main/dist/live.m3u`

---

## 换成你自己的源

编辑 `config.json`，`live_sources` 里每一项加一个 `{"name": "...", "url": "..."}`，push 上去即可。脚本同时兼容三种写法：

- 标准 M3U（带 `#EXTINF` 和 `tvg-logo`、`group-title`）
- TXT 逗号式：`频道名,http://xxx.m3u8`
- TXT 反序：`http://xxx.m3u8,频道名`

其它可调项：

```jsonc
"live_include_keywords": [],              // 留空=全要；填了就只保留含这些词的频道
"live_exclude_keywords": ["色情", "XXX"], // 按频道名过滤
```

想换干净的国际频道源，可以换这两个（都是社区维护、只收合法免费频道）：

```
https://iptv-org.github.io/iptv/index.m3u           // iptv-org 全量，约 1.2 万条
https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8   // Free-TV，少而精
```

---

## 本地试跑

```bash
python3 scripts/build.py
```

产物在 `dist/`，同时会生成一份 `dist/README.md` 统计报告。

---

## 几句提醒

- 公开直播源属于互联网搜集的第三方信号，**稳定性没保障**，失效是常态，这也是为什么要做自动更新 + 每频道保留多条备用线路。
- 建议优先走官方渠道（央视频、咪咕视频、各卫视官方 App），这套方案更适合当作备用和折腾。
- 请勿商用。
