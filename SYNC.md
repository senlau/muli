# 同步约定

## 触发

掌印 / 目力 **确认当日推送都已落盘** 之后，跑一次 sync。不要每写完一个文件就部署。若某一天只确认了其中一条，也可以只 upsert 那一条；已有日期不会被删掉。

给机器人的一句话：

> 推送确认后，运行 `python3 scripts/ingest.py --brief <vault根目录>`，`git add -A` 提交 `content/`、生成的页面和 `data/catalog.json`，push `main`。

摄影与人生（vault 里叫意义长卷）和另外三个栏目相对独立，不定期更新。

## 四个栏目的本地文件

工作目录里认这些路径（日期用 `YYYY-MM-DD`）：

| 栏目 | 文件 | 生成的文章页 |
| --- | --- | --- |
| 摄影师 | `daily/YYYY-MM-DD/recommendation.md` | `photographer/YYYY-MM-DD.html` |
| 视觉语言 | `daily/YYYY-MM-DD-aesthetic/lesson.md` | `aesthetic/YYYY-MM-DD.html` |
| 28mm 专题 | `28mm/YYYY-MM-DD/lesson.md` | `28mm/YYYY-MM-DD.html` |
| 摄影与人生 | `daily/meaning-stories/YYYY-MM-DD/` 或 `意义长卷.md` | `meaning/YYYY-MM-DD-{slug}.html` |

只把 `lesson.md` / `recommendation.md` 当正课。`28mm` 下面的 garden 出行参考、`SOURCES.md`、聊天稿，不会单独入库。视觉语言只谈风格和类型，不要放构图技法课；站位、换位留在 28mm 专题。

摄影与人生：
- 同一日期可有多条故事（按作者/主题分 slug），文件名 `YYYY-MM-DD-{slug}.md`
- 长卷 `意义长卷.md` 用 `### YYYY-MM-DD｜作者：标题` 分节，解析时按小节拆成多条
- 每条需有 `slug` 字段（如 `goldrei`、`tara`、`bryce`、`dukhan`）以区分同日多条；同步按日期和 slug 一起匹配，同日几条不会互相覆盖

若当日文件缺失，脚本会到这几份长卷里补同日小节：

- `作者长卷.md` 的「每日推送」（不收「专题批次」）
- `审美词本.md`
- `广角手记.md`
- `意义长卷.md`

当日正文很短、又没有图，而长卷里已有同日完整小节时，用长卷补全文和图片。

## 图片

图片只用文中的 CDN 地址：

`https://fastly.jsdelivr.net/gh/senlau/picx-images-hosting@master/muli/<文件名>`

不要把 jpg / png / webp 提交进这个仓库。非 HTTPS 的图片地址会让脚本直接报错退出。

可选：探测图片宽高，避免版心跳动。宽高写进 front matter 的 `w` / `h`，探测结果缓存在 `data/dimensions.json`（本地缓存，不提交）。加 `--probe` 时，CDN 返回 404 的图会被丢掉，不放进页面。

```bash
python3 scripts/ingest.py --brief /path/to/目力工作目录 --probe
```

## 命令

在本仓库根目录：

```bash
python3 scripts/ingest.py --brief /path/to/目力工作目录
```

脚本会：

1. 读取上面的 markdown，抽出日期、标题、标签、CDN 图和图注、外链
2. upsert 到 `content/<栏目>/YYYY-MM-DD.md`（摄影与人生是 `YYYY-MM-DD-{slug}.md`）；标了 `edited: true` 的文件不动
3. 重写全部页面：`index.html`、`learn.html`、`practice.html`、`life.html`、`archive.html`，每篇一页的 `photographer/` `aesthetic/` `28mm/` `meaning/`，以及 `data/catalog.json`
4. `content/` 里已经没有的文章，对应的旧文章页会被删掉

然后：

```bash
git add -A
git commit -m "feat: ingest 2026-10-28"
git push origin main
```

只提交 `content/ index.html data/catalog.json` 不够：栏目页和文章页都是单独的文件，要一起提交，本地预览才是新的。

推到 `main` 且改到 `content/`、页面、`scripts/`、样式或字体时，Actions 工作流「Deploy GitHub Pages」先跑 `--self-test`，再用 `--from-content` 重新生成全部页面，然后部署到 <https://senlau.github.io/muli/>。所以线上永远以 `content/` 为准。只想重新部署、不改内容时，在 GitHub 上对该工作流点 Run workflow。

## 每篇内容的 front matter

每行一个字段，值是 JSON：

