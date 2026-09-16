# design/archive — 历史快照（NON-NORMATIVE）

本目录是 Galatea 设计规范重建前的**历史快照**，仅供追溯，**不再具规范效力**。规范唯一来源为 `../HLD.md` 与 `../lld/`。

## 内容

- `card_01.md … card_06.md`：6 张设计卡照片的 Markdown 还原稿（2026-09-12 完成）。
  - card_01/02 ← `微信图片_…043506/…043519`（DOC:00 认知架构 1/2、2/2）
  - card_03/04 ← `微信图片_…043530/…043538`（DOC:01 软件架构 1/2、2/2）
  - card_05/06 ← `微信图片_…043545/…043555`（DOC:02 开发计划 1/2、2/2）
- `微信图片_*.jpg`：6 张原始屏幕照片（卡片源材料）。

## 还原与修复注记（2026-09-12）

1. **OCR 修正 7 处**：card_01 架构图补 `⇄`（Self Model ⇄ Functional Affect）；card_03 "未闭栈"→"未闭合"；card_04 "能力相约"→"能力契约"、"生成交 digest"→"生成父 digest"；card_05 符号 `Ÿ/Ž`→`Y/Z`（对齐同卡 M0 行）；card_06 "无合类旁路"→"无各类旁路"、"保护集或难否决"→"保护集回退否决"。
2. **跨卡一致性修复 3 处**（经照片复核为源卡片自身不一致）：card_02 §4 表格 E1/P1 合并行拆为 E1/H1/P1 三行；card_02 "不可颠倒"链补 F0 起点；card_04 测试链补 protection suite、card_06 测试金字塔补 Security（统一为含两者的超集）。
3. **更名**：Helios → Galatea（8 处，2026-09-12 owner 指定新项目名）。
4. **术语更名**：HIO（Helios I/O）→ PhysIO（Physical I/O）（2026-09-12 owner 裁决 Q-N01；含 card_02/03/04/06 正文与派生标识符 PhysIO Bridge / PhysIOControlGraph，各卡头部已加更名注记）。
5. **编码事故**：更名批处理曾因 PowerShell ANSI/GBK 默认编码损毁 card_02/03/04/06，已按原文重建为 UTF-8 无 BOM（详见 `../HLD.md` 附录 A.6）。

## 源文档状态

卡片对应的三份源文档 `00_ARCHITECTURE_OVERVIEW.md`(v3) / `01_SOFTWARE_ARCHITECTURE.md`(v1.1) / `02_DEVELOPMENT_PLAN.md`(v1.1)，以及旧 HLD/LLD，**已确认不可获得**。卡片头部"不得替代或覆盖源文档"的从属声明随源文档缺失而失效；现行规范以重建的 `../HLD.md` + `../lld/` 为准。
