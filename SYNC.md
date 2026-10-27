# 同步约定

## 触发

掌印 / 目力 **确认当日三条推送都已落盘** 之后，跑一次 sync。不要每写完一个文件就部署。若某一天只确认了其中一条，也可以只 upsert 那一条；已有日期不会被删掉。

给机器人的一句话：

> 三条流都确认后，运行 `python3 scripts/ingest.py --brief <vault根目录>`，提交 `content/`、`index.html`、`data/catalog.json`，push `main`。

## 三条本地文件

工作目录里认这些路径（日期用 `YYYY-MM-DD`）：

| 流 | 文件 | 聚类 |
| --- | --- | --- |
| 每日摄影师 | `daily/YYYY-MM-DD/recommendation.md` | 作者 |
| 每日审美一课 | `daily/YYYY-MM-DD-aesthetic/lesson.md` | 风格 / 类型 |
| 28mm 专题 | `28mm/YYYY-MM-DD/lesson.md` | 焦段 |

只把 `lesson.md` / `recommendation.md` 当正课。`28mm` 下面的 garden 出行参考、`SOURCES.md`、聊天稿，不会单独入库。审美目录里不要放构图技法课。

若当日文件缺失，脚本会到这三份长卷里补同日小节：

- `作者长卷.md` 的「每日推送」（不收「专题批次」）
- `审美词本.md`
- `广角手记.md`

当日正文很短、又没有图，而长卷里已有同日完整小节时，用长卷补全文和图片。

图片只用文中的 CDN 地址：

`https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/<文件名>`

CDN 返回 404 的地址会被丢掉，不放进页面。不要把 jpg / png / webp 提交进这个仓库。

## 命令

在本仓库根目录：

```bash
python3 scripts/ingest.py --brief /path/to/目力工作目录
```

脚本会：

1. 读取上面的 markdown，抽出日期、标题、标签、CDN 图和图注、外链
2. upsert 到 `content/photographer|aesthetic|28mm/YYYY-MM-DD.md`
3. 重写 `index.html` 和 `data/catalog.json`

每篇内容的 front matter：

```yaml
date: "2026-10-27"
title: "Trent Parke（大师 · 澳大利亚）"
stream: "photographer"    # photographer | aesthetic | 28mm
subtitle: "..."
summary: "..."
category: "大师"
tags: ["大师", "澳大利亚"]
thumbs: [{"src": "https://fastly.jsdelivr.net/...", "alt": "...", "caption": "..."}]
links: [{"label": "Magnum", "url": "https://..."}]
```

然后：

```bash
git add content index.html data/catalog.json
git commit -m "feat: ingest 2026-10-27"
git push origin main
```

推到 `main` 且碰到页面或 `content/` 时，Actions 工作流「Deploy GitHub Pages」会部署到 <https://senlau.github.io/muli/>。只想重新部署、不改内容时，在 GitHub 上对该工作流点 Run workflow。

可选：探测图片宽高，避免版心跳动。

```bash
python3 scripts/ingest.py --brief /path/to/目力工作目录 --probe
```

## 其它入口

全量 JSON（`streams.photographer` / `aesthetic` / `mm28`）灌入。`--brief` 在这个模式下只补图注和缺图，不改 JSON 正文：

```bash
python3 scripts/ingest.py --json path/to/content.json --brief /path/to/brief --probe
```

只改了 `content/*.md`，不读外部目录：

```bash
python3 scripts/ingest.py --from-content
```

自测解析器：

```bash
python3 scripts/ingest.py --self-test
```

删一则：删掉对应的 `content/.../YYYY-MM-DD.md`，再跑 `--from-content`。
