# 订阅聚合报告

生成时间：2026-09-04 05:04:42 (UTC+8)

## SenPlayer 订阅地址

复制下面对应的 Raw 链接，SenPlayer → IPTV 直播 → 添加订阅 → 粘贴即可。
（把 `<你的用户名>/<仓库名>/<分支>` 换成你自己的）

```
https://raw.githubusercontent.com/<你的用户名>/<仓库名>/<分支>/dist/live.m3u
https://raw.githubusercontent.com/<你的用户名>/<仓库名>/<分支>/dist/live.txt
```

国内访问不畅时改用 jsDelivr：

```
https://cdn.jsdelivr.net/gh/<你的用户名>/<仓库名>@<分支>/dist/live.m3u
```

## 本次直播源统计

- 上游原始条目：700
- 去重后频道：530
- 输出播放线路：627

| 上游源 | 状态 | 抓到条目 |
| --- | --- | --- |
| iptv-org 中国大陆 | ✅ | 502 |
| iptv-org 香港 | ✅ | 19 |
| iptv-org 台湾 | ✅ | 52 |
| 范明明 Global | ❌ 抓取失败 https://live.fanmingming.com/tv/m3u/global.m3u：HTTP Err | 0 |
| YanG 集合源 | ✅ | 127 |

### 频道分组 TOP

| 分组 | 频道数 |
| --- | --- |
| iptv-org 中国大陆 | 337 |
| •游戏「赛事」 | 54 |
| iptv-org 台湾 | 51 |
| •咪咕「移动」 | 42 |
| •影视「轮播」 | 27 |
| iptv-org 香港 | 15 |
| •温馨「提示」 | 4 |

## TVBox 点播源（SenPlayer 不可用）

- 合并去重后站点：75

| 上游源 | 状态 | 站点数 |
| --- | --- | --- |
| cysk003 AV | ✅ | 29 |
| fangkuia XPTV | ✅ | 21 |
| xiaobaitulele all_direct | ✅ | 25 |

> 这三个上游是 TVBox 的 CSP 爬虫站配置，不是播放地址，SenPlayer 无法消费。
> 这里只做原样聚合，供影视仓 / 猫影视 / TVBox 使用。