```yaml
date: "2026-10-28"
title: "何藩 Fan Ho"
stream: "photographer"    # photographer | aesthetic | 28mm | meaning
subtitle: "香港 · 光楔与剪影"
summary: "他用楼梯、烟尘和从楼缝楔进来的阳光……"   # 导语：标题下、卡片和 meta description 都用它
category: "大师"
tags: ["轮廓与剪影"]
topics: ["轮廓与剪影"]     # 可选：主题，归档「按主题」和文末「同一主题」
people: ["何藩 Fan Ho"]    # 可选：归档「按作者」
thumbs: [{"src": "https://fastly.jsdelivr.net/...", "alt": "...", "caption": "...", "w": 1200, "h": 800}]
links: [{"label": "M+ 何藩馆藏", "url": "https://..."}]
credit: "图片：..."        # 可选：文末的图片出处
slug: "goldrei"           # 仅 meaning 需要，用于同日多条区分
edited: true              # 可选：人工编辑过，同步不再覆盖
featured: true            # 可选：指定首页的本期精选
```

- `topics` 的名字对应 `content/topics.json` 里的 `name`，那里定 slug（`archive.html#topic-<slug>`）和排序。新名字会自动成为一个主题，但 slug 是自动生成的；长期用的主题请加进 `topics.json`。
- `thumbs[0]` 是卡片、首页大图和分享图。`thumbs` 里的图都应在正文出现一次；没放进正文的会补在第一个有图的小节末尾。
- `links` 进文末「作品与延伸阅读」。正文里已经链过的地址不再重复列出。
- 首页的本期精选默认取最新一天、按 摄影师 → 视觉语言 → 28mm 专题 → 摄影与人生 的顺序第一篇有图的文章。`featured: true` 会一直置顶（有多篇时取最新的一篇），换期时记得去掉。

## 编辑过的文章

人工改过的文章标 `edited: true`。之后 `--brief` 和 `--json` 都不会覆盖它，标题、副题、导语按原样显示。想换回 vault 原文：删掉这个文件再同步。只删 `edited` 这一行不够，已有的长正文不会被替换，同步只会补图。

正文是 markdown。各栏目的顺序：

| 栏目 | 结构 |
| --- | --- |
| 摄影师 | 一张主图＋两三句导语 → `## 作品观察`（每张作品一个 `###`，下面放图和一段观察）→ `## 看片时注意` → `## 风格对照` → `## 常见构图问题`（可选）→ `## 今日练习` → `## 书与系列` |
| 视觉语言 | `## 核心判断` → `## 作品观察`（`### 作者 — 作品, 年份`）→ `## 为什么成立` → `## 风格对照` → `## 常见问题` → `## 今日练习` |
| 28mm 专题 | `## 核心判断` → `## 作品观察` → `## 为什么是 28mm` → `## 怎么站`（可选）→ `## 风格对照` → `## 常见问题` → `## 今日练习` |
| 摄影与人生 | 一张主图，然后图文交替的叙述，不分节，每张图后面都要有文字 → `## 可以借用的做法` → `## 资料来源` |

渲染规则：

- `## 核心判断` 单独成块，不编号；其余 `##` 按顺序编号（`01 / 作品观察`）。摄影与人生不编号，`资料来源` 也不编号。
- `今日练习` 和 `可以借用的做法` 显示成框。
- 紧跟在 `###` 后面的图，用小标题当图注，不再重复 `thumbs` 里的 caption；其他位置的图显示 caption。图一律按原比例，不裁切。
- 站内互链写成 `[轮廓分离](#aesthetic-2026-10-27)`，会变成指向那篇文章页的链接；目标不存在时只留文字。

没标 `edited` 的同步稿，脚本会做一层兜底：小标题改成站内用语（跟锚点的关系 → 风格对照，同类场面常见废法 → 常见构图问题，可练一句 → 今日练习），删掉「入口」「类别」这类小节和反馈、推送记录等工作笔记，再按 核心判断 → 作品 → 分析 → 练习 → 书与资料 重排。兜底只是保底，读过一遍、改好后再标 `edited: true`。

## 其它入口

全量 JSON（`streams.photographer` / `aesthetic` / `mm28`）灌入。`--brief` 在这个模式下只补图注和缺图，不改 JSON 正文；本地已标 `edited: true` 的文章保留本地版本：

```bash
python3 scripts/ingest.py --json path/to/content.json --brief /path/to/brief --probe
```

只改了 `content/*.md` 或 `content/topics.json`，不读外部目录：

```bash
python3 scripts/ingest.py --from-content
```

自测解析器和页面生成：

```bash
python3 scripts/ingest.py --self-test
```

删一则：删掉对应的 `content/.../YYYY-MM-DD.md`，再跑 `--from-content`，它的文章页会一起删掉。

## 改版迁移

改版前全站是一页 `index.html`，现在是栏目页加每篇一页。迁移时注意：

- front matter 只新增了可选字段（`topics`、`people`、`credit`、`edited`、`featured`），原有字段的名字和含义都没变，旧文件照常解析。
- 现有 21 篇都已人工改过并标了 `edited: true`，同步不会再覆盖。
- 旧深链（`#photographer-2026-10-27`、`?tab=mm28&entry=…` 等）由 `index.html` 转到新页面，对照表见 [README](README.md)。
- 提交时改用 `git add -A`，否则新生成的页面会漏提交。
