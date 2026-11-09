# Story 6-11: 白标报告基础（品牌模板配置——保存/复用/白标 PDF 渲染 + CLI 命令族 + 6-10 品牌段联动）

**Status:** `review`

> **Note:** 本 Story 严格遵循 **SDD 规范驱动 + TDD 测试驱动** 融合模式。
> 每个 Task 必须独立完成完整的 TDD 红→绿→重构循环，禁止将测试编写与代码实现分离。
> 运行文档审查修订循环（参照 6-8/6-9/6-10 五轮形态）+ 人工按 story-template 合规清单核对后再执行 `dev-story`。

---

## 📖 Story 描述

**As a** 专业顾问（咨询/投资/银行）,
**I want** 配置基础品牌模板（上传 Logo、选择配色[预设 3 套]、选择字体[预设 2 种]）并保存为可复用模板，在导出 PDF 报告时品牌元素 100% 准确应用,
**So that** 可以直接交付客户，验证 MVP 付费意愿（epics L2518-2533 用户价值与 AC 三要素）。

### 业务价值

- **Epic 6 价值组「战略规划与审批能力」的白标交付面收口**：生成侧（6-1~6-5b）、审批侧（6-6）、溯源面（6-7）、高管速览（6-8）、分析师作业（6-9）、顾问面板（6-10）已 done——本 Story 交付 **P0-11 白标报告基础**（epics L2021 依赖行钦定「依赖 Story 6.5a——白标报告基础仅需 Markdown 基础，品牌配置可独立实现」L2036），是 Epic 6 最后一个功能 Story（其后仅剩 epic-6-retrospective）
- **四笔显式移交的兑现 Story**：①6-5b OD-9「位图渲染（品牌 logo/图表）归 6-11——reportlab Image 能力届时启用」（本 Story 首启 `platypus.Image`——reportlab 链零 Image 使用亲验，platypus 导入 :41-48 无 Image）；②6-5b OD-11「6-11 白标模板参数同入口扩展（--format 参数形态）」（本 Story `report-generate --brand-template` 同入口扩展）；③6-10 OD-6「configured 键是 6-11 对接锚——届时端口演进 v1.1.0 读配置面」（本 Story consultant_view v1.1.0 联动兑现）；④6-5a OD-10「报告版本链管理归 6-11 白标多模板立项定夺」（本 Story OD-1 裁定不立项——既有同 plan 多行版本链天然保留旧报告，白标导出不改变版本链面）
- **FR Coverage Map 无独立 FR**（同 6-6~6-10 形态第六连）：REST 白标面 `POST /reports/whitelabel` 归 FR-SP-16（P2）→ Epic 20 Story 20.4（epics L232/L600/L714——Epic 20 仅 backlog 无 Story 小节亲验）；监管报告导出 `POST /reports/regulatory` 同归 20.4（interface-design.md:1484-1489 §8.2.8 规划位）；Web 可视化品牌编辑器归 Epic 21/22（**亲验：Epic 21 九 Story 与 Epic 22 八 Story 均无品牌专属 Story**——UX spec 旅程 8「品牌配置旅程」:2100-2131 全是 Web 面口径[SVG/PNG 上传裁剪/色板/字体预览/质量评分≥9/10]，归后续 Web Story 立项，本 Story 不预建）；本 Story 交付**配置持久化 + 白标渲染 + CLI 呈现**（Epic 6 第十个 CLI-only Story——6.1-DF5 九连先例延续；openapi.yaml 零 diff）
- **首次激活的能力面**：reportlab 位图渲染（platypus.Image）+ TTF 字体注册通道（全仓零 TTFont 注册、零 .ttf/.otf 资产亲验——第二字体预设需新增字体资产分发）+ 品牌配置持久化面（brand_templates PG 表 018 migration——「用户可编辑结构化配置 = PG 表」仓标准，3-3 字典/documents/strategic_reports 三先例一致）
- **Epic 6 内部顺序**：6-10（done，顾问交付面）→ **6-11（本 Story，白标报告基础）** → epic-6-retrospective（optional）

### 范围边界（出处逐行声明）

| 面（出处） | 已交付（禁重复造轮） | 6-11 增量（本 Story） |
|---|---|---|
| 报告生成双链（6-5a/6-5b） | `generate_markdown_report` 五段编排（report_generation_service.py:154-193）+ `generate_pdf_report` 六段编排（pdf_report_generation_service.py:154-229：聚合→引文→渲染 :185 单实参→L4 WORM :189-198→L2 行→事件）+ CLI `report-generate --plan-id --format {markdown,pdf}`（agent_cli.py:342-360）+ `strategic_reports` 表（017 migration）+ `ReportGenerated` 事件（report_type 自由 str :57-72） | **零新入口**：白标导出 = `report-generate --format pdf --brand-template <name>` 同入口扩展（6-5b OD-11 钦定）；`generate_pdf_report` v1.1.0 增可选品牌参；metadata JSONB 顶层增品牌两键 brand_template_id/brand_applied（JSONB 自由扩展零 migration——顶层键=聚合基底+citation 族键[基数不定]之上追加；citations 条目七键 :416-427 是嵌套扩展先例）；report_type 沿用 "pdf" 零新增（OD-5） |
| PDF 渲染器（6-5b） | `ReportLabPdfRenderer`（reportlab_pdf_renderer.py）——CID 字体 `_FONT_NAME="STSong-Light"` :60 幂等注册 :109-117；四处硬编码色 :305/:313/:374-375；`_style()` base dict :390-402；`render(document)` 单参 :184-214 | **品牌应用扩展**：`PdfRendererPort.render` v1.0.0→v1.1.0 增 keyword-only 可选参 `brand: BrandRenderSpec \| None = None`（默认 None 走既有路径——零品牌调用等价回归[invariant=1 测试前置下 byte 级对照]）；字体/配色参数化 + platypus.Image logo 绘制（首启）+ TTF 注册通道（`_ensure_font` 幂等扩展——`_FONT_REGISTERED` 单布尔字典化） |
| 品牌配置存储（本 Story 新域） | **零存量**（词族 brand/white_label/logo src 实质命中仅 6-10 consultant_view 三文件[BrandSection/BRAND_* 两常量/CLI 文案]；品牌配置无表、无端口、无上传通道——6-10 范围边界表 L32 亲验移交在档） | **新建全链**：domain `BrandTemplate` 实体 + `BrandTemplateRepositoryProtocol`（R1 基础端口）+ PG 表 `brand_templates`（018 migration）+ `PostgreSQLBrandTemplateRepository` + 应用层 `BrandTemplateServicePort`/`BrandTemplateService`（预设常量+校验+L4 logo 通道） |
| 品牌段展示（6-10） | `BrandSection` 5 键恒默认态（consultant_view.py:120-135——零 IO 静态段；`_build_brand_section` 纯常量构造 service:173-186）；`configured` 恒 False 是 6-11 对接锚（docstring 触发器注记 :27-28/:31-34） | **v1.1.0 演进兑现**：品牌段改读配置面（`_build_brand_section` 注入第三依赖 brand_template_repository——最新模板派生 configured/三 status；零模板→默认态值不变[6-10 断言前提演进为零模板]；查询异常→degraded=True[零 IO 恒稳承诺打破——v1.1.0 docstring 勘误注记]）；6-10 测试面三处联动更新（Task 6 义务清单） |
| 白标 REST 导出面（Epic 20） | `POST /reports/whitelabel` 归 FR-SP-16 P2 → Epic 20 Story 20.4（epics L600/L714；interface-design.md:1488 规划位）——未立项 | **不做**（CLI-only 第十连——openapi.yaml 零 diff） |
| Web 品牌编辑器（UX） | UX spec 旅程 8（:2100-2131）九阶段全 Web 面口径（上传裁剪预览/色板/字体预览/模板选择器/质量评分）；Epic 21/22 无品牌 Story | **不做**（CLI `--logo-path` 本地路径直传形态承载上传语义；裁剪/预览/评分归后续 Web Story） |
| 多租户品牌隔离（1-11/后续） | 1-11 交付合规面；brand_templates 表无 tenant 列（与 strategic_reports/strategic_archives 同口径）；MVP 单租户 `MVP_TENANT_ID` 先例（pdf_report.py:54-58 docstring） | **单租户口径**：模板全局共享（跨 plan 复用语义本义）；Schema per Tenant 完整实现归租户管理后续 Story（6-10 OD-1 注记直系） |
| 批量报告管线（L129 锚） | `orchestration_service/data_pipeline` 轨休眠——再锚定条件原文含「6-11 白标多用户场景或 Epic 7」（deferred-work L129，五轮维持注记在档） | **显式不做批量+锚位收敛**（OD-8）：白标导出=单 plan 单次生成归 report-generate 既有入口（第六轮同构裁定）；**6-11 分支已消费**——再锚定条件收敛为「Epic 7 API 入口立项」（批量分支注销注记落档） |
| 报告版本链管理（6-5a OD-10 移交） | strategic_reports 同 plan_id 多行天然保留（OD-10 幂等锚=report_id；无唯一约束拦截）；`get_latest_by_plan` created_at 降序+report_id tie-break（report_repository.py:163-180） | **不立项裁定**（OD-1）：白标多模板导出不改变版本链面——旧报告（含白标/非白标）天然保留，latest 语义不变；「显式版本管理 UI/旧报告清理策略」归产品立项（无消费方 YAGNI） |

---

## ✅ Acceptance Criteria 验收标准

### AC-1: 品牌模板保存与预设校验（BrandTemplate 实体 + PG 持久化 + UPSERT 语义）

**Given** 顾问已登录（CLI 一次性进程——CLI 面无角色门槛注记，6-10 先例第三连；epics L2526 Given「并创建项目」在 CLI 配置面无 plan 前置——品牌模板不锚定 plan[见 AC-3]，口径差声明）且品牌模板表可写（018 migration 后）
**When** 执行 `sisys-agent brand-template-save --name <name> --color-scheme <key> --font-preset <key> [--logo-path <本地路径>]`（编程面 `SaveBrandTemplateUseCase.execute(name=..., color_scheme=..., font_preset=..., logo_path=...)`）
**Then** 保存成功返回 `BrandTemplate` 实体（**7 字段**：template_id[UUID——首次新建生成，同名更新保留原值]/name/color_scheme/font_preset/logo_object_key[str|None——仅当 logo_path 在场时非 None]/created_at/updated_at）并持久化 PG `brand_templates` 行：
- **UPSERT by name 语义**（同名=修订覆盖非冲突——钦定声明：CLI 面无 409 等价错误语义，同名保存是模板修订的预期用法）：首次→INSERT 新行；同名再存→UPDATE 该行（color_scheme/font_preset/logo_object_key/updated_at 更新，template_id/name/created_at 不变）。**保留语义与键锚定的承载位=服务侧**：save 编排服务先 `get_by_name`（同名取既有 template_id+logo_object_key——L4 对象键锚定既有 template_id 的前提），仓储仅按 template_id UPSERT 落库不承载保留判断（OD-12）；**updated_at 前进由服务构造实体时显式定值** `datetime.now(timezone.utc)`（report_repository 应用侧定时戳先例 :126-139——DDL server_default 仅 INSERT 初值；并发双 INSERT 撞 UNIQUE(name) 的 IntegrityError 由仓储捕获包装 495——CLI 单进程常态低概率，防御义务归仓储）
- **预设值域校验**：color_scheme ∈ `COLOR_SCHEME_PRESETS` 三键、font_preset ∈ `FONT_PRESETS` 两键（值域外 → `BrandTemplateValidationError` EXCEPTION_494——预设键值域校验落应用服务[domain 实体零 application import——依赖方向]，实体 `__post_init__` 仅守卫非空/长度 242）
- **实体构造守卫 242**：name 非空且 ≤100 字符；color_scheme/font_preset 非空且 ≤30 字符（domain 契约面）

**And** 预设常量单源冻结（应用层 `src/application/ports/brand_template.py` 模块级常量——TOOL_CATALOG/PHASE_STEP_DOMAINS「静态值域=冻结常量、PG 行只存 key」模式直系）：`COLOR_SCHEME_PRESETS` 3 套（corporate-blue 商务蓝/graphite 石墨灰/burgundy 酒红——每套 **5 色** hex 键族与 BrandRenderSpec 五色键一一对应[font_name 由 FONT_PRESETS 正交供给]，Task 0.2 冻结表钦定 hex 值）；`FONT_PRESETS` 2 项（stsong→STSong-Light CID 内置零注册/noto-sans-sc→TTF 注册——Task 0.2 冻结）

**验证标准/Validation Criteria:**
- [ ] 保存主链值级断言（PG 行读回七字段直推——template_id/name/color_scheme/font_preset/logo_object_key/created_at/updated_at[均非空]）
- [ ] UPSERT 两形态（首存 INSERT 新 template_id；同名再存 UPDATE template_id 不变+字段更新+updated_at 前进）[**验收面载体声明[R3]**：14 场景无 UPSERT 专场景——两形态由 Task 2 仓储单测（真实 PG）+Task 8 集成场景②承载，金字塔分布刻意取舍]
- [ ] 值域守卫负例全枚举（非法 color_scheme key/非法 font_preset key → 494；空 name/超长 name → 242）
- [ ] 预设常量值级断言（三键两键 exact set + 每套色键 hex 值与冻结表逐字一致——防漂移）

### AC-2: Logo 上传与格式守卫（L4 store 通道 + magic bytes 校验）

**Given** 顾问持有本地 Logo 图片文件（PNG/JPEG）
**When** `brand-template-save` 携带 `--logo-path` 执行
**Then** Logo 经 **L4 `store()`（非 WORM `archive()`）** 上传至新 bucket_type `"brand-assets"`（三段物理桶名 `{prefix}-brand-assets-{tenant_id}`——与 raw-documents/archive-evidence 并列；**resolve 通道组合根未传 tenant_id——物理桶恒 `{prefix}-brand-assets-default` 共享桶**[6-5b 集成共享桶先例]，隔离靠对象键锚 template_id；**测试前置桶自愈**：store 对缺桶抛 NoSuchBucket 且 src 零生产建桶——bucket_exists 探测+make_bucket 自愈且**勿带 object_lock**[WORM 锁破坏 logo 覆盖与 teardown 清理——与 archive-evidence 的 object_lock=True 建桶先例分立]；**勿入 archive-evidence WORM 桶**：logo 需可替换覆盖，WORM 7 年 retention 反语义——裁定依据），对象键锚 template_id 单键覆盖 `logos/{template_id}`（无 ext 后缀——content_type 承载 image/png|image/jpeg；换格式重传同键覆盖零垃圾对象）；PG 行 logo_object_key 回填该键（**documents 先例同构**：document_upload_service.py:151 PG 元数据行持 MinIO object key 双写）
**And** 格式守卫（服务层校验，**先于 L4 调用**）：①magic bytes 判定（stdlib 前 8 字节：PNG `\x89PNG\r\n\x1a\n`/JPEG `\xFF\xD8\xFF`——非二者 → 494，消息含合法格式说明）；②大小上限 2MB（`os.path.getsize`——超限 → 494，防误传大图渲染 OOM）；③路径不存在/不可读 → 494（isfile 否定+getsize/open 的 OSError 族伞形——R1-F3 补强：chmod-000 真实语义链红在 open 位）；④像素维度上限 4000px+图像体可解析（PIL 惰性读头——超限/`UnidentifiedImageError` → 494，R1-F6 补强：2MB 字节上限不约束解码内存[实测 9000×9000 白底 PNG 仅 258KB 而渲染峰值 RSS 1.1GB；10×20000 → LayoutError]——保存期 fail-fast 前移渲染期 492）
**And** logo 省略形态：`--logo-path` 缺席 → logo_object_key=None（模板可无 logo——配色/字体独立生效；已有 logo 的模板再存不带 --logo-path → **保留原 logo**钦定[修订语义：缺席≠清除，清除归后续模板管理 Story]）

**验证标准/Validation Criteria:**
- [ ] Logo 主链（L4 对象在场上传成功 + PG 行键回填 + L4 读回 bytes 与源文件逐字节相等）
- [ ] magic bytes 负例（文本文件/空文件 → 494 且 L4 零调用——spec Mock await_count==0 断言）
- [ ] 大小上限负例（>2MB 构造文件 → 494）
- [ ] 路径不存在负例（→494）
- [ ] 不可读负例（chmod-000 真文件[geteuid==0 动态 skip]+getsize TOCTOU 补充格 → 494「不可读」——R1-F3）
- [ ] 像素/解析负例（1×4001 PNG 超限 → 494；PNG magic+垃圾体图像体不可解析 → 494；4000×4000 恰值通过边界格——R1-F6）
- [ ] 省略保留语义（带 logo 保存→不带 --logo-path 再存→logo_object_key 不变+L4 零新调用）

### AC-3: 模板列表与复用入口（CLI brand-template-list + report-generate 同入口扩展）

**Given** 库中有 ≥2 个品牌模板行（预置或 AC-1 保存产物）
**When** 执行 `sisys-agent brand-template-list`（**零参数**——全局模板清单；编程面 `ListBrandTemplatesUseCase.execute() -> tuple[BrandTemplate, ...]`）
**Then** CLI 结构化输出：首行 `品牌模板: 共 {n} 个` + 逐模板行（`  {name} | 配色: {color_scheme 呈现名} | 字体: {font_preset 呈现名} | Logo: {已配置|未设置} | 更新: {YYYY-MM-DD HH:MM}`——呈现名=预设常量中文呈现键）；零模板空态 `品牌模板: 共 0 个` 后无行 + 恒在提示行（指向 brand-template-save——与 6-10 :1806 提示行形态对齐）；行序 **updated_at 降序**+name 字典序 tie-break（最新修订优先——UPSERT 每存必前进 updated_at 而 created_at 不变[AC-1]，created_at 排序下修订旧模板永沉底与语义互斥；与 6-10 项目行序 latest_activity_at 活动时间语义同族——R1 修复裁定）
**And** **复用入口**（6-5b OD-11 同入口钦定兑现）：`report-generate --plan-id <uuid> --format pdf --brand-template <name>`——`--brand-template` 可选参数默认 None（既有调用零破坏）；**参数组合守卫**：`--brand-template` 携带且 `--format markdown` → 494（品牌应用仅 PDF 面支持——Markdown 纯文本无视觉承载，组合非法显式拒绝非静默忽略；post-parse 检测归 CLI 层[checkpoint-recover 成组约束先例 :2026-2032——CLI 层唯一落位]）；**模板不存在**：`--brand-template ghost` 库中无此名 → 494（message 含模板名与「不存在」——404 等价语义，CLI 面 exit 1）
**And** 「支持后续项目复用」语义正面承载：模板不锚定 plan（全局单租户资源）——同一模板可跨任意 plan 反复引用导出（S13 两 plan 同模板导出承载）

**验证标准/Validation Criteria:**
- [ ] 列表输出断言（行数+逐行字段呈现名+行序降序——**载体钉位[R2 裁定]**：14 场景无「列表有行」专场景[S4 仅空态]——本断言由 Task 5 CLI 单测执行格[预置多行+行序断言]+Task 2 仓储 list 双序断言组合承载）
- [ ] 空态输出（`共 0 个` 后无行+提示行恒在）
- [ ] 复用参数落地（--brand-template 传递链：CLI→use case→服务→渲染 spec——分发表/参数锚断言）
- [ ] 组合守卫（--brand-template+--format markdown → stderr `[EXCEPTION_494]` exit 1）
- [ ] 模板不存在守卫（ghost 名 → `[EXCEPTION_494]` exit 1 + message 含模板名）

### AC-4: 白标 PDF 渲染品牌应用（PdfRendererPort v1.1.0 + BrandRenderSpec + reportlab 三件扩展）

**Given** 品牌模板已保存（含/不含 Logo 两形态）且某 plan 已有 BLM 产物（6-5b 导出前置同构）
**When** 执行 `report-generate --plan-id <uuid> --format pdf --brand-template <name>`
**Then** 导出主链复用 6-5b 六段编排（聚合→引文→渲染→L4 WORM→L2 行→事件）+ 品牌增量三段：①`PdfReportGenerationService.generate_pdf_report` v1.1.0 增可选参 `brand_template_name: str | None = None`——非 None 时经 `BrandTemplateServicePort.get_render_spec(name)` 组装 `BrandRenderSpec` 传入渲染器；②渲染器品牌应用三件：**字体**（spec.font_name 参数化 `_style()` base fontName——CID 名直用/TTF 名经 `_ensure_font` 幂等注册[TTFont 通道首启]）、**配色**（spec 五色键驱动：标题色 title_color[新能力——H1/H2 标题文字色，现 `_style` base 无 textColor 默认黑]/表头底 header_bg_color[:374]/网格线 grid_color[:375]/callout 底 callout_bg_color[:313]/callout 文字 callout_text_color[:305]——**四处硬编码色是 `_build_block`[:305/:313] 与 `_build_table`[:374/:375] 内联字面量，非 `_style` overrides 通道**：参数化需给两私有方法加参或经构造态传递）、**Logo**（spec.logo bytes → `ImageReader(BytesIO(logo))` → `platypus.Image` 等比缩放宽 ≤40mm 置于首页标题上方——位图首启；None → 零 logo 流）；③L2 行 metadata 增品牌键：`brand_template_id`/`brand_applied: True`（JSONB 顶层自由扩展零 migration——既有顶层键[聚合基底+citation 族键，基数不定]之上追加两键，无品牌导出零品牌键）
**And** `BrandRenderSpec` **7 键** frozen VO（`src/application/ports/pdf_report.py` 渲染契约面——Task 0.3 冻结）：font_name: str / title_color: str / header_bg_color: str / grid_color: str / callout_bg_color: str / callout_text_color: str / logo: bytes | None（渲染器直消费形态——logo 读取归应用服务 L4 通道，渲染器零 IO 纯函数纪律保持[6-5b OD-3 同源双渲染纪律延续]）
**And** **默认态零破坏回归**（契约冻结面）：`render(document)` 与 `render(document, brand=None)` 产物**等价**（同 document 双渲染 byte 级对照断言——**测试前置 `reportlab.rl_config.invariant = 1`**[fixture setup 设置/teardown 还原]：reportlab 默认态 trailer `/ID` 每次渲染含 time.time() 种子随机+`/CreationDate` 秒粒度漂移，byte 级对照结构性不可比——invariant 是 reproducible builds[SOURCE_DATE_EPOCH 同族]的标准前置，**生产路径日期语义零触碰**；+ 既有 6-5b 渲染测试全绿——**唯一例外 carve out**：test_reportlab_pdf_renderer.py:282 `test_cjk_font_registered_module_level` 的 `monkeypatch.setattr(module, "_FONT_REGISTERED", False)` 布尔字面量随哨兵字典化同步改空 dict 一行[哨兵类型变更的机械适配，零修改口径=除该行外零修改——R2 裁定]）；`generate_pdf_report(plan_id)` 单参调用零破坏（6-5b 既有调用方零改动——keyword-only 可选参默认 None 向后兼容，`--format` 扩展先例 e431427c 同构）

**验证标准/Validation Criteria:**
- [ ] 品牌渲染三件落地断言（字体名/styles 色值/Image Flowable 在场——渲染器单测 spy 断言或产物解析）
- [ ] 默认态等价（invariant=1 测试前置：brand=None 双渲染对照 == 逐字节相等）
- [ ] metadata 品牌键（brand_template_id/brand_applied直推；无品牌导出零品牌键对照）
- [ ] L4 WORM PDF 对象键不变（reports/{plan_id}/{report_id}.pdf——白标不改变归档通道）

### AC-5: 品牌元素 100% 准确应用（结构化断言体系——非计时口径）

**Given** 品牌模板三要素齐备（Logo+配色+字体）且导出完成
**When** 检查白标 PDF 产物内部结构
**Then** **100% 准确 = 结构化断言四件套**（「品牌应用准确率 100%」epics L2545 的 CLI-only 口径重读——6-5b「结构化断言」先例直系）：
- **字体在场**：PDF 字体资源含品牌字体名（**仅 TTF 形态承载断言**——noto-sans-sc 预设时页面 Resources/Font 含注册名 NotoSansSC，与渲染器默认 STSong-Light 互斥可判别；**stsong 预设与默认渲染器同字体——字体维度不可判别[断言恒真]**，该形态由渲染器单测传递链断言承载——S6 场景钦定 font_preset=noto-sans-sc）
- **Logo 在场**：首页含图像 XObject（pypdf 页面对象 Resources/XObject 至少一 Image——且仅品牌导出有，对照导出零图像）
- **品牌色在场**：PDF 内容流含品牌 title_color/header_bg_color 的 RGB 值序列（pypdf 内容流字节检索 hex→RGB 归一——判别锚：三套五色与渲染器默认四色[#444444/#F2F2F2/#E8E8E8/#BBBBBB]逐对互斥已数学验证[最小差 1/255 可判别]；**内容流色值是 reportlab `fp_str` 格式**[round 6 位+去前导/尾随零，如 #ECEFF1→`.92549 .937255 .945098 rg`]——期望串须用 `reportlab.lib.rl_accel.fp_str` 生成或 token 解析后容差比较，直拼 `f'{r/255:.6f}'` 恒不中）
- **配置传递链完整**：预设常量 hex → BrandRenderSpec → 渲染 styles（渲染器单测断言 `_style` 产出 textColor==spec 值——单元级直判）

**And** 准确性语义边界注记：「100% 准确」= 渲染器忠实应用品牌参数（纯函数确定性——同 spec 恒同产物）；**不含**像素级视觉比对（pypdfium2 光栅化像素 diff 归后续 Web 预览 Story——YAGNI 注记）；品牌应用失败（logo bytes 损坏等渲染异常）→ 既有 `PdfRenderingError` 492 包装（6-5b 渲染异常通道复用——不静默降级非品牌导出，失败显式红）

**验证标准/Validation Criteria:**
- [ ] 结构化四件套各至少一格断言落地（单测传递链+验收端到端 PDF 解析各承载）
- [ ] 对照腿（无品牌导出零图像 XObject+默认字体/默认色——判别非恒真）
- [ ] 渲染失败路径（logo bytes 非法图 → 492 包装——spec.logo 构造损坏 bytes 单测格）

### AC-6: 6-10 品牌段联动（consultant_view v1.1.0 读配置面 + 回归面处置）

**Given** 6-10 已交付 BrandSection 5 键恒默认态（configured 对接锚 docstring 注记在档）
**When** 6-11 实施后构建顾问视图
**Then** `ConsultantViewService` v1.0.0→v1.1.0（第三依赖注入 brand_template_repository——lambda 增 resolve 行）：`_build_brand_section` 改读配置——`list_templates()` 最新行（updated_at 降序首行——最新修订语义，与 AC-3 行序同键）派生：**有模板** → `configured=True` + logo_status（logo_object_key 在场→`已配置`/缺席→`未设置`）+ color_scheme_status/font_status（预设呈现名）；**零模板** → 五键全默认值（**与 6-10 恒值逐字相等**——6-10 验收 S3 断言在零模板前提下继续成立）；**查询异常** → `degraded=True`+默认值+段级容错（不抛——零 IO 恒稳承诺打破的结构性勘误：v1.1.0 docstring 注记更新[「恒 False 是结构性承诺」→「零模板/降级态下 False——v1.1.0 读配置面激活降级语义」]）
**And** **6-10 回归面处置清单**（Task 6 义务——预期演进信号兑现非删除）：①`consultant_view.py` 三处 docstring 触发器注记勘误（:27-28/:31-34/:121-129——「6-11 实施后」条件已兑现，改注 6-11 v1.1.0 语义）；②CLI 提示行 :1806 `提示: 品牌模板配置归 Story 6-11（白标报告基础）` → `提示: 执行 brand-template-save 配置品牌模板`（:1820 导出提示行**不动**——最小面）；③6-10 单测 `_build_brand` 行为断言改 Mock 三形态（零模板默认/有模板派生/异常降级）；④6-10 验收 S3 前置增「品牌模板表零行清点——有行 pytest.skip（共享库背景残留防御[预期零残留：同组串行+自包含清理]）」+断言本体零改动；⑤CLI 单测/验收提示行断言联动更新；⑥组合根 consultant_view lambda 两依赖→三依赖+契约测试 getsource 注入链锚更新
**And** **隔离纪律**（6-10 OD-13 前向约束扩展）：品牌模板写入方（本 Story 全部验收/集成测试）挂 `xdist_group("blm-planning-perf")` 同组+自包含 teardown 定向 DELETE（rowcount 断言防静默 0 行假绿——6-10 :417-429 先例直系）

**验证标准/Validation Criteria:**
- [ ] 联动三形态（有模板 configured True+呈现名直推/零模板五键与 6-10 默认值逐字相等/异常 degraded+默认值不抛）
- [ ] 6-10 验收/单测/CLI 三文件回归更新后全绿（Task 6 逐项清单勾选）
- [ ] v1.1.0 端口版本断言（契约测试 spec.version 更新）
- [ ] 6-10 S3 skip 门生效（预置残留行场景 skip 非假红——构造格）

### AC-7: 领域异常契约（494/495 两新码 + 复用面）

**Given** 本 Story 新增校验与存储失败语义（report 域预留码段 494-499 六码全空亲验——_code_ranges.py:199-212）
**When** 异常路径触发
**Then** 两枚新异常（`src/domain/exceptions/report_exceptions.py` 扩展——BusinessException 基类族与 490-493 同构）：
- `BrandTemplateValidationError`（**EXCEPTION_494**，400 语义——校验伞形）：非法 color_scheme key/非法 font_preset key/Logo 非合法可解码 PNG/JPEG 图像文件（magic bytes 非法或图像体无法解析——R1-F6 拓宽）/超限（字节 2MB/像素单边 4000px——两正交守卫）/路径不存在（含不可读伞形）/模板不存在/`--brand-template`+markdown 组合非法（message+context.field 区分**七形态=494 全触发面**；name 空值/超长是 242 实体守卫形态非 494——CLI stderr `[EXCEPTION_242]`；**CLI choices 面的非法预设 key 是 argparse exit 2 硬拦截**——494 值域校验经编程面 use case 直调触达，验收 S2 钦定编程面形态）
- `BrandTemplateStorageError`（**EXCEPTION_495**，500 语义）：brand_templates PG 读写失败/L4 logo 存取失败（与 491 ReportStorageError 同族分立——彼为报告产物持久化、此为品牌配置持久化，触发面与消费方不同）
**And** 复用面零改动：242（实体不变量守卫——BrandTemplate `__post_init__`）/492（渲染失败——品牌渲染异常包装）零新增改动；**完整注册义务清单**（CLAUDE.md 4 项强制 Checklist+3 项扩展）：定义文件+_code_ranges.py 子域映射[4 项强制]+`__init__.py` 暴露+子域码段校验+`_CLASS_TO_SUBDOMAIN` 注册+`EXCEPTION_HTTP_MAP` 映射+sisys-uni-exception-design.md §3.3.2 编码分配表更新[扩展 3 项]——**HTTP_MAP 机理注记：495→500 必须显式注册**（BusinessException 基类兜底是 400，先例 491 :320；494→400 与基类一致但族惯例全显式注册[report_exceptions 显式注册先例]）+8 项测试（2 类×4 维度[构造/context/to_dict/HTTP 映射]自定结构+既有 Registration 7 测复跑零碰撞——`tests/unit/domain/exceptions/` 全绿+`test_exception_handlers.py`）

**验证标准/Validation Criteria:**
- [ ] 两新码构造/context/to_dict/HTTP 映射测试全绿（8 项族）
- [ ] 编码唯一性+子域范围测试复跑零碰撞（490-499 段内）
- [ ] CLI stderr 呈现（`[EXCEPTION_494]`/`[EXCEPTION_495]` 格式——**通道分立注记[R2]**：494 组合守卫走 post-parse 守卫位独立 except 块[bootstrap 前——_parse_correction_group 先例形态，两通道 stderr 格式逐字同款]；495 走五步定式 bootstrap-resolve-asyncio 通道）
- [ ] 异常路径 Gherkin 场景纳入（S2 值域/S3 格式/S8 不存在/S9 组合四形态承载）

### AC-8: 性能三段口径（保存 P95<200ms + 导出<1min 继承 + 准确率结构化）

**Given** 真实服务在位（PG+MinIO+Redis——bootstrap 全链）
**When** 性能采样
**Then** 三段口径（六连口径差声明纪律延续）：
- **品牌配置保存延迟 P95<200ms**（epics L2543）= `save_brand_template` 服务面窗口（PG upsert 一次 flush+可选 L4 store——report_repository `_persist` 单往返先例 :126-139 佐证充裕；**20 轮 `sorted[ceil(0.95*n)-1]` 数学口径**六连同款——毫秒级上限参照 6-3/6-6 快照族而非 800ms 视图族）
- **白标报告导出时间<1 分钟**（epics L2544）= 6-5b 60s P95 既有口径承载（`_PERF_P95_LIMIT_SECONDS=60.0`，60s<1min 钦定关系——test_acceptance_pdf_report.py:102-103 先例）+ 品牌渲染增量在同入口复跑（渲染纯 CPU 亚秒[6-5b docstring :89-91]+logo Image 解码微秒级——增量不构成风险面注记；采样形态=单一数据源 plan × 20 轮+L4 对象读回）
- **品牌应用准确率 100%**（epics L2545）= AC-5 结构化断言四件套承载（非计时口径——三段口径差声明 docstring）

**验证标准/Validation Criteria:**
- [ ] 保存 P95 采样断言（20 轮含 L4 logo 路径全参形态——最重路径采样）
- [ ] 白标导出 20 轮 P95<60s（含品牌三件渲染——S12 承载）
- [ ] 口径差声明三段落 docstring（验收/集成文件头——六连纪律第七连）

---

## 🏗️ SDD+TDD 融合开发

> ⚠️ **关键约束：** 每个 Task 必须独立完成完整的 TDD 循环（红→绿→重构），禁止将测试编写与代码实现分离到不同 Task。

### SDD 规范定义（Task 0 — 必选前置）

> **执行顺序：** Task 0 必须在所有实现 Task 之前完成。SDD 规范是后续 TDD 测试的输入来源。

#### 领域事件 Schema (Domain Events)

- [ ] **零新增领域事件（OD-2 第十连声明）**：品牌模板保存/列表/白标导出零新事件——①配置面零订阅方（DictionaryUpdated[3-3] 有 API 消费面先例，品牌模板 CLI-only 零消费方）；②白标导出复用 `ReportGenerated`（report_type="pdf" 自由 str :57-72——6-5b 流经零类改动先例直系）；③event_channels.yaml/ChannelRouter.DEFAULT_MAPPINGS 零 diff；④`_FROZEN_EVENT_COUNT=56` 不变（三处契约测试复跑守护：test_event_channel_mapping_report.py:25/pdf_report.py:24/checkpoint_recovery.py:75）
- [ ] 事件命名规范零新增面（无 `[Aggregate][EventName]` 新事件）

#### 数据模型 (Data Models)

- [ ] 模型定义位于 `src/domain/entities/brand_template.py`（领域实体——StrategicReport 同构先例；非应用层 VO：本 Story 是持久化写域[配置保存]，与 6-9/6-10 纯读视图族分立）
- [ ] `BrandTemplate` 7 字段（Task 0.1 冻结表）：template_id: UUID / name: str / color_scheme: str / font_preset: str / logo_object_key: str | None / created_at: datetime | None / updated_at: datetime | None
- [ ] 纯标准库实现（dataclass+UUID+datetime——零外部依赖，import-linter 校验）
- [ ] PG 表 `brand_templates`（018 migration，down_revision="017"）：template_id UUID PK / name String(100) UNIQUE NOT NULL / color_scheme String(30) NOT NULL / font_preset String(30) NOT NULL / logo_object_key String(500) nullable / created_at+updated_at DateTime(timezone) server_default now()
- [ ] ORM model `src/infrastructure/storage/postgresql/models/brand_template.py`（`BrandTemplateModel(Base)`——models/ 目录 ReportModel :20-36 同构）

#### 统一端口定义注册与管理 (Port Contract)

- [ ] R1 基础端口：`src/domain/ports/brand_template_repository.py`——`BrandTemplateRepositoryProtocol`（`save(template) -> BrandTemplate` / `get_by_name(name) -> BrandTemplate | None` / `list_templates() -> list[BrandTemplate]`[updated_at 降序+name 字典序 tie-break——UPSERT 修订语义排序]；async Protocol——ReportRepositoryProtocol :23/:38 两方法同构扩展第三方法）
- [ ] R2 应用端口：`src/application/ports/brand_template.py`——`BrandTemplateServicePort`（`save_brand_template` / `list_brand_templates` / `get_render_spec(name) -> BrandRenderSpec`）+ 预设冻结常量（COLOR_SCHEME_PRESETS/FONT_PRESETS/呈现名映射）；R2 组合注入 R1：服务注入 brand_template_repository+l4_object（store/retrieve logo 通道）
- [ ] 端口演进三处 v1.0.0→v1.1.0（`compatibility=("v1.0.0",)` 元组——hybrid_search_service :1844-1861 先例）：`PdfRendererPort.render` 增 keyword-only `brand: BrandRenderSpec | None = None`；`PdfReportGenerationServicePort.generate_pdf_report` 增 `brand_template_name: str | None = None`；`ConsultantViewPort.build_consultant_view` 签名零变（服务实现演进——仅 spec.version 升 v1.1.0+第三依赖；**既有契约测试 test_port_contract_consultant_view.py:30-33 版本断言循环覆盖 service+use_case 两注册名——升级时须拆分断言**[service 期望 v1.1.0/use_case 维持 v1.0.0]，机械改断言值会致 use_case 假红）
- [ ] 端口注册以 registry.py 的 PortSpec 机制在 `src/composition_root.py` register_port 登记（4 新注册名：brand_template_repository[SCOPED v1.0.0——session_factory 注入 report_repository :3550-3559 同款]/brand_template_service[SINGLETON v1.0.0]/save_brand_template_use_case[SINGLETON]/list_brand_templates_use_case[SINGLETON]；registry.py 本身零修改——机制定义非逐端口登记表）+ 3 处既有注册版本升级（pdf_renderer/pdf_report_generation_service/consultant_view_service）
- [ ] 端口实现仅可在 `src/composition_root.py` 统一注册；端口契约门禁 contract_gate 兼容性检查通过（v1.0.0 兼容元组）
- [ ] 端口契约测试通过（`tests/contracts/test_port_contract_white_label_report.py`——五断言族+签名；三处版本升级断言）

#### 端口契约清单执行约束（强制）

- [ ] 本模板中的端口清单是唯一事实源（Single Source of Truth）
- [ ] 禁止新增未登记端口，禁止语义重复端口，禁止未同步更新 registry / resolver / contract test
- [ ] 每个端口必须同时具备 contract、registry、resolver、contract test、owner、version
- [ ] 未通过 Contract Gate 的端口变更不得进入实现 Task

#### 领域异常契约 (Domain Exception Contract)

> **原则**：异常是领域契约的一部分。本 Story 新增异常在 Task 0 完成设计（AC-7 承载），禁止在实现 Task 中临时定义。

- [ ] 归属模块与基类：report 子域（`src/domain/exceptions/report_exceptions.py`）——两新类均继承 `BusinessException`（490-493 同族：「报告失败是调用方可处理结果」语义延续）
- [ ] 唯一编码分配：`EXCEPTION_494`（BrandTemplateValidationError，400 语义）/`EXCEPTION_495`（BrandTemplateStorageError，500 语义）——report 段预留 494-499 内（六码全空亲验零碰撞）；`grep -r "EXCEPTION_49[45]" src/domain/exceptions/` 验证
- [ ] 构造器参数设计：携带 `context={"field": ..., "template_name": ..., "reason": ...}` 领域上下文
- [ ] 消息安全性审查：面向调用方可理解（含合法预设键清单/大小上限值），不泄露 SQL/堆栈
- [ ] 编码注册：`_code_ranges.py` report 行注释更新+`_CLASS_TO_SUBDOMAIN` 两类注册+sisys-uni-exception-design.md §3.3.2 编码分配表
- [ ] 导出完整性：report_exceptions `__all__` + 包 `__init__.py` 导入 + `EXCEPTION_HTTP_MAP`（494→400/495→500）
- [ ] 测试覆盖：`poetry run pytest tests/unit/domain/exceptions/ -v`（8 项族）+ `tests/unit/interfaces/api/test_exception_handlers.py`
- [ ] BDD 验收场景异常路径（S3 格式/S8 不存在+S9 组合——CLI stderr `[EXCEPTION_494]` exit 1 呈现；**S2 值域走编程面 use case 直调 pytest.raises 断 494**[CLI choices 是 exit 2 硬拦截——AC-7 口径]）

#### API 契约 (API Contract)

- [ ] **零 API 面**（CLI-only 第十连——openapi.yaml 零 diff；REST 白标归 Epic 20 Story 20.4[FR-SP-16 P2]；`POST /reports/whitelabel` interface-design.md:1488 规划位不动）

#### 六边形架构约束（必须遵守）

> **执行顺序：** 所有实现 Task 仅可依赖下述层间方向。领域层不得引入任何第三方依赖。

**四层架构定义**
| 层次 | 目录 | 职责 |
|------|------|------|
| domain | `src/domain/` | 核心业务逻辑，零外部依赖 |
| application | `src/application/` | 用例编排 |
| interfaces | `src/interfaces/` | 适配器 |
| infrastructure | `src/infrastructure/` | 技术实现 |

**领域层零依赖原则**
- 领域层（`src/domain/`）仅使用 Python 标准库
- 禁止导入：包括且不限于 langgraph, prefect, fastapi, pydantic, sqlalchemy, typer, redis, qdrant, minio, neo4j, aio_pika, litellm, instructor, requests, httpx, docker, psycopg2, reportlab

**依赖方向矩阵**
| 起点 \ 终点         | domain | application | interfaces | infrastructure |
|--------------------|--------|-------------|------------|----------------|
| **domain**         | —      | ✗ 禁止      | ✗ 禁止     | ✗ 禁止         |
| **application**    | ✓ 允许 | —           | ✗ 禁止     | ✗ 禁止         |
| **interfaces**     | ✓ 允许 | ✓ 允许      | —          | ✗ 禁止         |
| **infrastructure** | ✓ 允许 | ✓ 允许      | ✗ 禁止     | —              |

> **本 Story 特有落位**：预设常量与 BrandRenderSpec 在 application ports（渲染器[infrastructure] import application ports 常量合法——infra→application 允许；reportlab 渲染器 import `src.application.ports.pdf_report` 先例在位）；domain 实体零 application import（预设 key 值域校验落应用服务的依据）；entrypoints 组装层 import infrastructure 为设计使然（D1 方案 A——.importlinter 注记原文）。

#### 验收标准 Gherkin (Acceptance Tests)

- [ ] 功能测试文件：`tests/acceptance/test_acceptance_white_label_report.feature`（R6 模板——epics 钦定名采纳，14 场景 S1~S14）
- [ ] 步骤实现文件：`tests/acceptance/test_acceptance_white_label_report.py`
- [ ] 业务方评审通过
- [ ] 所有场景覆盖（Happy Path + Edge Cases——异常路径 S2/S3/S8/S9 承载）

**BDD 步骤实现约束：**
- 步骤函数使用 `event_loop.run_until_complete()` 运行 async 测试（三件套 `_run_async` 形态）
- 同一中文文本可能需要同时支持 given/when 装饰器
- 不要使用 `@pytest.mark.asyncio`（会导致 context 数据丢失）
- **Edge Cases 必须包含异常路径**——CLI 面等价承载：模板不存在（S8=404 等价）/参数组合非法（S9）/格式与大小守卫（S3）；**S2 值域守卫走编程面 use case 直调**（`resolve("save_brand_template_use_case").execute` + pytest.raises 断 code 494——CLI choices 是 argparse exit 2 硬拦截，494 不可经 CLI 直调触达）；**S4 空态前置品牌模板表零行清点**（有行 pytest.skip——与 6-10 S3 skip 门同款背景行防御）；**S6 品牌准确场景钦定 font_preset=noto-sans-sc**（TTF 形态可判别——stsong 与默认渲染器同字体恒真）；**S7 默认态回归断言形态钉死**（metadata 零品牌键对照+L4 对象键通道不变+6-5b 既有测试零修改[唯一例外见 AC-4 carve out]——不写两次导出 byte 相等，导出链 /ID 非确定）；权限面：CLI 无认证（身份走参数——6-10 注记第三连，RBAC 归 7-2 REST 立项）；资源冲突（409 等价）：同名保存=UPSERT 修订语义**钦定非错误**（AC-1 声明——CLI 面无冲突错误语义）
- **pytestmark 挂 `xdist_group("blm-planning-perf")`**（品牌模板写入方与 6-7/6-8/6-9/6-10 全部 strategic_* 提交型写入方同 worker 串行——6-10 OD-13 前向约束扩展；漏挂则与 6-10 consultant-view 品牌段/6-7 归档面并行产生间歇假红）
- **py 模块级零本 Story 新词族 import 硬纪律**（src 符号全部延迟到步骤函数内 import——模块级 import 收集期 ImportError 全文件 ERROR[6-9 :55-68 教训第四连]）
- **CLI 直调三清**（brand-template-save/list 与 report-generate 直调前 `clear_singleton()`+`clear_scoped()`+`_clear_session_ctx()` 三清+禁二次 bootstrap——checkpoint-recover 写命令直调先例+6-10 直系第四连）

**Task 0 完成标志：**
- [ ] 上述规范项全部定义完毕（冻结面清单：双 VO 键契约[7 字段+7 键含构造契约]/预设常量[3 套×5 色 hex+2 字体+呈现名]/端口契约与 018 DDL/CLI 参数——四冻结面）
- [ ] Gherkin 验收测试已编写，运行确认失败（🔴 红阶段验证——逐场景红形态以 Task 0.6 符号表为准：CLI 直调场景[S1/S3/S4/S8/S9]argparse exit 2→AssertionError/预置场景[S2/S5~S7/S10~S13]ImportError/S14 文件不存在 AssertionError）
- [ ] 规范文档通过人工评审或自动化校验
- [ ] **链路接线断言清单**已定义：新增 4 端口组合根 register_port 装配验证（resolve 可达）/零新事件零发布验证（三处 56 冻结计数+架构验证器 B 零 publish）/report-generate 扩展参数 CLI 分发接线确认/consultant_view 第三依赖 lambda 注入确认；「已实现未接线」组件在 deferred-work.md 登记

---

### TDD 循环约束（适用于每个 Task）

> **每个 Task 必须依次执行以下步骤，禁止跳过或颠倒顺序：**

| 阶段 | 动作 | 完成标志 |
|------|------|----------|
| **🔴 红** | 根据 SDD 规范编写失败测试 | `pytest` 运行失败，且失败原因符合预期 |
| **🟢 绿** | 编写最小实现让测试通过 | `pytest` 全部通过 |
| **🟡 变异** | 对新行为契约的断言做突变注入-还原实证（Epic 4 回顾行动项 7.1-2） | 改坏生产代码 → 测试红 → 还原 → 绿（证明断言活着） |
| **🔄 重构** | 优化代码（保持测试通过） | `ruff check` + `mypy` + `pytest` 全部通过 |

**禁止行为：**
- ❌ 先写代码后写测试（违反 TDD 测试先行原则）
- ❌ 将测试编写集中到最后一个 Task（违反 TDD 小步快跑原则）
- ❌ 跳过红阶段验证（未确认测试失败就直接写实现）
- ❌ 跳过变异实证（新断言未经突变验证即视为不可信——Epic 4 教训：8/13 Story 存在恒真断言）

---

### 测试分类与归属

> **明确区分 TDD 单元测试 与 SDD 架构验证测试，避免混淆。**

| 测试类型 | 归属 | 验证内容 | 测试文件 | 对应 Task |
|---------|------|----------|----------|-----------|
| **TDD 单元测试** | BrandTemplate 实体 | 7 字段/242 守卫负例全枚举/frozen | `tests/unit/domain/entities/test_brand_template.py` | Task 1 |
| **TDD 领域异常测试** | 494/495 两新码 | 构造/context/`to_dict()`/HTTP 映射/编码唯一性 8 项族 | `tests/unit/domain/exceptions/`（扩展） | Task 1 |
| **TDD 单元测试** | 仓储（真实 PG） | upsert 两形态/list 排序/映射隔离（6-5a test_report_repository.py 真实 session 先例） | `tests/unit/infrastructure/storage/test_brand_template_repository.py` | Task 2 |
| **TDD 单元测试** | BrandRenderSpec+渲染器品牌应用 | 7 键契约/字体注册幂等/色参数化/Image 在场/默认态等价[invariant 前提 byte 对照] | `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer_brand.py` | Task 3 |
| **TDD 单元测试** | 预设常量+BrandTemplateService | 预设 exact set+hex 值级/save 编排+校验矩阵七形态/get_render_spec 组装/L4 通道 Mock | `tests/unit/application/test_brand_template_presets.py` + `test_brand_template_service.py` | Task 4 |
| **TDD 单元测试** | Pdf 服务品牌段 | v1.1.0 品牌参编排+metadata 品牌两键+零品牌参回归 | `tests/unit/application/test_pdf_report_generation_service.py`（扩展） | Task 4 |
| **TDD 单元测试** | 双用例+CLI | 透传断言/五步定式/输出契约/组合守卫/getsource 块边界 | `tests/unit/application/use_cases/test_save_brand_template.py`+`test_list_brand_templates.py`+`tests/unit/interfaces/cli/test_agent_cli.py`（扩展） | Task 5 |
| **TDD 单元测试** | consultant_view v1.1.0 | 品牌段三形态+6-10 断言更新（6-10 文件更新） | `tests/unit/application/test_consultant_view_service.py`（更新） | Task 6 |
| **TDD 契约测试** | 端口契约 | 五断言族+三处版本升级+56 冻结计数 | `tests/contracts/test_port_contract_white_label_report.py` | Task 7 |
| **TDD 验收测试** | Gherkin 场景 | 业务价值验收（14 场景） | `test_acceptance_white_label_report.feature` | Task 0 |
| **TDD 验收测试** | BDD 步骤实现 | 步骤函数实现（三件套+三清+CLI 直调） | `test_acceptance_white_label_report.py` | Task 0 |
| **TDD 验收测试** | 收尾验收场景 | src 与测试目录完成清单最终确认 | 同上两文件 | Task 9 |
| **集成测试** | 真实链端到端 | PG+MinIO+渲染品牌应用五场景 | `tests/integration/test_integration_white_label_report.py` | Task 8 |
| **SDD 架构验证** | 六边形架构约束 | 依赖方向/零依赖/词族落位（**白名单形态**——6-8 先例，非 6-9/6-10 零命中形态：本 Story 有合法 infra 增量） | `tests/unit/architecture/test_white_label_report.py` | Task 9 |

---

### 测试要求与质量门禁

#### 覆盖率要求

根据 epics_v1.0.md CI/CD 质量门禁和 prd.md NFR 测试覆盖计划：

- [ ] **整体覆盖率 ≥80%**（`pytest --cov=src --cov-fail-under=80`）- **P0 阻断门禁**（基线 93%）
- [ ] **分层覆盖率门禁** - **P1 阻断门禁**
  - 领域层：≥90%（维持——新实体 BrandTemplate 全覆盖）
  - 应用层：≥85%（主改动层——epics L2548 对齐；新增文件 ≥95%）
  - 基础设施层：≥75%（新仓储+渲染器扩展——epics L2549 集成口径对齐）
- [ ] **关键路径覆盖率 100%**（品牌渲染三件/校验七形态/upsert 两形态全分支覆盖）

#### 代码质量门禁

- [ ] **Ruff 检查通过**（`poetry run ruff check src/ tests/`）
- [ ] **MyPy 类型检查通过**（`poetry run mypy src/`——基线 765 零错误）
- [ ] **无 P0/P1 级别问题**（代码审查）
- [ ] **预提交 Hooks 通过**（`pre-commit run --all-files`）

#### 测试隔离约束

> ⚠️ **核心原则：测试必须自包含（Self-contained），不污染共享状态，不依赖执行顺序。**

**约束规则：**

| 约束类型 | 规则 | 违反后果 |
|---------|------|---------|
| **事务隔离** | 集成 A 面 pg_session begin+rollback；B/C 面（CLI/性能）commit 式+定向 DELETE | 数据泄漏随机失败 |
| **品牌模板行清理** | teardown 定向 `DELETE FROM brand_templates WHERE template_id = ANY(:ids)` + **rowcount 断言防静默 0 行假绿**（6-10 :417-429 先例直系） | 残留行致 6-10 S3 假红 |
| **L4 对象清理** | logo 对象定向 delete（brand-assets **resolve 通道共享物理桶**——组合根未传 tenant_id 恒 `{prefix}-brand-assets-default`[6-5b 共享桶先例]，对象键锚 template_id 定位隔离）+**测试前置自愈建桶**（bucket_exists 探测→make_bucket **勿带 object_lock**——store 对缺桶抛 NoSuchBucket 且 src 零生产建桶）+PDF 对象键登记清理[WORM PDF 须裸 client remove_objects(bypass_governance_mode=True) 删——端口 delete 抛 ComplianceLockError；6-5b `_cleanup_pdf_objects` 直系]+strategic_reports/event_outbox 导出副产行清理（6-5b `_cleanup_report_rows`/`_cleanup_outbox_rows` 直系） | 对象泄漏/首轮 store NoSuchBucket/WORM 删失败静默 |
| **xdist 隔离** | 全部品牌模板/白标导出写入测试挂 `xdist_group("blm-planning-perf")`（与 strategic_* 提交型写入方同 worker 串行） | 并行假红 |
| **资源唯一性** | 模板名用 TestTenant UUID 前缀（`test-{uuid8}-品牌名` 形态——name UNIQUE 约束下防撞+teardown 定位） | ID 冲突 |
| **三清纪律** | CLI 直调前 clear_singleton+clear_scoped+_clear_session_ctx 三清；禁二次 bootstrap | 注册表态污染 |
| **异步上下文** | asyncio.Lock 类变量；BDD 步骤 `event_loop.run_until_complete()` | 锁失效/context 丢失 |
| **字体资产确定性** | TTF 注册幂等（模块级标志扩展 `_ensure_font`——重复注册同名不炸） | 重复注册异常 |
| **验证要求** | 并行测试 `pytest tests/unit tests/integration tests/contracts tests/acceptance -n auto` 通过（**显式四目录，裸 tests/ 挂起**）；连续 5 次无随机失败 | — |

**禁止行为：**
- ❌ 集成测试手动 `delete`/`truncate` 全表（应用 rollback+定向 DELETE）
- ❌ autouse fixture 删除全局匹配资源
- ❌ BDD 步骤函数使用 `@pytest.mark.asyncio`
- ❌ 验收面 mock（真实服务优先——BrandTemplateService/渲染器全真实；段级异常容错归单测 AsyncMock——验收面无故障注入通道，6-10 分立裁定第四连）
- ❌ 抑制注释（noqa/type: ignore/pylint disable）

---

## 📊 AC → Task → Subtask 追溯矩阵

> **编号语义注记**（6-9/6-10 同款）：Subtask 列引用的循环 A/B/C 为 **TDD 循环语义位**；Task 内 Subtask 编号（1.1 红/1.2 绿/1.3 重构/1.4 变异）是 TDD 阶段序，两套编号体系分立防混引；验收场景统一归 Task 0 编写/Task 9 收尾承载。

| AC | 验收标准描述 | 关联 Task | 负责 Subtask | 测试文件 |
|----|-------------|-----------|-------------|----------|
| AC-1 | 实体 7 字段+242 守卫 | Task 1 | 循环 A 实体 | `test_brand_template.py` |
| AC-1 | PG 表+UPSERT 两形态 | Task 2 | 循环 A migration+Model/循环 B 仓储 | `test_brand_template_repository.py` |
| AC-1 | save 编排+预设校验 | Task 4 | 循环 A save 编排+校验矩阵 | `test_brand_template_service.py` |
| AC-1 | 保存主链验收 | Task 0 | 0.4 场景 S1 | `test_acceptance_white_label_report.py` |
| AC-2 | Logo L4 通道+格式守卫 | Task 4 | 循环 A 校验矩阵/循环 B L4 通道 | `test_brand_template_service.py` |
| AC-2 | Logo 验收（真实 MinIO） | Task 0 | 0.4 场景 S1/S3 | `test_acceptance_white_label_report.py` |
| AC-3 | 列表用例+CLI 命令 | Task 5 | 循环 B 用例/循环 B CLI | `test_agent_cli.py` |
| AC-3 | 复用参数+组合守卫 | Task 5 | 循环 C report-generate 扩展 | `test_agent_cli.py` |
| AC-3 | 复用跨 plan 验收 | Task 0 | 0.4 场景 S13 | `test_acceptance_white_label_report.py` |
| AC-3 | 列表验收（空态+skip 门） | Task 0 | 0.4 场景 S4 | `test_acceptance_white_label_report.py` |
| AC-4 | BrandRenderSpec+渲染器三件 | Task 3 | 循环 A VO/循环 B 品牌应用/循环 C 默认态等价 | `test_reportlab_pdf_renderer_brand.py` |
| AC-4 | Pdf 服务 v1.1.0 编排 | Task 4 | 循环 C pdf 品牌段 | `test_pdf_report_generation_service.py` |
| AC-4 | 白标导出主链验收 | Task 0 | 0.4 场景 S5/S7 | `test_acceptance_white_label_report.py` |
| AC-5 | 100% 准确结构化四件套 | Task 3/8 | Task 3 传递链+Task 8 端到端解析 | 单测+`test_integration_white_label_report.py` |
| AC-5 | 准确验收（PDF 解析） | Task 0 | 0.4 场景 S6 | `test_acceptance_white_label_report.py` |
| AC-6 | 品牌段 v1.1.0 三形态 | Task 6 | 循环 A 读配置三形态 | `test_consultant_view_service.py`（更新） |
| AC-6 | 6-10 回归面六项处置 | Task 6 | 6.1-6.6 义务清单 | 6-10 三文件（更新） |
| AC-6 | 联动验收 | Task 0 | 0.4 场景 S10 | `test_acceptance_white_label_report.py` |
| AC-7 | 494/495 两新码全注册 | Task 1 | 循环 B 异常扩展 | `tests/unit/domain/exceptions/` |
| AC-7 | 异常路径验收 | Task 0 | 0.4 场景 S2/S8/S9 | `test_acceptance_white_label_report.py` |
| AC-8 | 保存 P95<200ms | Task 0/8 | 0.4 场景 S11+集成性能 | 验收+`test_integration_white_label_report.py` |
| AC-8 | 导出 P95<60s 继承 | Task 0 | 0.4 场景 S12 | `test_acceptance_white_label_report.py` |
| 全 AC | 收尾完成清单 | Task 9 | 9.1-9.4 | `test_acceptance_white_label_report.py` |

---

## 📋 Tasks / Subtasks 任务分解

> ⚠️ **TDD 循环内化原则：** 每个 Task 必须独立完成 红→绿→重构 循环，禁止将测试编写推迟到单独 Task。
> 每个 Subtask 组内的 TDD 循环按领域粒度拆分。

---

### Task 0: SDD 规范定义（必选前置）

**关联 AC:** AC-1~AC-8（全量——规范冻结是全部实现的前置）

> **目的：** 在进入代码实现前，明确实体契约、预设常量、BrandRenderSpec 键契约、端口演进、018 表结构、验收场景与六边形架构边界，并处置 deferred-work 锚定义务（L129 六轮处置+L13/L17/L107/L117+L170/L127/L369/L370/L395/L396/L402/L403/L409 逐条对表——Task 0.7 落档）。

- [x] Subtask 0.1: 冻结 BrandTemplate 实体 7 字段契约+BrandRenderSpec 7 键契约（Task 0.1 冻结表落 Dev Agent Record——实现禁增删键）
- [x] Subtask 0.2: 冻结预设常量（COLOR_SCHEME_PRESETS 三套 5 色 hex 值逐字钦定+FONT_PRESETS 两项[stsong/noto-sans-sc]+呈现名映射+TTF 资产钦定[来源/许可/放置路径/sha256 登记]——Task 0.2 冻结表）
- [x] Subtask 0.3: 定义端口契约（R1 仓储 Protocol 三方法+R2 服务 Port 三方法+三处 v1.1.0 演进签名+4 新注册名与组合根落位锚[6-5b 注册块 :3692 块尾邻位+consultant_view 块 :2177 后]+018 表结构 DDL 冻结）+ 契约测试文件骨架
- [x] Subtask 0.4: 编写 Gherkin 验收测试 `tests/acceptance/test_acceptance_white_label_report.feature`（14 场景钉死——**每场景 Then 均有可执行断言**[6-9 先例形态]；epics L2537-2545 架构测试三项落位对账：品牌模板配置测试→S1~S4/品牌应用测试→S5~S7/模板复用测试→S13；S1 保存主链/S2 值域守卫[编程面 use case 直调——CLI choices 是 exit 2 硬拦截 494 不可经 CLI 触达]/S3 Logo 格式/S4 列表空态[前置零行清点有行 skip——背景行防御]/S5 白标导出主链/S6 品牌准确四件套[font_preset 钦定 noto-sans-sc——stsong 与默认同字体恒真]/S7 默认态回归[断言形态=metadata 零品牌键对照+对象键通道不变+6-5b 既有测试零修改——不写两次导出 byte 相等]/S8 模板不存在/S9 参数组合守卫/S10 consultant-view 联动/S11 保存性能/S12 导出性能/S13 跨 plan 复用/S14 收尾完成清单）
- [x] Subtask 0.5: 编写 BDD 步骤实现 `tests/acceptance/test_acceptance_white_label_report.py`（6-10 R6 合规形态第七连：三件套[_run_async+模块级 event_loop+context dict]+三清+CLI 直调 helper[brand-template-save/list+report-generate 三清先例 :457-476 直系]+**模块级零新词族 import 硬纪律**[src 符号延迟到步骤函数内]+模板行预置走 `resolve("brand_template_repository").save(entity)` 直写通道[6-10 `_save_archive_row` :301-335 直系；**多模板行预置实体显式 updated_at 构造**——6-10 `_preset_anchor` :280-292 单一 now 基准+微秒偏移同款：直写绕过服务定时戳而 PG now() 是事务开始时间同事务恒值，隐式构造致排序退化 tie-break]+teardown 定向 DELETE rowcount 断言+L4 logo 对象登记清理+**brand-assets 桶自愈建桶**[bucket_exists 探测→make_bucket 勿带 object_lock——store 对缺桶抛 NoSuchBucket，src 零生产建桶，6-5b 验收探测+自愈先例直系]+**BLM 产物预置 helper**[导出场景 Given：`_assemble_archive_only` 九依赖轻装配+`_archive_steps` 八阶段逐段 compose_and_archive_step_chain——6-5b 验收 :600-758 直系；归档三面残留清理（档案行/Qdrant 点/WORM blob）:309-391 直系]+**渲染正例 Logo 用 Pillow 生成最小合法 PNG**[仓内既有 PNG 测试字节是截断假体——magic 8 字节可过但 ImageReader 渲染 492；Pillow 已是项目依赖零新依赖；magic 负例用文本/截断字节]+**导出副产物三面清理**[strategic_reports 行 `_cleanup_report_rows` :283-306+event_outbox 行 `_cleanup_outbox_rows` :258-281+WORM PDF 对象**裸 client remove_objects(bypass_governance_mode=True)**——端口 delete 对锁定对象抛 ComplianceLockError，6-5b `_cleanup_pdf_objects` :393-412 直系]+**pytestmark xdist_group("blm-planning-perf")**+P95 双场景[保存 200ms/导出 60s——20 轮 sorted[ceil(0.95n)-1] 公式]）；运行验收测试，确认失败（🔴 红阶段验证——逐场景红形态见 Task 0.6 符号表：CLI 直调场景为 argparse exit 2→SystemExit 捕获→exit_code 断言 AssertionError 形态[6-10 :470 行内注释亲注先例（helper :457-476）——R2 勘误：exit-2 亲注在 :470 行内注释非 :465-468 docstring]，含预置/服务类延迟 import 的场景为 ImportError 形态）
- [x] Subtask 0.6: 定义逐场景红锚符号表（14 场景逐场景标注「首个新词族触达点」——**CLI 直调无预置场景**[S1 保存 When 直调/S3 格式守卫 When 直调/S4 列表 When 直调]：argparse invalid choice/unrecognized **exit 2**→SystemExit 捕获→exit_code 断言 AssertionError[6-10 :470 行内注释亲注先例——helper :457-476]；**含预置或服务类延迟 import 场景**[S2 编程面 Given 预置/S5/S6/S7/S10/S11/S12/S13 的 Given 预置 helper 或服务类 import]：ImportError 形态；**S8 模板不存在**[report-generate 既有命令+--brand-template 未注册]：unrecognized arguments exit 2（与 S9 同机理）；**S9 组合守卫**[纯参数面无预置]：exit 2；**S14**：_COMPLETION 文件不存在 AssertionError[6-10 S12 直系]）
- [x] Subtask 0.7: deferred-work 锚定义务处置落档（OD-8 表——L129 六轮处置[6-11 分支消费+批量分支注销+锚位收敛 Epic 7]+13 条逐条对表注记[既有锚 12 条+新增观察面 #13]）
- [x] Subtask 0.8: 关键代码锚点行号复核（并行会话提交会使行号漂移——锚点表基准 HEAD@9258b36d，实施前复核）

**完成标准/Definition of Done:**
- [ ] 规范项全部定义完毕（两张 VO 键契约冻结表+预设冻结表+端口/表结构冻结+场景钉死+锚定义务）
- [ ] 验收测试运行失败（预期行为，红阶段确认——14 场景全红；逐场景红形态以 Task 0.6 符号表为准[CLI 直调场景 exit 2→AssertionError/预置场景 ImportError/S14 文件不存在 AssertionError]）

---

### Task 1: 领域层——BrandTemplate 实体 + 仓储端口 + 494/495 异常扩展

**关联 AC:** AC-1/AC-7

> **六边形落位：** `src/domain/entities/brand_template.py` + `src/domain/ports/brand_template_repository.py` + `src/domain/exceptions/report_exceptions.py`（扩展）——domain 纯标准库零外部依赖。

#### TDD 循环 A：BrandTemplate 实体

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/entities/test_brand_template.py`（7 字段默认值/构造成功/frozen setattr 抛/`__post_init__` 242 守卫负例全枚举[空 name/超 100 长 name/空 color_scheme/超 30 长 key/logo_object_key 可 None 正例]） |
| 🟢 绿 | 实现 `src/domain/entities/brand_template.py`（frozen dataclass+`__post_init__` 守卫——实体构造抛 `EntityValidationError` 242，context 携带 field/value） |
| 🔄 重构 | docstring 全中文 Google 风格（值域校验落应用服务的依赖方向注记+UPSERT by name 语义注记），运行 `ruff`+`mypy` |

#### TDD 循环 B：494/495 异常扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/domain/exceptions/` 扩展用例（两类构造/context 键/`to_dict()` 序列化/EXCEPTION_HTTP_MAP[494→400/495→500]/编码唯一性+子域范围 8 项族复跑） |
| 🟢 绿 | 实现 `BrandTemplateValidationError`(EXCEPTION_494)+`BrandTemplateStorageError`(EXCEPTION_495)（BusinessException 族——490-493 同构；同步 `_code_ranges.py` report 行注释+`_CLASS_TO_SUBDOMAIN`+`__init__.py` 导出+sisys-uni-exception-design.md §3.3.2） |
| 🔄 重构 | 消息模板统一（合法预设键清单入消息——调用方可理解性） |

- [x] Subtask 1.1: 🔴 红 — 循环 A+B 失败测试
- [x] Subtask 1.2: 🟢 绿 — 实体+仓储 Protocol+两异常最小实现（Protocol 三方法签名与 Task 0.3 冻结逐字一致）
- [x] Subtask 1.3: 🔄 重构 — docstring+类型注解收口
- [x] Subtask 1.4: 🟡 变异 — 守卫突变实证（删 name 非空守卫 → 空名构造绿 → 还原红；494 code 改 496 → 唯一性测试红——证明断言活着）

**完成标准/Definition of Done:**
- [ ] 实体+Protocol+两异常实现完成，契约与 Task 0.1/0.3 冻结表逐字一致
- [ ] TDD 循环全部通过（红绿变异三态留痕）
- [ ] `poetry run pytest tests/unit/domain/ -v` 全绿（含既有 8 项族零回归）
- [ ] 覆盖率：新增实体+异常 ≥95%

---

### Task 2: 基础设施存储面——018 migration + BrandTemplateModel + PostgreSQLBrandTemplateRepository

**关联 AC:** AC-1

> **六边形落位：** `deploy/postgresql/alembic/versions/018_brand_templates.py` + `src/infrastructure/storage/postgresql/models/brand_template.py` + `src/infrastructure/storage/postgresql/repository/brand_template_repository.py`——017/ReportModel/PostgreSQLReportRepository 三件直系复刻。

#### TDD 循环 A：migration + ORM Model

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 migration/Model 验收断言（018 文件存在+revision 链 018→017+列集/UNIQUE 约束/索引与 Task 0.3 DDL 冻结逐字比对——6-5b migration 断言形态）；`alembic upgrade head` 后 `\d brand_templates` 列断言 |
| 🟢 绿 | 实现 018 migration（create_table+UNIQUE(name)——**UNIQUE 先例援引 007 snapshots version unique[017 无 UNIQUE 约束先例，仅 PK]**+列结构/server_default now() 017 :21-47 范本直系）+BrandTemplateModel（Base 导入 models/outbox.py——ReportModel 同源） |
| 🔄 重构 | migration 文件头注记（「只增 migration 红线——已合入禁改」+与 Model 镜像声明） |

#### TDD 循环 B：仓储实现（真实 PG）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/storage/test_brand_template_repository.py`（真实 PG session——6-5a test_report_repository.py 先例：save INSERT 新行/get_by_name 命中与未命中 None/**UPSERT 落库语义仓储层**：按实体 template_id 有行 UPDATE 三配置字段+updated_at/无行 INSERT[保留字段由服务侧先行 get_by_name 钦定后传入——仓储不承载保留判断，见 Task 4 编排锚]/并发双 INSERT 撞 UNIQUE(name)→IntegrityError→495 包装负例[**仓储测试实体构造通则[R2]**：所有形态实体自带显式 updated_at——UPDATE 形态 None 时 UPDATE 写 NULL 撞 NOT NULL 且被 IntegrityError→495 路径误吞；list 双序断言：updated_at 降序+name 字典序 tie-break——跨事务 save 或显式构造保证主排序键可区分（同事务 now() 同值退化 tie-break 致排序突变锚失效）]/实体↔Model 映射隔离[_to_entity/_to_model 往返]；**pytestmark 挂 xdist_group("blm-planning-perf")**——真实 PG 写入方同组串行[漏挂致 6-10 S3 意外 skip]） |
| 🟢 绿 | 实现 `PostgreSQLBrandTemplateRepository(BrandTemplateRepositoryProtocol)`（session_factory 注入+ContextVar session 优先 fallback 双模式——report_repository :103-124 直系；UPSERT 语义：按实体 template_id 落库[有行 UPDATE/无行 INSERT]+IntegrityError→BrandTemplateStorageError 495 包装） |
| 🔄 重构 | 映射函数收口+`__all__` |

- [x] Subtask 2.1: 🔴 红 — 循环 A/B 失败测试
- [x] Subtask 2.2: 🟢 绿 — migration+Model+仓储最小实现
- [x] Subtask 2.3: 🔄 重构 — docstring（UPSERT 语义+双模式 fallback 注记）
- [x] Subtask 2.4: 🟡 变异 — UPSERT 突变实证（改 save 为恒 INSERT → 同名二存 template_id 变异断言红；list 排序键反转 → 双序断言红——还原绿）

**完成标准/Definition of Done:**
- [ ] migration+Model+仓储实现完成（`alembic upgrade head` 幂等）
- [ ] TDD 循环全部通过（变异锚 2 处留痕）
- [ ] 覆盖率：仓储 ≥95%（UPSERT 两分支+排序+映射全覆盖）

---

### Task 3: 基础设施渲染面——字体资产 + BrandRenderSpec + ReportLabPdfRenderer 品牌扩展

**关联 AC:** AC-4/AC-5

> **六边形落位：** `src/application/ports/pdf_report.py`（BrandRenderSpec VO+render v1.1.0 签名——渲染契约面）+ `src/infrastructure/reporting/reportlab_pdf_renderer.py`（品牌应用三件）+ `src/infrastructure/reporting/fonts/NotoSansSC-Regular.ttf`（资产）。

#### TDD 循环 A：BrandRenderSpec VO + 端口 v1.1.0 签名

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 VO 契约测试（7 键 exact set+frozen+hex 色键格式守卫[6 位 hex——242 格式守卫，application VO 抛 242 先例充分：consultant_view.py:66-91 等六文件]/logo bytes\|None 两态/**构造契约**：五色键+font_name 必填[缺省构造 TypeError——Task 0.1 冻结，防默认值与渲染器默认参数同值致等价突变锚失效]+logo 缺省默认 None 断言[6-10 R1-F2 默认值断言形态的必填版变体]+`PdfRendererPort.render` 双参签名断言[inspect.signature 参数键集 {self, document, brand}]） |
| 🟢 绿 | 实现 BrandRenderSpec（frozen dataclass 7 键+hex 格式 `__post_init__` 守卫）+render 签名扩展（keyword-only `brand: BrandRenderSpec \| None = None`——既有单参调用零破坏） |
| 🔄 重构 | docstring（渲染契约面语义+「logo 读取归应用服务、渲染器零 IO 纯函数」纪律注记） |

#### TDD 循环 B：渲染器品牌应用三件

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer_brand.py`（**字体**：spec.font_name=注册名 → 产物字体资源含名/`_style()` base fontName==spec 值 spy 断言；**配色**：五色键驱动——表头底/网格/callout 双色/标题色逐色断言[styles/内联字面量参数化后的值级]；**Logo**：spec.logo bytes[测试 PNG 构造——**渲染正例须可解码**：Pillow 生成最小合法 PNG（仓内既有 PNG 测试字节是截断假体——magic 可过但 ImageReader 渲染 492；Pillow 已是依赖零新增）；magic 负例用文本/截断字节] → 首页含 Image Flowable[产物 XObject 断言——pypdf 解析]；**TTF 注册**：noto 预设注册幂等[双 render 不炸]+注册后可用；**brand=None**：零品牌路径） |
| 🟢 绿 | 实现渲染器品牌应用（`_apply_brand(spec)` 入口：`_ensure_font` 扩展 TTFont 注册[`_FONT_REGISTERED` 字典化]+`_style` fontName/textColor 参数化+四处硬编码色改 spec 驱动[None→原值]+logo Image[ImageReader(BytesIO)+等比缩放宽 ≤40mm 置于首页标题上方]+platypus 导入增 Image/ImageReader） |
| 🔄 重构 | 品牌样式组装收口（`_brand_overrides(spec) -> dict` 纯函数——色键映射单源） |

#### TDD 循环 C：默认态等价回归（invariant 前提）

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写等价断言（**测试前置 `reportlab.rl_config.invariant = 1`**[fixture setup 设置/teardown 还原]——默认态 trailer `/ID` 每次渲染含 time.time() 种子随机[同秒仍漂]+`/CreationDate` 秒粒度漂移，byte 级对照结构性不可比；invariant 是 reproducible builds[SOURCE_DATE_EPOCH 同族]标准前置，生产路径日期语义零触碰——主会话+双 Agent 三重实验实证）：同 document `render(doc)` == `render(doc, brand=None)` 逐字节相等——**6-5b 契约冻结面**；既有 6-5b 渲染测试全绿零修改复跑（唯一例外见 AC-4：:282 monkeypatch 行随字典化机械适配） |
| 🟢 绿 | 实现零破坏路径（brand None 早退——全部 spec 驱动分支 None 态走原值；若等价红[invariant 前提下非确定源已钉死，等价红只剩实现侵入过深一种归因]则收口——绿=重构完成的判据） |
| 🔄 重构 | 等价语义 docstring（v1.1.0 向后兼容承诺——compatibility 元组的运行面证据） |

- [x] Subtask 3.1: 🔴 红 — 循环 A/B/C 失败测试
- [x] Subtask 3.2: 🟢 绿 — VO+签名+渲染器三件+TTF 资产落地（资产获取义务：Google Noto Sans SC **官方仓 google/fonts ofl/notosanssc 仅分发 variable TTF**[NotoSansSC[wght].ttf ~17MB，默认实例=Regular wght 400，TrueType glyf 表——reportlab TTFont 可载入]——**无官方静态单字重 TTF 分发物**[R1 事实核验]；钦定官方 variable TTF 直用或 fontTools varLib.instancer 静态实例化；**非 OTF/CFF**[reportlab TTFont 不支持 CFF outline——noto-cjk 官方 repo 的 OTF/OTC 全系不可用；实施时 registerFont 成功+中文渲染正常双验证恰好覆盖 variable 载入风险]；SIL OFL 1.1 许可[可再分发嵌入]；放置 `src/infrastructure/reporting/fonts/`；文件头 docstring 登记 sha256+入仓体积注记）
- [x] Subtask 3.3: 🔄 重构 — 渲染器代码优化（色键映射单源+Image 缩放纯函数化）
- [x] Subtask 3.4: 🟡 变异 — 三件突变实证（fontName 参数化删除断言侧 → 字体断言红；header_bg 色改恒原值 → 色断言红；logo Image 流删除断言侧 → XObject 断言红；等价断言侧 brand None 改走空 spec → 等价红[空 spec 必填键构造 TypeError 或默认值≠渲染器默认——Task 0.1 构造契约判别前提]——还原全绿）

**完成标准/Definition of Done:**
- [ ] VO+签名+渲染器三件+资产实现完成，7 键契约与 Task 0.1 冻结逐键一致
- [ ] TDD 循环全部通过（变异锚 4 处留痕）
- [ ] 默认态等价成立（invariant=1 前提 byte 对照）+6-5b 渲染测试零修改全绿（唯一例外：:282 monkeypatch 值 False→空 dict 一行——哨兵字典化机械适配，AC-4 carve out）
- [ ] 覆盖率：渲染器新增分支 ≥95%

---

### Task 4: 应用层——预设常量 + BrandTemplateService + PdfReportGenerationService v1.1.0 品牌编排

**关联 AC:** AC-1/AC-2/AC-4

> **六边形落位：** `src/application/ports/brand_template.py` + `src/application/services/brand_template_service.py`（新建）+ `src/application/services/pdf_report_generation_service.py`（扩展）——两依赖注入（brand_template_repository+l4_object）keyword-only。

#### TDD 循环 A：预设常量 + save 编排 + 校验矩阵

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_brand_template_presets.py`（三套 exact set 键+每套 5 色 hex 值与冻结表逐字断言+呈现名映射+两项字体[stsong→CID 名直用/noto-sans-sc→注册名]）+`test_brand_template_service.py` 循环 A（**save 编排顺序锚**：`get_by_name` **先行**[同名取既有 template_id+logo_object_key——L4 键锚定与保留语义的单源承载位]→值域校验→logo 校验→[logo_path 在场]L4 store[logos/{既有或新 template_id}——换格式重传同键覆盖]→实体构造[无 logo_path 时 logo_object_key 沿用既有行值承载保留语义；updated_at=datetime.now(timezone.utc) 服务侧定时戳]→repo.save[仓储纯 UPSERT 落库][spec Mock await 序断言：**get_by_name→store→save**]；**校验矩阵七形态**：非法 color key/非法 font key/空 name[242 由实体抛——服务透传]/magic bytes 非 PNG-JPEG/超 2MB/路径不存在/合法全参——「校验矩阵七格」494×5+242×1+成功×1[与 AC-7「七形态=494 全触发面」分立口径——矩阵含 242/成功格，名称分立防混读——R2 注记][R2 代码审查勘误：R1-F6 拓宽像素/解析负例后矩阵终态 13 格——494×10+242×1+成功×2]） |
| 🟢 绿 | 实现 `ports/brand_template.py` 常量+`BrandTemplateService.save_brand_template`（get_by_name 先行取既有 template_id/logo_object_key[保留语义与键锚定单源]→值域校验+**name 前置预检**[非空/≤100 在 L4 store 前服务预检——实体 __post_init__ 242 保留为最终防线；预检防「非法 name+logo 形态」store 先行产生孤儿 logo 对象——R3 裁定]→logo 校验→L4 store[logos/{template_id} 键+content_type 推断]→BrandTemplate 构造[保留语义构造时承载：无 logo_path 沿用既有键；updated_at 服务侧定时戳]→repo.save[仓储按 template_id 纯 UPSERT 落库——保留判断归服务侧单源]） |
| 🔄 重构 | 校验函数收口（`_validate_preset_keys`/`_validate_logo_file` 两私有方法——七形态消息模板单源） |

#### TDD 循环 B：get_render_spec 组装 + L4 logo 读回

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写循环 B 用例（get_render_spec：模板存在→预设映射 hex+font_name+L4 retrieve logo bytes 组装 7 键 spec；模板不存在→494[message 含模板名]；**logo 缺席模板**→spec.logo=None；L4 异常→495 包装；**L4 读回零调用断言**：无 logo 模板→retrieve await_count==0） |
| 🟢 绿 | 实现 `get_render_spec(name)`（repo.get_by_name→None 抛 494；预设常量映射五色+font_name；logo_object_key 在场→l4.retrieve 聚合 bytes[retrieve 是 def 返回 AsyncIterator——`async for chunk` 聚合形态照 chain_of_thought :298 先例；异常→495]；BrandRenderSpec 构造返回） |
| 🔄 重构 | 组装纯函数化（`_spec_from_template(template, logo_bytes)` ——便于 pdf 服务单测 stub） |

#### TDD 循环 C：PdfReportGenerationService v1.1.0 品牌编排

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_pdf_report_generation_service.py`（**brand_template_name=None 既有路径零变化**[6-5b 既有用例零修改全绿]；brand 参在场：get_render_spec 调用锚+render(document, brand=spec) 双参调用锚[spec Mock call_args]+metadata 品牌两键[brand_template_id/brand_applied 直推+无品牌对照腿零品牌键]；get_render_spec 抛 494 → 透传[导出前置校验语义——非降级]；brand spec 组装异常 → 透传不吞） |
| 🟢 绿 | 实现 v1.1.0（注入第十依赖 brand_template_service[现状九依赖+两配置参数→v1.1.0 十依赖，组合根 lambda 9 参→10 参]+`generate_pdf_report(plan_id, *, brand_template_name=None)`——**get_render_spec 前置于聚合查询**[R3 钦定：「导出前置校验语义」落位兑现——后置则 S8 裸 plan 先撞 490 非 494 场景结构性红；前置则 S8 免 BLM 预置直达 494]→渲染双参→metadata 增两键） |
| 🔄 重构 | 品牌段编排 docstring（六段→六段+品牌前置小步说明+「品牌失败不降级为非白标导出」诚实语义注记） |

- [x] Subtask 4.1: 🔴 红 — 循环 A/B/C 失败测试
- [x] Subtask 4.2: 🟢 绿 — 常量+服务+v1.1.0 编排最小实现
- [x] Subtask 4.3: 🔄 重构 — 校验/组装收口+docstring
- [x] Subtask 4.4: 🟡 变异 — 突变实证五锚（预设 hex 改值 → 值级断言红；校验顺序换[先 L4 后校验] → L4 零调用断言红；logo 保留语义删[无 logo 再存清空] → 保留断言红；metadata 品牌键漏写 → 两键断言红；brand 参错传 None → 双参调用锚红——还原全绿）

**完成标准/Definition of Done:**
- [ ] 常量+服务+v1.1.0 编排实现完成（预设 hex 与 Task 0.2 冻结逐字一致）
- [ ] TDD 循环全部通过（变异锚 5 处留痕）
- [ ] 6-5b 既有 pdf 服务用例零修改全绿
- [ ] 覆盖率：新增文件 ≥95%

---

### Task 5: 用例 + CLI 命令族 + 组合根注册

**关联 AC:** AC-1/AC-3

> **六边形落位：** `src/application/use_cases/save_brand_template.py` + `list_brand_templates.py`（新建）+ `src/application/use_cases/generate_pdf_report.py`（**扩展[R3 补位]——execute 增 keyword-only `brand_template_name: str | None = None` 透传：--brand-template 传递链 CLI→use case→服务的必需中间环节，注册零改动维持 v1.0.0[可选参默认 None 向后兼容零破坏]**）+ `src/entrypoints/agent_cli.py`（两新命令+report-generate 扩展）+ `src/composition_root.py`（4 新注册块+3 处版本升级）。

#### TDD 循环 A：双用例 + 组合根注册

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `test_save_brand_template.py`+`test_list_brand_templates.py`（透传断言[参数键集+await_once_with]+异常传播+架构注记测试[getsource 零 EntityValidationError 字样——6-10 :62-69 直系]）+ `tests/contracts/test_port_contract_white_label_report.py` 骨架（五断言族中 registered+getsource 注入链两断言先行红——注册名/lambda 未在册） |
| 🟢 绿 | 实现两用例（keyword-only 透传——GenerateMarkdownReportUseCase :16-52 直系）+组合根 4 新注册块（brand_template_repository[SCOPED session_factory]+brand_template_service[SINGLETON 双依赖]+两用例[SINGLETON]——6-5b 注册块 :3600-3692 块尾邻位）+**本批 2 处版本升级**（pdf_renderer/pdf_report_generation_service v1.1.0[+brand_template_service 依赖——现状九依赖+两配置参数→十依赖，lambda 9 参→10 参]+`GeneratePdfReportUseCase` execute 增 brand_template_name 透传[注册零改动维持 v1.0.0——可选参向后兼容]——compatibility=("v1.0.0",) 元组）+**consultant_view 升级预告注记**（归 Task 6 原子批——注册版本+lambda 三依赖+服务实现+docstring 勘误+契约拆分**五件同批**：R3 裁定，lambda 三依赖先落而服务两参则 resolve TypeError 破坏 6-10 全测试面） |
| 🔄 重构 | 注册块注释（OD 裁定注记+**措辞纪律：新块注释禁 `--format`/`--plan-id` 字样**——防 getsource 切块断言边界污染[6-9 教训第四连]；**切块机制三注记**：①切块标记依赖 `add_parser(\n        "<cmd>"` 8 空格缩进+换行字面形态——新命令注册保持同款缩进否则 split 不命中；②brand-template-list 的前置注释落入 brand-template-save 块内[块尾截至下一 add_parser]——两新块注释措辞纪律互相覆盖；③现有三断言块[executive/analyst/consultant-view]在插入点之前不受影响） |

#### TDD 循环 B：CLI brand-template-save / brand-template-list 命令

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 `test_agent_cli.py`（**Parser 格**：两命令注册锚+参数定义[--name/--color-scheme choices 三键/--font-preset choices 两键/--logo-path 可选]+getsource 块边界断言[新块零 --format 字样]；**执行格**：五步定式[Stub patcher 每命令族专用——6-10 :3764-3767 直系]+成功输出契约[保存：`品牌模板已保存: {name}`+`配色: {呈现名} | 字体: {呈现名} | Logo: {已上传|未设置}`+`模板标识: {template_id}`；列表：首行计数+逐行+空态+提示行]+DomainError `[EXCEPTION_494]` stderr exit 1+UUID 无关参数零守卫面注记[name 非 UUID——242 UUID 守卫不适用，name 非空校验在服务/实体]） |
| 🟢 绿 | 实现两命令（argparse 注册 :631 isolation-logs 块后邻位+五步定式执行函数 `_run_brand_template_save_cli`/`_run_brand_template_list_cli`——checkpoint-create 写命令 :1188+ 直系+纯 stdlib print） |
| 🔄 重构 | 输出契约 docstring（「输出即契约」哲学+列表行序 updated_at 降序注记） |

#### TDD 循环 C：report-generate --brand-template 同入口扩展

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 扩展 report-generate 既有测试段（**参数格**：--brand-template 可选默认 None+choices 不限[自由名——模板名非枚举]+**组合守卫格**：--brand-template+--format markdown → `[EXCEPTION_494]` stderr exit 1[post-parse 检测——_parse_correction_group 函数体 :1874-1925+守卫调用点 :2026-2032（含 DomainError stderr [code] exit 1 呈现块）成组约束先例直系]；**透传格**：--brand-template X → use case 调用参数锚[X 入参]；**默认格**：无 --brand-template → 既有调用形态零变化[6-5b 用例零修改]） |
| 🟢 绿 | 实现（add_argument[default=None metavar=TEMPLATE_NAME help 品牌模板名]+分发透传+`_print_report_summary` 品牌增量行[`品牌模板: {name}（已应用）`——brand 参在场时]+组合守卫 post-parse 检测） |
| 🔄 重构 | 参数 help 文案（与 6-5b --format help 风格对齐——含 Story 注记） |

- [x] Subtask 5.1: 🔴 红 — 循环 A/B/C 失败测试
- [x] Subtask 5.2: 🟢 绿 — 双用例+组合根+两新命令+扩展参数最小实现
- [x] Subtask 5.3: 🔄 重构 — CLI 输出/注释措辞收口
- [x] Subtask 5.4: 🟡 变异 — 突变实证四锚（组合守卫删除断言侧 → markdown+brand 组合直通红；透传漏传 brand 参 → 参数锚红；choices 语义错改枚举 → 自由名格红；版本漏升 v1.1.0 → 契约断言红[Task 7 预跑]——还原全绿）

**完成标准/Definition of Done:**
- [ ] 双用例+4 注册块+两新命令+扩展参数实现完成（17 命令族→19——加法闭合）
- [ ] TDD 循环全部通过（变异锚 4 处留痕）
- [ ] 6-5b 既有 report-generate 用例零修改全绿
- [ ] 覆盖率：新增 ≥95%

---

### Task 6: consultant-view 品牌段联动 v1.1.0 + 6-10 回归面处置

**关联 AC:** AC-6

> **性质说明：** 本 Task 是 6-10 对接锚的兑现面（BrandSection 读配置演进）+ 6-10 交付测试的预期演进更新——跨 Story 修改须逐项清单化。

#### TDD 循环 A：品牌段读配置三形态

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 更新+扩展 `tests/unit/application/test_consultant_view_service.py`（**三形态**：零模板[list 返回空]→五键全默认值[与 6-10 恒值逐字相等断言]；有模板[最新行 mock——updated_at 降序首行]→configured True+logo_status[键在场→已配置/缺席→未设置]+color_scheme_status/font_status[预设呈现名直推]；查询异常[AsyncMock side_effect]→degraded True+默认值+不抛；第三依赖构造签名断言[_make_service 工厂三参]） |
| 🟢 绿 | 实现 v1.1.0（`ConsultantViewService` 增 brand_template_repository keyword-only 第三依赖+`_build_brand_section` 改 async 读 list_templates 首行派生+段级 try 容错[降级语义激活]；ports 文件三处 docstring 触发器注记勘误[:27-28/:31-34/:121-129——「6-11 实施后」兑现注记+degraded 恒 False 承诺勘误]；spec.version v1.0.0→v1.1.0） |
| 🔄 重构 | 品牌段派生 docstring（最新模板口径+呈现名映射单源引用预设常量[import application 同层合法]） |

#### 6-10 回归面义务清单（逐项勾选——预期演进信号兑现非删除）

- [x] 6.1: `consultant_view.py` 三处 docstring 注记勘误（触发器兑现+v1.1.0 语义）
- [x] 6.2: CLI 提示行更新：agent_cli.py:1806 `提示: 品牌模板配置归 Story 6-11（白标报告基础）` → `提示: 执行 brand-template-save 配置品牌模板`（:1820 导出提示行**不动**——最小面裁定）+**CLI 品牌显示块三值改派生[R3 补位]**：:1800-1804 consultant-view 显示行「Logo: 默认 | 配色: 默认」两段硬编码改 BrandSection 派生值[logo_status/color_scheme_status 直引]——v1.1.0 后 configured 态「已配置+默认」并存自相矛盾（6-10 交付呈现面语义破损）
- [x] 6.3: 6-10 单测更新：`_build_brand` 行为断言改三形态 Mock（6-10 原断言「与常量恒等」→ 零模板形态保留恒等+两新形态）
- [x] 6.4: 6-10 验收 S3 前置更新：品牌模板表零行清点（有行 pytest.skip——共享库背景残留防御；断言本体零改动）
- [x] 6.5: 6-10 CLI 单测/验收提示行断言联动更新（「归 Story 6-11」→ 新文案 in lines）+品牌显示块断言联动（6.2 派生改造对应行）
- [x] 6.6: 组合根 consultant_view lambda 两依赖→三依赖+契约测试 getsource 注入链锚更新（增 `'"brand_template_repository"'` 字面量锚）+**版本断言拆分**（test_port_contract_consultant_view.py:30-33 PORT_NAMES 两名循环——service 期望 v1.1.0/use_case 维持 v1.0.0，机械改断言值会致 use_case 假红）

**完成标准/Definition of Done:**
- [ ] v1.1.0 品牌段三形态全绿+6-10 三文件（ports/service 单测/CLI 单测/验收）回归更新后全绿
- [ ] TDD 循环通过+变异 1 锚（三依赖漏注入 → 构造断言红）
- [ ] 6-10 验收测试整体复跑全绿（S3 skip 门生效形态验证）

---

### Task 7: 契约守护与冻结面回归

**关联 AC:** AC-1~AC-7（横切守护）

> **性质说明：** 端口契约测试+三处版本升级断言+事件冻结计数复跑+6-5b/6-10 冻结面全量回归——本 Task 不新增生产码。

- [x] Subtask 7.1: 补全 `tests/contracts/test_port_contract_white_label_report.py`（Task 5 骨架两断言外补全五断言族全量：4 新注册名 registered+spec 元数据[版本/lifetime/owner/tags 含 brand]+interface is 具体类+lambda getsource 注入链[依赖注册名带引号字面量锚]+resolve 可达 isinstance 注入链非 None+方法签名键集[save_brand_template 四参 keyword-only/get_render_spec 单参]）
- [x] Subtask 7.2: 版本升级断言（pdf_renderer/pdf_report_generation_service/consultant_view_service spec.version=="v1.1.0"+compatibility 元组含 "v1.0.0"——**既有契约测试必须更新仅 test_port_contract_consultant_view.py:33 一处**[版本等值断言唯一所在，拆分 service v1.1.0/use_case v1.0.0]；test_port_contract_pdf_report.py 仅 `startswith("v")` 无等值断言——**pdf 系两处等值断言（pdf_renderer/pdf_report_generation_service v1.1.0）落本 Story 新契约文件承载**[R2 钉死：既有 pdf 契约测试不改]；SERVICE_INJECTION_DEPENDENCIES 可选增列 brand_template_service 成十依赖[防「九依赖」注释漂移，非红面]）
- [x] Subtask 7.3: 事件冻结复跑（三处 `_FROZEN_EVENT_COUNT=56` 契约测试零修改全绿+event_channels.yaml/DEFAULT_MAPPINGS 零 diff git 证据）
- [x] Subtask 7.4: 全量回归（`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`——显式四目录；6-5a/6-5b/6-8/6-9/6-10 五 Story 验收文件零失败）

**完成标准/Definition of Done:**
- [ ] 契约测试五断言族全绿+三处版本断言绿
- [ ] 56 冻结计数零变化+yaml/router 零 diff
- [ ] 四目录全量回归零失败（预存环境抖动甄别口径——isolation-switch-log 时序敏感先例外）

---

### Task 8: 集成测试——真实链端到端

**关联 AC:** AC-1/AC-2/AC-4/AC-5/AC-8

> **形态：** 真实服务模式（独立 PG schema+savepoint rollback+MinIO **共享 default 桶**[resolve 通道派名——组合根未传 tenant_id 恒 `{prefix}-brand-assets-default`，对象键锚 template_id 定位+定向清理；6-5b 集成共享桶先例直系]+**自愈建桶**前置[bucket_exists 探测→make_bucket 勿带 object_lock]）+真实渲染端到端。

#### TDD 循环 A：真实链五场景

| 阶段 | 动作 |
|------|------|
| 🔴 红 | 编写 `tests/integration/test_integration_white_label_report.py`（场景①保存主链[brand-assets 桶自愈建桶前置+真实 PG 行+真实 MinIO logo 对象+读回逐字节]；场景②UPSERT 修订[同名二存 template_id 稳定+**updated_at 前进点名断言**[二存值>首存值——AC-1 语义的端到端单点承载]+L4 同键覆盖]；场景③白标导出端到端[真实 BLM 产物预置→generate_pdf_report(plan_id, brand_template_name=...)→L2 行品牌两键+L4 WORM PDF 对象]；场景④**品牌应用 100% 准确端到端**[pypdf 解析产物：品牌字体资源名[noto-sans-sc 形态]+首页 Image XObject 在场+品牌色 RGB 在内容流[fp_str 格式期望串]——对照腿：无品牌导出零图像]；场景⑤性能双段[保存 20 轮 P95<200ms+导出 20 轮 P95<60s]） |
| 🟢 绿 | 步骤实现（真实服务三件套直调+TestTenant 模板名前缀+**多模板行预置显式 updated_at 构造**[单 now 基准+微秒偏移——同事务 server_default now() 恒值致排序退化]+**teardown 顺序钦定：L4 对象清理先行、PG 行清理后行**[行清理 rowcount 断言 assert-raise 中断会跳过后续对象清理——防孤儿泄漏]+teardown 定向 DELETE rowcount 断言；**动态跳过**：PG/MinIO 不可用 pytest.skip） |
| 🔄 重构 | 场景 docstring（口径差声明三段落+背景行免疫注记） |

- [x] Subtask 8.1: 🔴 红 — 五场景失败测试
- [x] Subtask 8.2: 🟢 绿 — 步骤实现+清理链
- [x] Subtask 8.3: 🔄 重构 — docstring+口径注记
- [x] Subtask 8.4: 🟡 变异 — 端到端突变 1 锚（品牌导出链 brand 参丢弃[服务透传改 None] → 场景③④红——证明端到端断言活着）

**完成标准/Definition of Done:**
- [ ] 五场景全绿（真实 PG+MinIO+渲染）
- [ ] 性能双段达标（200ms/60s）
- [ ] 清理后零残留（行/对象复查断言）

---

### Task 9: SDD 架构约束验证 + 开发结束验收测试

**关联 AC:** AC-1~AC-8（收尾）

> **性质说明：** 架构验证测试（白名单形态——本 Story 有合法 infra 增量）+ 开发结束验收（14 场景全绿+完成清单逐项确认）。

#### 架构验证测试实现（四验证器——`test_analyst_view.py` 直系样板+6-8 白名单变体）

- [x] Subtask 9.1: 创建 `tests/unit/architecture/test_white_label_report.py`（验证器 A 落位[domain 实体/ports 文件 AST ClassDef 含 BrandTemplate/两 Port/BrandRenderSpec+常量 AST 断言]；验证器 B 零 publish[服务源码 token 扫描+DomainEvent 子类全集对比]；**验证器 C 白名单形态[R3 修正·R5 计数勘误]——白名单=三层全量合法 brand 词族新文件集 8 个**{domain: entities/brand_template.py+ports/brand_template_repository.py；application: ports/brand_template.py+services/brand_template_service.py+use_cases/save_brand_template.py+use_cases/list_brand_templates.py；infra: models/brand_template.py+repository/brand_template_repository.py}+fonts 目录（资产文件名无 brand 词族不入集）+渲染器[修改既有单列]——**集合等值比较（==）双向判别**[漏列红+多列红——`<=` 子集比较多列静默无判别]；[与 6-9/6-10 零命中形态分立注记——本 Story 非「纯三零」]；验证器 D CLI 接线[两新命令 add_parser 锚+report-generate 扩展参数锚+组合根注册锚+resolve 注入链]；SERVICE_ALLOWED_PREFIXES+FORBIDDEN_IMPORTS 照设）
- [x] Subtask 9.2: 开发结束验收场景（S14 收尾：`_COMPLETION_SRC_FILES`[**新建 9+扩展 12**=21 个 src 文件——▲12 含 domain/exceptions/__init__.py+use_cases/generate_pdf_report.py+interfaces/api/exception_handlers.py[R1 代码审查勘误：原「9+11=20」漏列 exception_handlers.py——AC-7 HTTP_MAP 注册义务的正确交付件]；migration 018 单独清单项]/`_COMPLETION_TEST_FILES` 逐项 `path.is_file()` 断言——6-10 :104-123/:1233-1246 直系）
- [x] Subtask 9.3: 全套复跑（14 场景全绿[S1~S13 功能/性能+S14 收尾]+四目录全量+`ruff`+`mypy`+覆盖率报告）
- [x] Subtask 9.4: deferred-work 处置注记落档（Task 0.7 表回写+新增观察面登记评估[若实施中发现]）

**完成标准/Definition of Done:**
- [ ] 架构四验证器全绿（白名单集精确）
- [ ] 14 场景全绿（S1~S13 功能/性能+S14 收尾）+完成清单逐项确认
- [ ] Story 可进入 `review`

---

## 📝 Dev Notes 开发笔记

### 相关架构模式和约束 Architecture Patterns & Constraints

**来源:** [`architecture.md`](../../_bmad-output/planning-artifacts/architecture.md) + [`interface-design.md`](../../docs/architecture/interface-design.md)

- **架构模式:** 六边形架构（Ports & Adapters）+ 四层分层（domain→application→infrastructure/interfaces）+ 组合根统一装配（PortSpec/Registry/Resolver/ContractGate）
- **设计约束:** 领域层零外部依赖（import-linter 强制）；依赖方向矩阵（infra→application ✓ 允许——渲染器 import application ports 常量先例在位）；端口演进 compatibility 兼容元组（v1.0.0 调用方零破坏）
- **接口治理:** 统一端口注册（4 新+3 升级）、PortSpec 元数据（name/version/interface/impl/lifetime/tags）、Composition Root 装配、契约优先、版本化兼容
- **技术栈:** Python 3.11+ / reportlab（platypus Image/ImageReader/TTFont 首启三能力）/ SQLAlchemy 2.0（新表 Model）/ alembic（018）/ MinIO（brand-assets 新桶 store 通道）/ argparse CLI
- **存储分层:** L2 PG（brand_templates 配置行）/ L4 MinIO（logo 对象 store 非 WORM + 白标 PDF 沿用 archive WORM）/ L0/L1/L3/L5 零触碰

### 关键架构决策（OD 偏离声明——Task 0 落档）

| OD | 裁定 | 依据 |
|----|------|------|
| **OD-1** | **范围边界——MVP = 品牌模板配置面（实体+PG 表+仓储+服务+CLI brand-template-save/list）+ 白标 PDF 渲染（PdfRendererPort v1.1.0+渲染器三件+pdf 服务 v1.1.0+CLI --brand-template 同入口扩展）+ 6-10 品牌段联动（consultant_view v1.1.0 读配置）。不含**：Web 可视化品牌编辑器（UX 旅程 8 全 Web 面口径——Epic 21/22 无品牌 Story，归后续 Web Story 立项，本 Story 不预建）/REST 白标 `/reports/whitelabel`+监管报告 `/reports/regulatory`（FR-SP-16 P2 → Epic 20 Story 20.4——epics L600/L714+interface-design :1484-1489）/质量评分≥9/10 与 PPT 导出（UX 旅程 8 面板口径——归 Web Story）/Markdown 品牌应用（纯文本无视觉承载——零变化声明，组合守卫显式拒绝）/报告版本链管理（6-5a OD-10 移交裁定**不立项**：strategic_reports 同 plan 多行天然保留旧报告+get_latest_by_plan latest 语义已足——白标多模板导出不改变版本链面；显式版本管理 UI 归产品立项）/批量导出管线（L129 六轮维持——见 OD-8）/多租户品牌隔离（单租户 MVP_TENANT_ID 先例；brand_templates 无 tenant 列与 strategic_reports 同口径）/模板删除/改名（YAGNI——修订覆盖语义已足，删除归后续模板管理 Story） | epics L2518-2561 范围权威+L2036 依赖钦定 + 6.1-DF5 九连 CLI-only 先例 + 6-5b OD-9/OD-11 移交 + 6-10 OD-1/OD-6 对接锚 + YAGNI |
| **OD-2** | **零新增领域事件第十连**：品牌模板保存/列表零新事件（配置面零订阅方——DictionaryUpdated[3-3] 有 API 消费面分立注记）；白标导出复用 `ReportGenerated`（report_type="pdf" 自由 str——6-5b 流经零类改动先例直系）；event_channels.yaml/DEFAULT_MAPPINGS 零 diff；`_FROZEN_EVENT_COUNT=56` 不变（三处契约测试复跑守护） | 事件语义纯度+零订阅方 YAGNI+6-5b 复用先例+零 yaml/router diff 红利 |
| **OD-3** | **存储裁定——PG 新表 brand_templates（018）+ Logo 走 L4 `store()`（新 bucket_type "brand-assets"）**:①「用户可编辑结构化配置 = PG 表」仓标准（3-3 字典/documents/strategic_reports 三先例一致——configs/ yaml 仅随代码分发的静态资产[5-2 档案先例]不适合运行时可保存模板）；②Logo **必须 L4 非 L0**：L0StoragePort.write 签名 `content: str` 纯文本 .md 专用（FileMemoryAdapter 只写 markdown——二进制不适配亲验），L4 store(file_path) fput_object 二进制安全+版本/tags；③**store() 非 archive()**：archive 是 WORM 7 年 retention（证据合规语义）——logo 需可替换覆盖，WORM 反语义；新桶 brand-assets 与 raw-documents/archive-evidence 并列（三段物理名 {prefix}-brand-assets-{tenant}）；④对象键 `logos/{template_id}` 无 ext 单键覆盖（content_type 承载 png/jpeg——换格式重传同键覆盖零垃圾对象；PDF reports/ 前缀先例同构）；⑤PG 行持 logo_object_key（documents 先例 :151 双写同构——MinIO 对象+PG 元数据行）；⑥**不选** Redis 缓存（静态配置从不过 Redis 仓纪律——TOOL_CATALOG/PHASE_STEP_DOMAINS 全进程内常量先例；单行读写 P95<200ms 充裕无需缓存）；⑦**桶创建前置**：store() 对缺桶抛 NoSuchBucket 且 src 零生产建桶/deploy 无脚本——测试面 bucket_exists 探测+make_bucket 自愈且**勿带 object_lock**（WORM 锁破坏 logo 覆盖与 teardown 清理——与 archive-evidence 的 object_lock=True 建桶先例分立）；resolve 通道组合根未传 tenant_id——物理桶恒 `{prefix}-brand-assets-default` 共享桶，隔离靠对象键锚 template_id（R1 裁定钦定共享桶+对象键级清理形态——与 6-5b 集成先例一致） | 三先例仓标准+L0 签名事实+WORM 语义分立+单租户量级 |
| **OD-4** | **预设常量单源+渲染注入形态**：COLOR_SCHEME_PRESETS（3 套×5 色 hex+呈现名——五色键与 BrandRenderSpec 五色键一一对应，font_name 由 FONT_PRESETS 正交供给）+FONT_PRESETS（2 项）冻结于 `src/application/ports/brand_template.py`（TOOL_CATALOG/PHASE_STEP_DOMAINS「静态值域=冻结常量、实例行只存 key」模式直系——PG 行零冗余 hex，改预设=改常量+版本）；**BrandRenderSpec 7 键**（font_name/title_color/header_bg_color/grid_color/callout_bg_color/callout_text_color/logo）定义 `ports/pdf_report.py`（渲染契约面——渲染器直消费形态：logo 是 bytes 非对象键[L4 读取归应用服务 get_render_spec，渲染器零 IO 纯函数纪律保持]）；**第二字体预设 = TTF 资产入仓**（stsong=STSong-Light CID 内置零注册/noto-sans-sc=官方 variable TTF[NotoSansSC[wght].ttf 默认实例 Regular——google/fonts 无静态单字重 TTF 分发，钦定直用或 instancer 静态实例化]SIL OFL 1.1 入仓 `src/infrastructure/reporting/fonts/`+TTFont 幂等注册——**简体 CID 仅 STSong-Light 一款[reportlab defaultUnicodeEncodings/typeFaces_chs 双口径亲验]**、仓内零 TTF 资产亲验，第二预设必须 TTF；**OTF/CFF 不可用注记**：reportlab TTFont 不支持 CFF outline——noto-cjk 官方 repo 的 OTF/OTC 全系不可用，实施时 registerFont 成功+中文渲染正常双验证）；**值域校验落应用服务**（domain 实体零 application import——实体仅守卫非空/长度 242，预设 key ∈ 键集校验在 BrandTemplateService 抛 494——6-3 用例层守卫先例） | 常量单源先例+渲染纯函数纪律+依赖方向矩阵+CID 字体族事实 |
| **OD-5** | **report_type 零新增——白标 PDF 沿用 ReportType.PDF + metadata 品牌键承载**：`brand_template_id`/`brand_applied` 两键入 strategic_reports.metadata JSONB（顶层自由扩展零 migration——顶层键=聚合基底+citation 族键[基数不定]之上直接追加两键；citations 条目七键 :416-427 是 JSONB 嵌套扩展先例）；**四零红利**：①LATEST_REPORT_TYPE_DOMAIN 值域零变化（6-10 frozenset 守卫零触碰零回归）②ReportType 枚举零扩（domain 值域面零改动——枚举是裸 str 守卫面）③ReportGenerated report_type="pdf" 复用（事件面零变化）④get_latest_by_plan 跨型不分语义下白标 PDF 亦是「当前交付物」（6-10 latest 遮蔽口径自然兼容）；**同模板修订跨导出追溯裁定[R3 注记]**：模板 A→plan1 导出→A 修订→plan2 导出的两份 PDF 同 brand_template_id 异渲染参数——MVP 接受：PDF 产物本身即渲染参数固化载体（旧 PDF 天然保留修订前渲染结果），模板版本快照与「清除」语义同批归后续模板管理 Story；6-10 consultant_view.py:43 的 branded_pdf 注记成为「不触发注记」——docstring 追加 6-11 裁定说明（值域本体不变） | 四零红利+JSONB 自由扩展先例+最小 domain 改动 |
| **OD-6** | **异常两新码 494/495（report 预留段首占两枚）**：`BrandTemplateValidationError`（EXCEPTION_494，400 语义——七形态伞形[494 全触发面]：非法 color_scheme key/非法 font_preset key/Logo 非合法可解码 PNG/JPEG 图像文件（magic 非法或图像体无法解析——R1-F6 拓宽）/超限（字节 2MB/像素单边 4000px）/路径不存在/模板不存在/参数组合非法[name 空值/超长归 242 实体守卫——非 494 形态]；message+context.field 区分）；`BrandTemplateStorageError`（EXCEPTION_495，500 语义——brand_templates PG 读写/L4 logo 存取）；**否决复用 242**：242 是实体不变量守卫（domain VO 构造面），品牌校验是应用层输入+存储混合面——独立码 CLI stderr `[EXCEPTION_494]` 直判可观测性更好+码段成文预留六码全空零冲突（_code_ranges.py:210）；**否决独立 NotFound 码**：「模板不存在」是输入校验失败族（与值域外同族——最少开码原则）；渲染失败复用 492（6-5b 通道——品牌渲染异常[logo bytes 损坏]走既有包装不静默降级） | 码段预留事实+可观测性+最少开码+完整注册义务[4 项强制 Checklist+3 项扩展] |
| **OD-7** | **CLI 三面扩展——17→19 命令族+同入口参数**：①`brand-template-save`（--name 必填/--color-scheme choices 三键/--font-preset choices 两键/--logo-path 可选本地路径——argparse choices 值域面[494 深层校验在服务——CLI choices 是第一道 UX 面]）；②`brand-template-list`（零参数全局清单——与 consultant-view 零参数先例第二连）；③`report-generate --brand-template <name>`（6-5b OD-11 同入口钦定兑现——可选默认 None 向后兼容[e431427c 四处增量先例直系]）；**组合守卫**（--brand-template+--format markdown → 494）post-parse 检测归 CLI 层（checkpoint-recover 成组约束 :2026-2032 先例——CLI 层唯一落位）；**注释措辞纪律**：两新命令注册块注释禁 `--format`/`--plan-id` 字样（getsource 切块断言边界——6-9 教训第四连；report-generate 块自身是 --format 的家无污染面） | 6-5b OD-11 钦定+6-10 零参数先例+成组约束先例+措辞纪律 |
| **OD-8** | **性能三段口径+锚定义务 13 条处置**：①保存 P95<200ms = save 服务面窗口（PG upsert+可选 L4 store；20 轮 sorted[ceil(0.95n)-1] 公式六连同款——毫秒级口径参照 6-3/6-6 快照族；report_repository `_persist` 单往返 :126-139 充裕佐证）；②导出<1min = 6-5b 60s P95 既有口径承载（60s<1min 钦定关系——test_acceptance_pdf_report.py:102-103）+品牌渲染增量同入口复跑（渲染纯 CPU 亚秒+logo 解码微秒——增量不构成风险面注记）；③准确率 100% = AC-5 结构化四件套（非计时——口径差声明第七连）。**锚定义务 13 条**（Task 0.7）：L129 **六轮处置+分支消费**（本 Story 裁定单 plan 单次形态——批量分支注销，再锚定条件收敛为「Epic 7 API 入口立项」；orchestration_service 废弃定夺随 Epic 7 同批——6-10 五轮+本 Story 收敛注记）/L13 第四轮不触发[现有 6-1/6-9/6-10 三条注记——R1 轮次勘误]/L17 第八轮顺延[七条注记+1 可复现]/L107 不触发（零 Skills 消费）/L117+L170 第十连零消费顺延 Epic 8/L127 第五轮不触发[现有 6-1/6-3/6-9/6-10 四条注记——R1 轮次勘误]/L369+L370 顺延 Epic 7（CLI-only 第十连）/L395+L396 维持 Epic 21-22（**L396 末尾「渲染归 6-11」注记本 Story 兑现核对**——PdfRendererPort v1.1.0 落地注记）/L402+L403 维持（CLI 入口沿用+json_chain 零触碰第四连）/L409 report-generate 既有族内（--brand-template 非 --plan-id 面——brand-template-save 含 --name 非 UUID 参数不入观察项注记） | epics L2541-2545 性能三行+六连口径差声明纪律+deferred-work 原文触发条件逐条对表 |
| **OD-9** | **测试文件命名（禁故事编号后缀）+双词族映射声明**：acceptance `test_acceptance_white_label_report.feature/.py`+integration `test_integration_white_label_report.py`（**对 epics L2558 钦定名 `test_white_label_report_integration.py` 的显式偏离**——仓规 test_integration_* 前缀，6-8/6-9/6-10 OD-9 同款偏离声明第四连）；unit/architecture `test_white_label_report.py`（**对齐 epics L2557 钦定名**——零偏离）；**双词族映射**：测试面 white_label_report（epics 钦定采纳）/src 面 brand_template（BrandTemplate 实体自然名+与 6-10 BrandSection/BRAND_* 既有词族同根连续——whitelabel/white_label src 零命中亲验，brand 词族仅 6-10 三文件[状态展示语义]本 Story 扩展为配置实现语义）；CLI 子命令 `brand-template-save`/`brand-template-list` 无重名亲验（add_parser 17 命令族逐一比对——落地后 19）；注册名 brand_template_repository/brand_template_service/save_brand_template_use_case/list_brand_templates_use_case | 记忆「禁止故事编号命名文件」+仓规前缀惯例+epics 钦定名采纳/偏离逐处声明+词族同根连续 |
| **OD-10** | **组合根 4 新注册+3 处版本升级+依赖链声明**：brand_template_repository（SCOPED v1.0.0——session_factory 注入 report_repository :3550-3559 直系）+brand_template_service（SINGLETON v1.0.0——双依赖 repo+l4_object）+两用例（SINGLETON 透传）；**升级三处** compatibility=("v1.0.0",)（hybrid_search_service :1844-1861 元组先例）：pdf_renderer v1.1.0（impl 类直传不变——签名在端口）/pdf_report_generation_service v1.1.0（现状九依赖+两配置参数→增 brand_template_service 成第十依赖[SINGLETON→SINGLETON 同态无捕获注记；组合根 lambda 9 参→10 参]）/consultant_view_service v1.1.0（三依赖 +brand_template_repository[SINGLETON 捕获 SCOPED——6-10 两 SCOPED 无混态注记延续+1]）；6-4 CLI session P0 三步排查法核验：新 SCOPED 仓储 session_factory 注入形态既有——无缺口面 | 注册先例+版本演进三先例+lifetime 惯例+session 排查义务 |
| **OD-11** | **6-10 品牌段联动兑现+回归面六项处置**：BrandSection **5 键键契约不变、值语义演进**（v1.1.0 读配置——零模板五键与 6-10 恒值逐字相等[6-10 断言前提演进为「零模板」]/有模板 configured True+呈现名派生/异常 degraded True[零 IO 恒稳承诺打破——docstring 勘误]）；呈现名单源引用预设常量（ports 同层 import 合法）；品牌段「最新行」=updated_at 降序首行（与 AC-3 行序同键——UPSERT 修订语义）；**回归面六项义务清单**（Task 6.1~6.6——docstring 勘误/CLI 提示行 :1806 更新[:1820 不动最小面]/单测三形态/验收 S3 skip 门[品牌模板表零行清点+有行 skip——共享库残留防御]/CLI 断言联动/组合根 lambda+契约锚）；**xdist 前向约束扩展**：本 Story 全部品牌模板写入方挂 blm-planning-perf 同组+teardown rowcount 断言（6-10 OD-13「新增提交型写入测试必须挂同组」约束的品牌面扩展——漏挂则与 6-10 S3 skip 门/6-7 归档面并行假红） | 6-10 OD-6 对接锚+预期演进信号兑现语义+共享库背景行风险 |
| **OD-12** | **UPSERT by name 修订语义+logo 保留语义**：save 编排=服务侧 `get_by_name` **先行**（保留语义与 L4 键锚定的单源承载位——同名取既有 template_id+logo_object_key，L4 store 用既有 template_id 作键实现同键覆盖）→校验→[logo 在场]L4 store→实体构造→repo.save（仓储按 template_id 纯 UPSERT 落库：有则 UPDATE[template_id/name/created_at 不变+三配置字段+updated_at 前进]/无则 INSERT[新 template_id]）；**updated_at 前进=服务构造实体时 datetime.now(timezone.utc) 显式定值**（report_repository 应用侧定时戳先例 :126-139——DDL server_default 仅 INSERT 初值，两机制不混用）；并发双 INSERT 撞 UNIQUE(name)→仓储捕 IntegrityError 包装 495（CLI 单进程常态低概率，防御义务归仓储）；**409 等价语义钦定为非错误**（同名保存=模板修订预期用法——CLI 面无冲突错误语义；与「资源冲突 409」Edge Case 要求的口径差声明：REST 面 20.4 届时再评估冲突语义）；logo 保留：已有 logo 模板再存不带 --logo-path → logo_object_key 与 L4 对象**不变**（修订语义：缺席≠清除——清除归后续模板管理 Story YAGNI 注记） | 最简修订语义+CLI 面语义分立+YAGNI |
| **OD-13** | **共享库断言体系延续+品牌面特化**：6-10 OD-13 四件套直系适配——①模板行预置 TestTenant UUID 前缀名（name UNIQUE 防撞+teardown 定位）；②**6-10 S3 skip 门**（品牌模板表零行清点——本 Story 写入方清理失败残留的兜底；预期零残留[同组串行+rowcount 断言]）；③consultant-view 品牌段全局查询背景行免疫 = 同组串行+自包含清理双保险（品牌段读「最新模板」是全局面——外来行必致 configured True 假红，skip 门是唯一兜底）；④性能场景背景量级敏感（品牌模板行>10 skip 门——list/最新行查询量级注记）；**L4 对象判别**：logo 对象键锚 template_id（TestTenant 前缀名→template_id 唯一——对象断言按键定位零背景免疫面） | 6-10 OD-13 直系+品牌段全局查询特化+S3 联动风险 |
| **OD-14** | **架构验证器 C 白名单形态（非纯三零）**：白名单=**三层全量合法 brand 词族新文件集 8 个**（domain 2[entities/brand_template.py+ports/brand_template_repository.py]+application 4[ports/brand_template.py+services/brand_template_service.py+use_cases/save_brand_template.py+list_brand_templates.py]+infra 2[models/brand_template.py+repository/brand_template_repository.py]——8 个 .py 文件；fonts 资产文件名无 brand 词族不入集归目录单列）+reporting/fonts/*（资产目录）+reportlab_pdf_renderer.py 扩展（既有文件单列）——**集合等值比较（==）双向判别**（R3 修正：仅枚举 infra 会自我误伤 domain/application 6 文件；`<=` 子集比较多列静默）；domain 另有 report_exceptions.py/_code_ranges.py/__init__.py 扩展（合法 domain 面——与 6-9/6-10「纯三零零命中」形态分立注记[彼零 domain 零 infra；本 Story 是 6-5a/6-5b 同构的全层 Story]）；**migration 018 合法新增**（只增红线——已合入禁改）；验证器 A/B/D 照设（A 落位含新文件 AST 断言/B 零 publish/D CLI 接线锚） | 6-8 白名单先例+全层 Story 形态+import-linter 校验面+R3 白名单自矛盾修正 |

### 项目结构说明 Project Structure（本 Story 涉及面）

```
src/
├── domain/
│   ├── entities/brand_template.py                          ★ 新建（BrandTemplate 7 字段+242 守卫——Task 1）
│   ├── ports/brand_template_repository.py                  ★ 新建（R1 基础端口三方法——Task 1）
│   └── exceptions/
│       ├── report_exceptions.py                            ▲ 494/495 两类扩展（Task 1）
│       ├── _code_ranges.py                                 ▲ report 行注释+_CLASS_TO_SUBDOMAIN（Task 1）
│       └── __init__.py                                     ▲ 494/495 两类导出（Task 1——▲ 第 10 个扩展文件）
├── application/
│   ├── ports/
│   │   ├── brand_template.py                               ★ 新建（预设冻结常量+BrandTemplateServicePort——Task 4）
│   │   ├── pdf_report.py                                   ▲ BrandRenderSpec 7 键+render v1.1.0 签名（Task 3）
│   │   └── consultant_view.py                              ▲ 三处 docstring 勘误+注记兑现（Task 6）
│   ├── services/
│   │   ├── brand_template_service.py                       ★ 新建（save/list/get_render_spec 编排——Task 4）
│   │   ├── pdf_report_generation_service.py                ▲ v1.1.0 品牌编排（Task 4）
│   │   └── consultant_view_service.py                      ▲ v1.1.0 品牌段读配置（Task 6）
│   └── use_cases/
│       ├── save_brand_template.py                          ★ 新建（Task 5）
│       ├── list_brand_templates.py                         ★ 新建（Task 5）
│       └── generate_pdf_report.py                          ▲ execute 增 brand_template_name 透传（Task 5——▲ 第 11 个扩展文件）
├── infrastructure/
│   ├── storage/postgresql/
│   │   ├── models/brand_template.py                        ★ 新建（BrandTemplateModel——Task 2）
│   │   └── repository/brand_template_repository.py         ★ 新建（UPSERT 仓储——Task 2）
│   └── reporting/
│       ├── fonts/NotoSansSC[-Regular].ttf                  ★ 新建（OFL 字体资产——文件名随渠道二择：直用 NotoSansSC[wght].ttf 或 instancer 静态实例化命名[Task 3.2 钦定后 S14 清单同步]）
│       └── reportlab_pdf_renderer.py                       ▲ 品牌应用三件+TTFont 注册（Task 3）
├── interfaces/api/exception_handlers.py                     ▲ HTTP_MAP 494/495 两行（Task 1——▲ 第 12 个扩展文件[R1 代码审查勘误补列]）
├── entrypoints/agent_cli.py                                ▲ 两新命令+report-generate 扩展（Task 5/6）
└── composition_root.py                                     ▲ 4 新注册块+3 版本升级（Task 5/6）

deploy/postgresql/alembic/versions/018_brand_templates.py   ★ 新建（Task 2）

tests/
├── unit/
│   ├── domain/entities/test_brand_template.py              ★ 新建（Task 1）
│   ├── domain/exceptions/（report 扩展）                    ▲（Task 1）
│   ├── infrastructure/storage/test_brand_template_repository.py   ★ 新建（Task 2）
│   ├── infrastructure/reporting/test_reportlab_pdf_renderer_brand.py ★ 新建（Task 3）
│   ├── application/
│   │   ├── test_brand_template_presets.py                  ★ 新建（Task 4）
│   │   ├── test_brand_template_service.py                  ★ 新建（Task 4）
│   │   ├── test_pdf_report_generation_service.py           ▲ 品牌段扩展（Task 4）
│   │   ├── test_consultant_view_service.py                 ▲ v1.1.0 三形态更新（Task 6——6-10 文件）
│   │   └── use_cases/
│   │       ├── test_save_brand_template.py+test_list_brand_templates.py ★ 新建（Task 5）
│   │       └── test_generate_pdf_report_use_case.py        ▲ 品牌透传三用例（Task 5——6-5b 文件[R1 勘误补列]）
│   ├── infrastructure/reporting/test_reportlab_pdf_renderer.py ▲ :282 carve out 一行机械适配（Task 3——6-5b 文件[R1 勘误补列]）
│   ├── interfaces/cli/test_agent_cli.py                    ▲ 三命令段扩展（Task 5/6）
│   ├── interfaces/api/test_exception_handlers.py           ▲ HTTP_MAP expected 集合同步（Task 1[R1 勘误补列]）
│   └── architecture/test_white_label_report.py             ★ 新建（Task 9——epics 钦定名采纳）
├── integration/test_integration_white_label_report.py      ★ 新建（Task 8，OD-9 偏离声明）
├── contracts/test_port_contract_white_label_report.py      ★ 新建（Task 7；三处既有版本断言更新）
├── contracts/test_port_contract_consultant_view.py         ▲ 版本拆分+三依赖锚（Task 6——6-10 文件[R1 勘误补列]）
└── acceptance/
    ├── test_acceptance_white_label_report.feature/.py      ★ 新建（Task 0/9，R6 模板）
    └── test_acceptance_consultant_view.py                  ▲ S3 skip 门+提示行断言更新（Task 6——6-10 文件）

_bmad-output/implementation-artifacts/deferred-work.md      ▲ 13 条处置注记（Task 0.7/9.4）
docs/architecture/sisys-uni-exception-design.md             ▲ §3.3.2 编码分配表 494/495（Task 1）
```

（▲ 修改 / ★ 新建 / 禁整文件覆盖——就地扩展纪律）

### 关键代码锚点（实现直读——主会话亲验 2026-11-08+四 Agent 调研交叉；行号基准 HEAD@9258b36d，实施前 Task 0.8 复核为准——并行会话提交会使行号漂移）

| 锚点 | 位置 | 说明 |
|---|---|---|
| epics Story 6.11 定义 | `_bmad-output/planning-artifacts/epics_v1.0.md:2518-2561` | AC 三要素/性能三项/测试文件名钦定源（L2021/L2036 依赖行；L600/L714 Epic 20 边界） |
| PdfRendererPort 单参 | `src/application/ports/pdf_report.py:96-105` | `render(document) -> bytes`——v1.1.0 品牌参扩展点（docstring :92-94 单参纯渲染注记） |
| PdfReportGenerationServicePort | `src/application/ports/pdf_report.py:108-133` | `generate_pdf_report(plan_id)`——v1.1.0 brand_template_name 扩展点 |
| PDF 对象键/WORM | `src/application/ports/pdf_report.py:76-82` | EVIDENCE_BUCKET_TYPE/PDF_OBJECT_KEY_TEMPLATE/APPENDIX_C_TITLE——白标导出零变化复用 |
| 渲染器字体锚 | `src/infrastructure/reporting/reportlab_pdf_renderer.py:60`（`_FONT_NAME="STSong-Light"`）+:109-117（`_ensure_font` 幂等注册） | TTFont 注册扩展位（字典化标志）；stsong 预设值单源 |
| 渲染器四硬编码色 | `reportlab_pdf_renderer.py:305/:313/:374/:375` | callout 文字 #444444/callout 底 #F2F2F2/表头底 #E8E8E8/网格线 #BBBBBB——五色键参数化改造点（+title_color 新能力；四色在 `_build_block`[:305/:313] 与 `_build_table`[:374/:375] 内联字面量，`_style` overrides 通道够不到——三套五色与默认四色互斥性已数学验证[最小差 1/255]） |
| 渲染器 _style base | `reportlab_pdf_renderer.py:390-402` | fontName 恒 STSong-Light 全程纪律——参数化改造点 |
| platypus 导入区 | `reportlab_pdf_renderer.py:41-48` | 无 Image/ImageReader——首启导入位 |
| 六段编排调用点 | `src/application/services/pdf_report_generation_service.py:154-229`（render 单实参 :185/L4 :189-198/metadata :218-220） | v1.1.0 品牌编排扩展位（现状九依赖+两配置参数 :108-122——v1.1.0 增第十依赖） |
| citations 条目七键先例 | `pdf_report_generation_service.py:416-427`（`_citation_to_dict`+组装 :218-220） | 引文条目七键[index/document_id/chunk_id/filename/page/status/stage]+顶层 citation 族键 :215-222——JSONB 嵌套/顶层自由扩展双先例（顶层键基数不定——品牌两键直接追加） |
| BrandSection 对接锚 | `src/application/ports/consultant_view.py:120-135`（+常量 :27-34+值域 :41-46） | v1.1.0 值语义演进位；三处 docstring 触发器注记勘误位（Task 6.1） |
| 品牌段恒默认态实现 | `src/application/services/consultant_view_service.py:173-186` | `_build_brand_section` 改读配置位（第三依赖注入） |
| CLI report-generate | `src/entrypoints/agent_cli.py:342-360`（注释 :338-341）+异步壳 :1027-1043+五步定式 :1143-1185+分发 :2446-2447 | --brand-template 扩展位（e431427c 四处增量先例）；打印 :1108-1140 format 感知分支 |
| CLI 提示行 | `agent_cli.py:1806`（6-11 归属提示）/:1820（导出提示——不动） | Task 6.2 更新位 |
| CLI 17 命令族 | `agent_cli.py`（add_parser 17 处——consultant-view :585 三视图族注册尾位[第三位]、族内唯一零参数命令[:583 亲注；注册尾位是 isolation-logs :631]） | 新命令注册位 ：631 isolation-logs 块后邻位 |
| 成组约束先例 | `agent_cli.py:1874-1925`（`_parse_correction_group` 函数体）+:2026-2032（守卫调用点——DomainError stderr `[code]` exit 1 呈现块） | 组合守卫（--brand-template+markdown）直系样板（双锚点） |
| 写命令五步定式 | `agent_cli.py:1188+`（checkpoint-create）/:1984-2097（checkpoint-recover） | UUID 守卫先于 bootstrap→_ensure_bootstrapped :101-112→resolve→asyncio.run→DomainError `[code]` stderr exit 1 |
| 组合根 6-5b 注册块 | `src/composition_root.py:3600-3692`（pdf_renderer :3646 类直传/service :3656 九依赖/use_case :3681） | 4 新注册块落位（块尾邻位）+pdf 系版本升级位 |
| 组合根 6-10 注册块 | `composition_root.py:2141-2177`（两 SCOPED 无混态注记 :2142-2146） | consultant_view_service v1.1.0 三依赖升级位 |
| 版本演进先例 | `composition_root.py:1555-1574`（agent_engine v1.1.0 单行变更）/:1844-1861（hybrid_search_service compatibility 元组） | 三处升级直系样板 |
| report_repository 注册 | `composition_root.py:3550-3559`（SCOPED+session_factory） | brand_template_repository 注册直系样板 |
| L4ObjectPort | `src/domain/ports/l4_object.py:32-51`（store file_path 流式）/:53-68（retrieve）/:107-124（archive WORM） | logo 走 store 非 archive（OD-3）；retrieve 聚合 bytes 归服务 |
| L4 桶命名 | `src/infrastructure/storage/minio/minio_repository.py:253-261`（`{prefix}-{bucket_type}-{tenant_id}`） | brand-assets 新桶物理名；resolve 通道 tenant 段恒 default——共享桶+对象键隔离（测试自愈建桶勿带 object_lock——6-5b 验收 :546-570 探测+建桶先例） |
| 017 migration 范本 | `deploy/postgresql/alembic/versions/017_strategic_reports.py:21-47` | 018 直系范本（revision 链 018→017） |
| ReportModel 范本 | `src/infrastructure/storage/postgresql/models/report.py:20-36` | BrandTemplateModel 直系（Base 自 models/outbox.py） |
| 仓储双模式范本 | `src/infrastructure/storage/postgresql/repository/report_repository.py:103-139`（ContextVar 优先/session_factory fallback/_persist 纯 INSERT） | brand 仓储直系+UPSERT 扩展位 |
| ReportRepositoryProtocol | `src/domain/ports/report_repository.py:23/:38` | 三方法 Protocol 设计参照 |
| dictionary 全链先例 | `src/domain/ports/domain_dictionary.py:123-129`+models/dictionary.py:35-84+repository/domain_dictionary_repository.py:43[pk_column 行]+007 migration | 「配置=PG 表」最完整先例（term 业务键 PK 形态对照——本 Story 取 UUID PK+name UNIQUE 混合） |
| documents 双写先例 | `src/application/services/document_upload_service.py:145-153`（metadata["storage_object_key"]=object_key :151） | PG 行持 MinIO 键双写同构 |
| exception 码段 | `src/domain/exceptions/_code_ranges.py:199-212`（report 行 490-499；494-499 预留 :210）+report_exceptions.py:35/:67/:111/:144（490-493 类定义） | 494/495 开码位+8 项族测试义务 |
| ReportGenerated 事件 | `src/domain/events/workflow_events.py:57-72`（report_type 自由 str） | 复用零改动亲验 |
| 冻结计数三处 | `tests/contracts/test_event_channel_mapping_report.py:25`/`test_event_channel_mapping_pdf_report.py:24`/`test_event_channel_mapping_checkpoint_recovery.py:75` | `_FROZEN_EVENT_COUNT=56` 守护复跑位 |
| 6-10 验收 S3 断言 | `tests/acceptance/test_acceptance_consultant_view.py:775-782`（configured is False+注释 :778 预期演进信号） | Task 6.4 skip 门更新位 |
| 6-10 验收预置样板 | `test_acceptance_consultant_view.py:301-335`（`_save_archive_row` repo.save 直写）+:417-429（teardown rowcount 断言） | 模板行预置/清理直系样板 |
| 验收 CLI 直调样板 | `test_acceptance_consultant_view.py:457-476`（三清+main(argv)+SystemExit 捕获——红形态 exit 2→exit_code 断言 AssertionError :470 行内注释亲注） | 三命令直调直系（写命令：checkpoint_recovery.py :1301/:1542 先例） |
| P95 采样样板 | `test_acceptance_consultant_view.py:89-90/:1087-1099`（20 轮 sorted 公式）+`test_acceptance_pdf_report.py:102-103`（60s 口径） | 双性能段直系 |
| 契约测试样板 | `tests/contracts/test_port_contract_consultant_view.py`（五断言族 :21-89——版本断言 :30-33 两名循环，升级时拆分） | 本 Story 契约测试直系+版本断言扩展 |
| 架构验证样板 | `tests/unit/architecture/test_consultant_view.py`（四验证器 :56-200） | 直系+验证器 C 白名单变体（6-8 先例） |
| R6 钦定模板 | `tests/acceptance/test_acceptance_postgresql_relational_layer.feature`（243 行）/.py（863 行） | AC 横幅+@scenario 双行字面量+三件套形态 |
| UX 旅程 8（Web 边界） | `ux-design-specification.md:2100-2131`（品牌配置旅程九阶段）+:785-821（BrandConfig 架构） | Web 面不做边界注记援引 |
| REST 白标规划位 | `docs/architecture/interface-design.md:1484-1489`（§8.2.8 /reports/whitelabel+/reports/regulatory） | Epic 20 Story 20.4 边界援引 |
| deferred-work 锚位 | `_bmad-output/implementation-artifacts/deferred-work.md`：L129（六轮+分支消费）+L13/L17/L107/L117+L170/L127/L369/L370/L395+L396/L402+L403/L409 | 13 条处置原文位（Task 0.7——行号主会话亲验 2026-11-08） |
| MVP 单租户先例 | `src/application/ports/pdf_report.py:54-58`（tenant_id 构造参数 docstring） | 品牌面单租户注记援引 |

### 锚定义务清单（deferred-work 台账——Task 0.7 逐条处置）

| # | 台账锚位（deferred-work.md） | 留项内容 | 6-11 处置（Task 0 落档） |
|---|---|---|---|
| 1 | L129（orchestration_service/data_pipeline 轨） | 再锚定=批量报告管线需求（**6-11 白标多用户场景**或 Epic 7 API 入口立项——五轮维持注记在档） | **六轮处置+6-11 分支消费**（OD-8）：本 Story 裁定白标导出=单 plan 单次生成归 report-generate 既有入口（第六轮同构收窄——无 DAG 编排需求）；**「6-11 白标多用户场景」触发分支已消费注销**——再锚定条件收敛为「Epic 7 API 入口立项」；orchestration_service 废弃定夺随 Epic 7 同批；注记落档 |
| 2 | L13（灰度推进/per-version 统计视图） | 触发=产品立项 | **第四轮同构不触发，锚位维持**（OD-8——R1 轮次勘误：台账现有 6-1/6-9/6-10 三条注记）：品牌配置面非工具版本统计面（零 skill 依赖——6-10 更远）；注记落档 |
| 3 | L17（langgraph retry/timeout 字段） | 触发=checkpoint_table/图引擎字段消费方 | **第八轮同构不触发，锚位顺延**（OD-8）：品牌配置+渲染面零图引擎/零 checkpoint_table 消费；注记落档 |
| 4 | L107（B2 事件驱动摄取+持续数据供给） | 触发=Epic 6 首个 Skills 消费场景定型 | **不触发**（OD-8）：本 Story 零 Skills 消费（无 skill_selector 依赖）；锚位不变；注记落档 |
| 5 | L117/L170（RabbitMQ 消费侧零接线+事件消费基建） | 触发=首个消费方 Story | **顺延 Epic 8**（OD-8）：零事件零订阅第十连（配置面+导出面均生产侧零新增）；注记落档 |
| 6 | L127（unified_storage+L0/memory 12 端口休眠） | 触发=Epic 6（多轮顺延） | **第五轮同构不触发，锚位顺延**（OD-8——R1 轮次勘误：台账现有 6-1/6-3/6-9/6-10 四条注记）：品牌面零记忆消费（logo 走 L4 既有激活端口非休眠族）；注记落档 |
| 7 | L369/L370（6.5a-DF1 REST 导出面/DF2 L0 撕裂） | 触发=Epic 7 API 入口立项 | **顺延 Epic 7**（OD-8）：CLI-only 第十连——触发条件不含本 Story；注记落档 |
| 8 | L395/L396（6.7-DF1 句级引文/DF2 bbox 四元组） | 锚位 Epic 21/22 | **锚位维持 Epic 21/22**（OD-8）：CLI-only 无 Web 高亮面；**L396 末尾「渲染归 6-11」注记本 Story 兑现核对**——PdfRendererPort v1.1.0 品牌扩展落地（位图/引文高亮仍归 Web 面）；注记落档 |
| 9 | L402/L403（D6-8-R1-1 CLI .env 加载/R1-2 json_chain S 编号） | 触发=CLI 入口标准化/下次触及 | **非 6-11 修复面维持**（OD-8 第四连）：新增命令沿用既有 agent_cli 入口形态；json_chain 文件零触碰；注记落档 |
| 10 | L409（D6-9-R1-1 CLI `*--plan-id` 命令族非 canonical UUID 观察项） | 触发=CLI 输入标准化专项或 7-2 REST 契约 | **注记追加**（OD-8）：report-generate 经台账「等」字+同款宽松 UUID 守卫[:1159-1160]归族[台账原文点名面为 *-view/trace-tree——注记措辞引「等」字依据，不写台账点名]（--plan-id 既有面不变）；brand-template-save 含 --name/--logo-path 非 UUID 参数形态（零 --plan-id 面——不入观察项波及面）；锚位不变；注记落档 |
| 11 | （6-10 Task 0.7 第 11 行对接锚） | BrandSection.configured 是 VO 契约面非台账留项——6-11 经端口 v1.1.0 承载 | **本 Story 兑现**（OD-11）：consultant_view_service v1.1.0 读配置面落地——对接锚闭环（零新登记：兑现注记落 6-10 docstring 勘误） |
| 12 | （6-5b OD-9 位图移交——story 文件面非台账） | 位图渲染归 6-11（reportlab Image 届时启用） | **本 Story 兑现**（OD-1）：platypus.Image 首启（logo 绘制）；**台账零登记确认**（6-5b story done 存档不改——移交注记在 story 文件，本 Story 落地即闭环）；注记落档 |
| 13 | （新增观察面候选登记评估） | TTF 字体资产分发面（仓内二进制+许可合规） | **登记评估**（OD-4）：字体资产 sha256+OFL 许可 docstring 登记（资产验证义务 Task 3.2）；若实施中发现资产获取/许可面问题→登记新锚；否则「验证通过+登记在渲染器 docstring」注记落档 |

### 前一个故事学习经验 Lessons Learned from Previous Story

**来源:** [Story 6-10 顾问视图](./6-10-consultant-view.md)（五轮代码审查收敛 done v1.6.0——2026-11-08）+ 6-5b（PDF 渲染链——本 Story 渲染扩展直系）+ 6-5a（PG 仓储+migration 全层先例）

**关键学习/Key Learnings:**
- **Agent 误报主会话复核**（六连教训）：调研结论关键锚点主会话亲验后方可入 Story——本 Story 已亲验 20 组关键事实（epics 六行原文/PdfRendererPort 单参 :96+调用点 :185/渲染器四色 :305-:375+_style :390+platypus 无 Image/17 命令族+五步定式+成组约束 :2026-2032/组合根 6-5b 三块+6-10 双块+版本演进三先例行号/BrandSection :120-135+BRAND_* :27-34+LATEST_REPORT_TYPE_DOMAIN :46/6-10 S3 断言 :775-782+CLI 提示行 :1806/:1820/L4 端口六方法+桶命名三段式/017 migration+ReportModel+仓储双模式/dictionary 全链+documents 双写 :151/494-499 六码全空+三处冻结计数/deferred-work 13 锚行号+L129 六轮注记原文/Epic 20-22 边界[20.4 三行定义+21/22 零品牌 Story]/UX 旅程 8 全 Web 口径/仓内零 TTF 零 TTFont 注册/citations 条目七键 :416-427+顶层 citation 族键 :215-222/MVP_TENANT_ID :54-58）
- **渲染链纯函数纪律**（6-5b 直系）：渲染器单参纯渲染（logo 读取归应用服务——BrandRenderSpec 传 bytes 保渲染器零 IO）；默认态等价[invariant=1 测试前置下 byte 对照——reportlab 默认态 /ID+CreationDate 非确定源，R1 三重实验实证]是 v1.1.0 演进的向后兼容运行面证据
- **端口版本演进先例族**（agent_engine/blm_planning_service/hybrid_search_service 三处）：单行 version 变更+lambda 增注入+compatibility 元组——三处升级照抄
- **预期演进信号兑现语义**（6-10 注记直系）：configured 断言红是 6-11 实施的预期信号非 flake——本 Story 更新断言形态（skip 门+零模板前提）而非删除
- **共享库背景行防御**（6-10 OD-13 四件套直系+品牌面特化）：TestTenant 前缀+同组串行+teardown rowcount 断言+skip 门兜底四层防御
- **实施攻坚预防**（6-9/6-10 五项教训延续）：注释措辞纪律（新块禁 --format/--plan-id 字样+getsource 切块三注记[8 空格缩进标记/两新块注释互相覆盖/现有断言块不受影响]）/BDD 步骤文本重复绑定合并自足/延迟 import 硬纪律/CLI 直调三清+禁二次 bootstrap/ruff format 提交前亲验
- **性能口径差声明**（七连纪律）：三段口径（保存 200ms/导出 60s 继承/准确率结构化）逐段 OD+docstring 承载

**应用到本故事/Applied to This Story:**
- [ ] 20 组关键锚点主会话亲验（创建期已执行——锚点表承载）
- [ ] 渲染器纯函数+默认态等价回归（Task 3 循环 C——invariant=1 测试前置）
- [ ] 三处端口版本演进照抄先例（Task 5）
- [ ] 6-10 断言预期演进兑现六项清单（Task 6）
- [ ] 共享库四层防御（TestTenant/同组/rowcount/skip 门——Task 0.5/8）
- [ ] 实施攻坚五项预防（Task 5 注释纪律+切块三注记/BDD 绑定/延迟 import/三清/ruff format）
- [ ] 性能三段口径差声明（OD-8+验收/集成 docstring）
- [ ] 全程禁抑制注释+提交信息禁 AI 署名+三红线 grep

### 其他约束速查

- **风险集中登记**：①口径风险=预设常量 hex/字体预设映射（Task 0.2 冻结表唯一版本+值级断言防漂移）；②契约风险=BrandRenderSpec 7 键+实体 7 字段（Task 0.1 冻结——实现禁增删键；**构造契约：五色键+font_name 必填+logo 默认 None**——防默认值与渲染器默认参数同值致等价突变锚失效）+**默认态等价**（Task 3 循环 C——invariant=1 测试前置 byte 对照；v1.1.0 演进的兼容红线）；③**字体资产风险（本 Story 最大技术风险）**=reportlab TTFont 对 OTF/CFF 不支持——**钦定官方 variable TTF（TrueType glyf——NotoSansSC[wght].ttf 默认实例 Regular，google/fonts 无静态单字重 TTF 分发）或 fontTools instancer 静态实例化**+registerFont 成功+中文渲染正常双验证（Task 3.2 双验证义务恰好覆盖 variable 载入风险；资产获取失败时备选：思源黑体 TTF 转换版[同 OFL]——sha256 登记义务不变；入仓体积 ~17MB 注记）；④联动风险=6-10 三文件回归面（Task 6 六项清单逐项+整体复跑）；⑤共享库风险=品牌段全局查询背景行（OD-13 四层防御+S4 skip 门）；⑥清理风险=PG 行+L4 对象双资产定向清理（rowcount+对象键登记）+brand-assets 桶自愈建桶（勿带 object_lock）；⑦装配风险=4 新注册+3 升级行号漂移（Task 0.8 复核——lambda resolve 以 grep 为准）；⑧口径风险=epics L2549「集成测试覆盖率≥75%」以基础设施层 ≥75% 门禁承载（仓覆盖率门禁无集成维——口径差声明：映射理由=集成测试覆盖的实现在 infrastructure 层）
- **三条红线**：禁 `raise ValueError` / 手动 HTTPException / 继承内置 Exception（提交前三条 grep 自查零输出）；禁 noqa/type: ignore/pylint disable；提交信息禁 AI 署名
- **覆盖率**：整体 ≥80%（基线 93%）/ application ≥85%（主改动层）/ domain ≥90% 维持 / infrastructure ≥75%（新增仓储+渲染分支）/ 新增文件 ≥95%
- **验收零 mock 全真实**（pytest.skip() 动态跳过；真实服务三通道——PG 模板行+MinIO logo/PDF 对象+真实渲染；异常路径 CLI 真实触发[494 真抛]；段级异常容错归单测 AsyncMock——验收面无故障注入通道第四连）
- **运行命令**：`SISYS_USE_TEST_PORTS=1 poetry run pytest tests/unit tests/integration tests/contracts tests/acceptance`（显式四目录，裸 `tests/` 挂起）

---

## 🤖 开发代理记录 Dev Agent Record

### 使用模型 Agent Model Used

| 配置项 | 值 |
|--------|-----|
| **Model** | Claude Code（create-story：GLM 调度） |
| **Version** | create-story workflow（bmad-create-story skill v6.3.0） |
| **Execution Date** | 2026-11-08 |

### 调试日志引用 Debug Log References

| 配置项 | 路径 |
|--------|------|
| **Workflow Config** | `.claude/skills/bmad-create-story/workflow.md` |
| **Template** | `.claude/skills/bmad-create-story/template.md` |
| **Epic 配置** | `_bmad-output/planning-artifacts/epics_v1.0.md`（Story 6.11 定义 L2518-2561；依赖行 L2021/L2036；Epic 20 边界 L232/L600/L714） |
| **架构文档** | `docs/architecture/architecture.md` + `docs/architecture/interface-design.md`（L526 format 先例/L1466 export 归 Epic 7/L1484-1489 白标+监管 REST 规划位） |
| **UX/需求规范** | `_bmad-output/planning-artifacts/prd.md`（FR-SP-16）+ `ux-design-specification.md`（品牌模板系统架构 L785-821/旅程 8 品牌配置 L2100-2131/品牌即价值 L291） |
| **前一个 Story** | `_bmad-output/implementation-artifacts/stories/6-10-consultant-view.md`（v1.6.0 收敛定稿——对接锚与回归面直系）+ `6-5b-pdf-report-citation-index.md`（渲染链直系） |
| **Sprint 状态** | `_bmad-output/implementation-artifacts/sprint-status.yaml` |

### 实现计划与规范冻结 Implementation Plan & Frozen Specs（Task 0——dev-story 实施时落档）

#### Task 0.1 双 VO 键契约冻结表（实现禁增删键）

| VO | 键数 | 键清单（序=字段序） |
|---|---|---|
| `BrandTemplate`（domain 实体） | 7 | template_id: UUID / name: str / color_scheme: str / font_preset: str / logo_object_key: str \| None / created_at: datetime \| None / updated_at: datetime \| None |
| `BrandRenderSpec`（application VO） | 7 | font_name: str / title_color: str / header_bg_color: str / grid_color: str / callout_bg_color: str / callout_text_color: str / logo: bytes \| None |

**构造守卫与构造契约**：BrandTemplate `__post_init__` 抛 242（name 非空且 ≤100/color_scheme、font_preset 非空且 ≤30）；BrandRenderSpec `__post_init__` 抛 242（**五色键** 6 位 hex 格式校验 `^#[0-9A-Fa-f]{6}$`——stdlib re；application VO 抛 242 先例充分[consultant_view.py:66-91 等六文件]）；frozen 双 VO（setattr 抛）。**BrandRenderSpec 构造契约（R1 钦定）**：五色键+font_name **必填**（缺省构造 TypeError）、logo 唯一可选默认 None——必填即判别保证（默认值不得与渲染器默认参数同值是 Task 3.4 等价突变锚的判别前提，必填形态从根上排除同值默认风险）。

#### Task 0.2 预设常量冻结表（hex 逐字钦定——值级断言防漂移）

```python
# COLOR_SCHEME_PRESETS: dict[str, ColorSchemePreset]（3 套——键→呈现名+五色）
"corporate-blue": "商务蓝"  # title #1F4E79 / header_bg #DCE6F1 / grid #9CB4D6 / callout_bg #EEF3FA / callout_text #33517A
"graphite": "石墨灰"        # title #37474F / header_bg #ECEFF1 / grid #B0BEC5 / callout_bg #F5F7F8 / callout_text #455A64
"burgundy": "酒红"          # title #7B1F2B / header_bg #F5E6E8 / grid #C9A0A8 / callout_bg #FAF0F1 / callout_text #6E3B44
# 五色键 = BrandRenderSpec 五色键一一对应（title_color/header_bg_color/grid_color/
# callout_bg_color/callout_text_color）；font_name 不在配色套内[正交分立——由 FONT_PRESETS 供给]；
# 三套五色与渲染器默认四色（#444444/#F2F2F2/#E8E8E8/#BBBBBB）逐对互斥已数学验证[最小差 1/255 可判别]
#
# FONT_PRESETS: dict[str, FontPreset]（2 项）
"stsong": "STSong-Light（内置宋体）"       # CID 名直用零注册（_FONT_NAME :60 同值）
"noto-sans-sc": "Noto Sans SC（黑体）"     # TTF 注册名 "NotoSansSC"——资产 sha256 实施时登记
#
# 呈现名映射：预设键→中文呈现（CLI 输出与 BrandSection status 共用单源）
```

（hex 钦定值实施时若与视觉评审冲突可整表替换——**替换必须同步冻结表+值级断言**，禁散改单值。）

#### Task 0.3 端口契约与表结构冻结

- `BrandTemplateRepositoryProtocol`（domain）：`save(template: BrandTemplate) -> BrandTemplate` / `get_by_name(name: str) -> BrandTemplate | None` / `list_templates() -> list[BrandTemplate]`（**updated_at 降序**+name 字典序 tie-break——UPSERT 修订语义[AC-1 修订不动 created_at，created_at 排序与「最新修订优先」互斥——R1 裁定]）
- `BrandTemplateServicePort`（application）：`save_brand_template(*, name, color_scheme, font_preset, logo_path: str | None = None) -> BrandTemplate` / `list_brand_templates() -> tuple[BrandTemplate, ...]` / `get_render_spec(template_name: str) -> BrandRenderSpec`
- `PdfRendererPort.render(self, document, *, brand: BrandRenderSpec | None = None) -> bytes`（v1.1.0）
- `PdfReportGenerationServicePort.generate_pdf_report(self, plan_id, *, brand_template_name: str | None = None) -> StrategicReport`（v1.1.0）
- 018 DDL：`brand_templates(template_id UUID PK, name VARCHAR(100) UNIQUE NOT NULL, color_scheme VARCHAR(30) NOT NULL, font_preset VARCHAR(30) NOT NULL, logo_object_key VARCHAR(500) NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())`（server_default 仅 INSERT 初值——UPDATE 分支 updated_at 由服务侧构造实体显式定值[OD-12 应用侧定时戳]）
- 组合根注册名×4（brand_template_repository[SCOPED]/brand_template_service/save_brand_template_use_case/list_brand_templates_use_case[SINGLETON×3]）+升级×3（pdf_renderer/pdf_report_generation_service/consultant_view_service → v1.1.0+compatibility）

#### Task 0.6 逐场景红锚符号表

| 场景 | 预期红形态（Task 0 时点） |
|---|---|
| S1/S3/S4（CLI 直调无预置） | brand-template-save/list 命令未注册 → argparse invalid choice **exit 2** → SystemExit 捕获 → exit_code 断言 AssertionError（6-10 :470 行内注释亲注先例[helper :457-476]——**非 ImportError**） |
| S2/S5/S6/S7/S10~S13（含预置/服务类延迟 import） | 步骤函数内延迟 import `ImportError: No module named 'src.domain.entities.brand_template'` 族（Given 预置 helper 或服务类 import 先触发） |
| S8（模板不存在）+S9（组合守卫） | report-generate 既有命令+`--brand-template` 未注册 → argparse unrecognized arguments **exit 2**（纯参数面；S8 若 Given 有预置步骤则预置 import 先触发 ImportError——实施时按 Given 设计二择其一并在符号表钉死；**绿形态注记[R3]**：get_render_spec 前置于聚合查询——S8 免 BLM 预置直达 494[message 含模板名]，后置实现则裸 plan 先撞 490 场景结构性红） |
| S14（收尾清单） | `_COMPLETION_SRC_FILES` 文件不存在 AssertionError（6-10 S12 形态直系） |

#### Task 0 实施记录（dev-story 2026-11-08）

- **锚点复核（Subtask 0.8）**：基准 9258b36d → HEAD c6f87227 间 5 笔提交全部 docs-only（story+sprint-status 两文件）——`git diff --name-only` 非 md/yaml 零命中，**代码锚点零漂移**；四视角调研 Agent（渲染链/存储链+组合根/CLI+契约/6-10 联动+验收模板）独立复核一致。
- **TTF 资产钦定落档（Subtask 0.2 补充）**：外网（raw.githubusercontent.com/jsdelivr）连接重置不可达；改用本地官方分发物 `/mnt/c/Windows/Fonts/NotoSansSC-VF.ttf`（Google 官方 Noto Sans SC variable TTF，17,773,244 字节，sfnt 0x00010000 TrueType glyf 非 CFF，SIL OFL 1.1 许可允许再分发嵌入）——**双验证亲测通过**：①`pdfmetrics.registerFont(TTFont("NotoSansSC", path))` 成功；②中文渲染正常（pypdf 提取「战略规划品牌白标测试：石黑茶」完整）；放置 `src/infrastructure/reporting/fonts/NotoSansSC-VF.ttf`，sha256=`763146584cf0710223441356b4395e279021b0806c196614377a7a0174ae074a`（渲染器文件头 docstring 登记义务 Task 3 承载）。fontTools 非项目依赖（pypi 镜像可达但零新依赖纪律）→ instancer 静态实例化路线排除，钦定 variable TTF 直用（默认实例 Regular wght 400）；文件名保留 `-VF` 后缀（诚实标注 variable 形态——S14 清单与渲染器 docstring 同步该名）。
- **红阶段验证（Subtask 0.5 DoD）**：14 场景全红（14 failed in 22s，服务四件全部在位零 skip）；红形态三型实测与符号表吻合——S1 `exit=2 stderr=usage: sisys-agent ... invalid choice: 'brand-template-save'` → exit_code 断言 AssertionError；S2 `ModuleNotFoundError: No module named 'src.application.ports.brand_template'`（Given 延迟 import 触发）；S14 `AssertionError: src 交付件缺失[品牌模板实体]`。
- **Given 设计钉死（符号表 S8 二择+S7 补注）**：S8 Given 设计为零预置（免 BLM 预置——绿形态 get_render_spec 前置直达 494 承载 R3 裁定），红形态=unrecognized arguments exit 2（与 S9 同机理）；S7 Given 钦定「BLM 完成+品牌模板已保存」组合形态（库有模板但未指定品牌导出=默认态——与 S6 对照腿语义互补；红锚由模板预置的 ImportError 触发）；S12 复用 S5 同文本 Given（pytest-bdd 同文本单绑定纪律——重复绑定已排除）。
- **_COMPLETION_TEST_FILES 计数钉死**：16 项（12 新建+4 扩展——扩展含 6-10 三测试文件族与 6-5b pdf 服务单测）。**[R1 代码审查勘误：实交 21 项（12 新建+9 扩展）——漏列 5 个扩展文件：test_generate_pdf_report_use_case/test_reportlab_pdf_renderer/test_port_contract_consultant_view/test_exception_handlers/test_report_exceptions；S14 清单与结构图测试树已同步补列]**
- **deferred-work 处置（Subtask 0.7）**：13 条义务覆盖 14 个物理行全部追加注记落档（L129 六轮+分支消费注销/L13 第四轮/L17 第八轮/L107 不触发/L117+L170 顺延 Epic 8/L127 第五轮/L369+L370 顺延 Epic 7/L395 维持/L396 维持+兑现核对/L402+L403 第四连/L409 注记追加）——行数守恒 409 行。

#### Task 1~9 实施记录（dev-story 2026-11-08）

- **Task 1 领域层**：BrandTemplate 实体（7 字段+242 守卫负例全枚举[frozen/空名/超长/边界恰值]）+BrandTemplateRepositoryProtocol 三方法+494/495 两异常（BusinessException 族：494 七形态伞形[构造器 field 必参+context_extra 合并]、495 layer 二元 {l2,l4}[与 491 {l0,l2} 分立——值域分立双向判别]）+六处注册义务全落（report_exceptions/_code_ranges 注释+_CLASS_TO_SUBDOMAIN/__init__ 导出/HTTP_MAP 494→400+495→500 显式/sisys-uni-exception-design.md §3.3.2/exception_handlers 测试 expected 集合同步）。变异①name 守卫停用→2 红；②494→496 码漂移→2 红。domain 全绿 3806 passed。
- **Task 2 存储面**：018 migration（revision 018→017+UNIQUE(name)[uq_brand_templates_name]+server_default now() 仅 INSERT 初值注记）+BrandTemplateModel（七列镜像+UniqueConstraint）+PostgreSQLBrandTemplateRepository（UPSERT：SELECT by template_id→UPDATE 四字段[三配置+updated_at]/无行 INSERT+IntegrityError→495 包装[UNIQUE 撞+NOT NULL 撞双路径]+双模式 fallback[直调 get_session 防呆纪律]+list 双序 ORDER BY updated_at DESC, name ASC）。dev 库（5432）与测试库（5433）双 stamp 017+upgrade head 应用。真实 PG 12 用例全绿。变异①UPSERT 恒 INSERT→1 红；②主序反转→1 红。
- **Task 3 渲染面**：NotoSansSC-VF.ttf 资产入仓（sha256 登记+OFL 许可+来源注记在渲染器文件头）+BrandRenderSpec 7 键 VO（hex 242 守卫+必填构造契约）+render v1.1.0 keyword-only brand 参+渲染器三件（_FONT_REGISTERED 字典化+TTFont 注册通道[_TTF_FONT_FILES 映射]+五色参数化[_brand_color_or 默认回落]+platypus.Image logo[等比缩放宽≤40mm，BytesIO 传参——ImageReader 直传走文件名分支 TypeError 实证修正]）。:282 monkeypatch carve out 机械适配（False→{}）。默认态等价（invariant=1 byte 对照）绿+6-5b 渲染测试零修改复跑绿。变异四锚全红（fontName 参数化删/表头色恒原值/logo 流删/等价断言侧注入 spec）。
- **Task 4 应用层**：预设常量（3 套×5 色+2 字体+呈现名单源 in ports/brand_template.py）+BrandTemplateService（save 编排钦定序[get_by_name→值域+name 预检→logo 校验→L4 store→构造→repo.save]+校验矩阵七格+get_render_spec[脏键 494 防御包装]+list tuple 化）+PdfReportGenerationService v1.1.0（第十依赖 brand_template_service 可选尾参+品牌前置小步[R3 钦定前置于聚合查询]+双参渲染[brand None 走单参——既有 side_effect 零破坏]+metadata 两键[template_id 经 list 精确匹配定位——端口三方法冻结的 O(n) 取舍注记]）。变异五锚全红（hex 值/校验顺序/保留语义/metadata 漏写/brand 错传 None）。**[R2 代码审查勘误：Task 4 时点「校验矩阵七格」为实施实况；R1-F6 拓宽像素/解析负例+R1-F3/F17① 补格后终态 13 格（494×10+242×1+成功×2）]**
- **Task 5 CLI+组合根**：双用例（SaveBrandTemplateUseCase 四参 keyword-only/ListBrandTemplatesUseCase 零参）+GeneratePdfReportUseCase execute 增 brand_template_name 透传（None 单参调用——既有用例零修改；注册零改动维持 v1.0.0）+CLI 19 命令族（brand-template-save[choices 三键+两键+--logo-path 可选]/brand-template-list[零参]/report-generate --brand-template[自由名+组合守卫 post-parse 在 UUID 守卫与 bootstrap 前——markdown 组合 494]）+品牌增量打印行+组合根 4 新注册（SCOPED 仓储 session_factory 注入+service SINGLETON[SINGLETON 捕获 SCOPED 注记]+双用例）+2 处升级（pdf_renderer/pdf_report_generation_service v1.1.0+compatibility 元组）。注释措辞纪律（新块零 --format/--plan-id 字样）+切块边界断言绿。组合根冒烟 6 端口版本+resolve 全过。变异三锚（组合守卫删/透传漏传/choices 错改）+变异④版本漏升归 Task 7 补做。
- **Task 6 consultant_view v1.1.0 联动（五件同批原子落位）**：服务增 brand_template_repository 可选尾参第三依赖+_build_brand_section async 化三形态（零模板默认[与 6-10 恒值逐字相等]/有模板派生[configured True+呈现名——呈现名单源引用预设常量]/查询异常降级[degraded True 不抛——零 IO 恒稳承诺勘误]）+ports 三处 docstring 勘误+版本声明 v1.1.0×2+组合根 lambda 三依赖+compatibility+CLI 显示块三值派生改造（「Logo: 默认|配色: 默认」硬编码→BrandSection 派生值）+提示行「执行 brand-template-save 配置品牌模板」+6-10 回归面六项（docstring/提示行/单测三形态/S3 skip 门[品牌模板表零行清点+information_schema 表存在性探测——红阶段容错注记]/CLI 断言联动×2 文件/契约拆分[service v1.1.0+use_case v1.0.0+getsource 三依赖锚]）。变异：三依赖漏注入→契约 2 红。6-10 验收 12 passed+6-10 单测全绿。
- **Task 7 契约守护**：test_port_contract_white_label_report.py 九用例五断言族（4 新注册 spec 元数据+interface is 具体类+lambda getsource 注入链+resolve isinstance+方法签名[save 四参 keyword-only 恰形态]）+三处版本升级等值断言（v1.1.0+compatibility——pdf 系两处落新文件钉死）+pdf_use_case 注册零改动 v1.0.0+pdf 服务 lambda 十依赖锚。事件冻结：三处 56 计数复跑+event_channels.yaml/events 零 diff git 证据。变异④补做：pdf_renderer 版本改 v1.0.0→契约断言红→还原绿。
- **Task 8 集成五场景**：真实链（独立引擎+共享 default 桶[对象键锚 template_id 定位]+自愈建桶[勿带 object_lock]+多行预置显式 updated_at[单 now 基准+微秒偏移]+teardown 顺序钦定[L4 对象先行 PG 行后行+brand 行 rowcount 断言殿后]）——①保存主链[PG 行七字段+L4 逐字节]②UPSERT 修订[template_id 稳定+updated_at 前进点名断言]③白标导出端到端[metadata 品牌两键+WORM 对象键通道]④品牌准确四件套[字体资源 NotoSansSC+首页 Image XObject+双色 fp_str+对照腿零图像零品牌色]⑤性能双段[保存 20 轮 P95<200ms+导出 20 轮 P95<60s+L2 行数累计 20]。实施攻坚两留痕：pytest-asyncio auto 模式下探测协程化（自建 loop→RuntimeError 双循环冲突）；每测试三清（SINGLETON 缓存绑定旧 loop→InterfaceError——驱逐后 resolve 惰性重建）。变异：use case brand 参丢弃→场景③④双红→还原绿。
- **Task 9 架构+收尾**：四验证器（A 落位[八文件+VO/端口/常量 AST+domain 零第三方+服务/用例白名单方向]/B 零 publish[+DomainEvent 子类全集 AST 比对]/C 白名单形态[三层全量 8 .py 集合等值==双向判别+fonts 目录单列+渲染器三件运行面锚]/D CLI 接线[缩进敏感 add_parser 锚+--brand-template 参数+四注册+三升级块 v1.1.0+compatibility]）。14 验收场景全绿（S1~S13+S14 收尾——S8 补「exit code 为 1」独立步骤绑定）。新增文件覆盖率：service 98%+repo 96%+实体/VO 100%（补异常分支用例：L4 store 495/save 协议外 495/495 透传/三方法无 factory RuntimeError）。四目录全量两轮：第一轮 15452 passed+2 预存抖动[analyst_view Redis 跨循环+checkpoint_snapshot Qdrant 最终一致——均与 6-11 无因果面，隔离复跑+单场景双跑+整文件复跑三重绿定谳]。

### 完成清单 Completion Notes List

- [x] 故事需求从 `epics_v1.0.md` L2518-2561 提取（AC 三要素+性能三项+测试文件名钦定逐行对账）
- [x] 架构约束从 `architecture.md`/`interface-design.md` 提取（六边形矩阵+REST 边界 L1484-1489）
- [x] 前一个故事学习经验整合（6-10 对接锚+6-5b 渲染链双直系）
- [x] 状态设置为 `ready-for-dev`
- [x] SDD+TDD 融合开发要求定义完成（四冻结面[双 VO 键契约含构造契约/预设 3 套×5 色+2 字体/端口+018 DDL/CLI 参数]+14 OD 裁定+14 场景）
- [x] 项目结构对齐统一规范（新建 9+扩展 12+migration 018——白名单形态[R1 代码审查勘误：11→12 补列 interfaces/api/exception_handlers.py]）

### 文件清单 File List

**创建的文件/Created Files（dev-story 实施交付）：**
- `_bmad-output/implementation-artifacts/stories/6-11-white-label-report-basic.md`
- `src/domain/entities/brand_template.py` + `src/domain/ports/brand_template_repository.py` - 实体+R1 端口
- `src/application/ports/brand_template.py` + `src/application/services/brand_template_service.py` - 预设+R2 服务
- `src/application/use_cases/save_brand_template.py` + `list_brand_templates.py` - 双用例
- `src/infrastructure/storage/postgresql/models/brand_template.py` + `repository/brand_template_repository.py` - 存储双件
- `src/infrastructure/reporting/fonts/NotoSansSC-VF.ttf` - 字体资产（variable TTF 直用钦定——sha256=76314658...ae074a，OFL 1.1）
- `deploy/postgresql/alembic/versions/018_brand_templates.py` - migration（dev 5432+测试 5433 双库已应用）
- unit 7 个新测试文件：`tests/unit/domain/entities/test_brand_template.py` + `tests/unit/infrastructure/storage/test_brand_template_repository.py` + `tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer_brand.py` + `tests/unit/application/test_brand_template_presets.py` + `test_brand_template_service.py` + `tests/unit/application/use_cases/test_save_brand_template.py` + `test_list_brand_templates.py`
- unit/architecture 1+integration 1+contracts 1+acceptance 2：`tests/unit/architecture/test_white_label_report.py` + `tests/integration/test_integration_white_label_report.py` + `tests/contracts/test_port_contract_white_label_report.py` + `tests/acceptance/test_acceptance_white_label_report.feature/.py`（合计 **12 个测试新文件**）

**修改的文件/Modified Files（src 扩展 12+6-10/6-5b 测试文件+文档台账——[R1 代码审查勘误：11→12 补列 exception_handlers.py；测试扩展实为 9 文件]）：**
- `src/domain/exceptions/report_exceptions.py`+`_code_ranges.py`+`__init__.py` - 494/495
- `src/application/use_cases/generate_pdf_report.py` - execute 增 brand_template_name 透传（None 单参调用零破坏）
- `src/application/ports/pdf_report.py`+`services/pdf_report_generation_service.py` - v1.1.0 双演进（BrandRenderSpec+render 双参+品牌前置小步+metadata 两键）
- `src/application/ports/consultant_view.py`+`services/consultant_view_service.py` - v1.1.0 联动（三处 docstring 勘误+三依赖+品牌段三形态）
- `src/infrastructure/reporting/reportlab_pdf_renderer.py` - 品牌三件（TTFont 通道+五色参数化+platypus.Image+哨兵字典化+字体资产 docstring 登记）
- `src/interfaces/api/exception_handlers.py` - HTTP_MAP 494→400+495→500 两行（AC-7 注册义务——[R1 勘误补列]）
- `src/entrypoints/agent_cli.py`+`src/composition_root.py` - CLI 两新命令+--brand-template 扩展+组合守卫+4 新注册+3 处 v1.1.0 升级
- 6-10 测试文件：`tests/unit/application/test_consultant_view_service.py`（三形态+第三依赖工厂）+`tests/acceptance/test_acceptance_consultant_view.py`（S3 skip 门+提示行/显示块断言联动）
- 6-5b 测试文件：`tests/unit/infrastructure/reporting/test_reportlab_pdf_renderer.py`（:282 monkeypatch carve out 一行机械适配）+`tests/unit/application/test_pdf_report_generation_service.py`（品牌编排四用例扩展）+`tests/unit/application/use_cases/test_generate_pdf_report_use_case.py`（品牌透传三用例）
- `tests/unit/domain/exceptions/test_report_exceptions.py`（494/495 八项族承载——[R1 勘误补列]）
- `tests/unit/interfaces/cli/test_agent_cli.py`（三命令段扩展+6-10 显示块断言联动）+`tests/contracts/test_port_contract_consultant_view.py`（版本拆分+三依赖锚）+`tests/unit/interfaces/api/test_exception_handlers.py`（HTTP_MAP expected 集合同步）
- `_bmad-output/implementation-artifacts/deferred-work.md`+`docs/architecture/sisys-uni-exception-design.md` - 台账 14 行处置注记与 §3.3.2 编码表

---

## 📊 故事详情 Story Details

| 配置项 | 值 |
|--------|-----|
| **Story ID** | 6.11 |
| **Story Key** | 6-11-white-label-report-basic |
| **File** | `_bmad-output/implementation-artifacts/stories/6-11-white-label-report-basic.md` |
| **Status** | `backlog` → `ready-for-dev` → `in-progress` → `done` |
| **Epic** | Epic 6: 战略规划流程（BLM 前两阶段） |
| **价值组** | 战略规划与审批能力（白标交付面收口） |
| **优先级** | P0-11（MVP，UX 白标报告） |
| **覆盖 FR** | 无独立 FR（FR-SP-16 REST 面归 Epic 20 Story 20.4——第六连形态） |

### 完成总结 Completion Summary

1. [x] All tasks defined 所有任务定义完成（Task 0~9——十任务全链）
2. [x] All acceptance criteria specified 所有验收标准已定义（AC-1~AC-8+14 场景）
3. [x] Architecture constraints extracted 架构约束已提取（六边形矩阵+白名单形态+依赖方向特有落位）
4. [x] Previous story learnings integrated 前一个故事学习经验已整合（6-10 对接锚+6-5b 渲染链）
5. [x] Sprint status synced to `ready-for-dev`

### 🔧 文档审查修复 Docs Review Fixes [文档审查/修订必选]

> 如果本 Story 经过 `bmad-review-adversarial-general` 审查，在此记录所有对故事文件的修复项。

| # | 问题 | 严重度 | 修复方案 |
|---|------|--------|----------|
| 1 | byte 等价断言在 reportlab 默认配置下绿不可达（trailer /ID 每次渲染含 time.time() 种子随机+CreationDate 秒粒度漂移——同 document 双渲染结构性不等；主会话+双 Agent 三重实验实证） | P0 | AC-4/Task 3 循环 C 增测试前置 `rl_config.invariant=1`（fixture setup/teardown——reproducible builds 业界标准做法，生产路径日期语义零触碰）；连带 S7 断言形态钉死+循环 C 绿归因修正+突变锚 3.4 前提注记——12 处出现位全修 |
| 2 | 「六色」术语链与冻结表矛盾：BrandRenderSpec 实为 5 色键+font_name 正交，冻结表每套仅钦定 5 hex，「(+第 6 色见下)」悬空引用，值级断言「每套 6 色」与冻结表对不上 | P1 | 全文 12 处统一「五色键+font_name 正交分立」；删悬空引用；补互斥性数学验证注记 |
| 3 | 「metadata 七键→九键」前提错误：七键是 citations 条目键（:416-427 `_citation_to_dict`），顶层键=聚合基底+citation 族键基数不定——「九键」断言无法落笔 | P1 | 9 处统一改「顶层自由扩展两键」（AC-4 验证标准既有正确口径为单源）；锚点表改「citations 条目七键先例」正确语义 |
| 4 | save 编排顺序矛盾：L4 键锚 template_id 要求 get_by_name 先于 L4 store，Task 4 红/绿文字顺序相反；仓储收到 logo_object_key=None 无法区分「保留/无 logo」——保留语义承载位悬空 | P1 | 钦定服务侧单源编排：get_by_name 先行→校验→L4 store→构造（保留语义构造时承载）→repo.save 纯落库；Mock await 序锚钉死 get_by_name→store→save；AC-1/AC-2/Task 2B/Task 4/OD-12 五处同步 |
| 5 | 排序语义矛盾：UPSERT 修订不动 created_at，「最新修订优先」与 created_at 降序互斥；「与 6-10 一致」援引反证（6-10 实为 latest_activity_at） | P1 | 排序键统一 updated_at 降序+name 字典序 tie-break（六处出现位）；AC-6 品牌段「最新行」同键 |
| 6 | AC-5 字体断言在 stsong 预设下结构性恒真（渲染器默认字体即 STSong-Light，品牌/对照腿同真判别力为零）——Epic 4「8/13 恒真断言」教训复发形态 | P1 | S6 钦定 font_preset=noto-sans-sc；AC-5 改「仅 TTF 形态承载断言+CID 形态由传递链单测承载」 |
| 7 | S2 值域守卫经 CLI 直调不可达：argparse choices 硬拦截 exit 2，494 永不触达 | P1 | S2 钦定编程面 use case 直调；AC-7/OD-7/Subtask 0.4 补注记 |
| 8 | brand-assets 桶创建前置缺失：store 对缺桶抛 NoSuchBucket 且 src 零生产建桶，全文零建桶步骤 | P1 | AC-2/Task 0.5/Task 8/隔离表/OD-3⑦ 补「bucket_exists 探测+make_bucket 自愈且勿带 object_lock」（6-5b 验收先例） |
| 9 | consultant_view 契约测试版本断言循环覆盖 service+use_case 两名——机械改断言值致 use_case 假红 | P1 | 端口节/Task 5/Task 6.6/7.2 补拆分义务（service v1.1.0/use_case 维持 v1.0.0）；7.2 修正「必须更新仅一处」+pdf 契约 startswith 事实 |
| 10 | 「TestTenant 物理桶隔离 test-{uuid}」与 resolve 通道现实错位（组合根未传 tenant_id——物理桶恒共享 default） | P2 | 钦定共享桶+对象键级清理形态（AC-2/隔离表/Task 8/OD-3/锚点表六处） |
| 11 | Task 9.2 `_COMPLETION_SRC_FILES`「新建 9+扩展 7」三种口径不齐（结构图 ▲9 漏 __init__.py/File List 10） | P2 | 统一「新建 9+扩展 10」；结构图补 __init__.py ▲ 行（R3 追记：#26 use case 补位后再统一为「新建 9+扩展 11」——本行口径已被 #26 演化取代） |
| 12 | 14 vs 13 场景计数漂移（Task 9 内自互斥）+File List「九个测试新文件」实为 12+「三笔移交」实列四项+锚定义务「12 条」vs 表 13 行 | P2 | 统一 14 场景（S1~S13+S14 收尾）/12 测试文件/四笔移交/13 条锚定义务 |
| 13 | 494「七形态」含「模板名非法」与 AC-1/Task 4 的 242 口径冲突 | P2 | 七形态重枚举（color/font key 拆两形态恰 7；name 归 242 注记）——AC-7/OD-6 同步 |
| 14 | getsource 切块边界三细节未注记（8 空格缩进标记依赖/list 前置注释落入 save 块/两新块注释互相覆盖） | P2 | Task 5 重构行+学习经验补「切块机制三注记」 |
| 15 | BrandRenderSpec 默认值未冻结——默认值与渲染器默认参数同值时等价突变锚静默失效 | P2 | Task 0.1 钦定构造契约：五色键+font_name 必填+logo 默认 None（必填即判别） |
| 16 | updated_at 前进实现责任位未钦定（DDL server_default vs 应用侧定时戳混用）+并发 INSERT 撞 UNIQUE 的 IntegrityError 逃逸 | P2 | OD-12 钦定服务侧定时戳+仓储捕 IntegrityError 包装 495；DDL 注记「server_default 仅 INSERT 初值」 |
| 17 | L13「第八轮」/L127「第八轮」与台账注记链不可复现（实为第四轮/第五轮） | P2 | OD-8+锚定义务表轮次勘误（L17 第八轮免修） |
| 18 | 红锚符号表「S1~S8 一刀切 ImportError」与 6-10 先例（exit 2→AssertionError）相悖 | P2 | Task 0.6/Subtask 0.5/两处 DoD 逐场景条件化（CLI 直调/预置/纯参数三形态+S8 二择） |
| 19 | 字体资产「静态版」非官方现成分发物（google/fonts 仅 variable TTF） | P2 | Task 3.2/OD-4/风险③ 改钦定官方 variable TTF 直用或 instancer 静态实例化+体积注记 |
| 20 | 「十依赖」锚点表现状锚混入目标态；OD-6 错引（零事件是 OD-2）；「Checklist 4 项」名实不齐；registry.py 登记表述误导 | P3 | 锚点表两时点标注/L176 改 OD-2/「4 项强制+3 项扩展」/「以 registry.py 机制在 composition_root 登记」 |
| 21 | 「双清」标题词 vs 三函数内容；追溯矩阵漏 S4 行；epics Given「并创建项目」差异未声明；AC-1 验证标准七字段列 5 个；017 无 UNIQUE 先例措辞；pk_column :43；契约 :21-89；consultant-view 尾位措辞；_parse_correction_group 双锚点；L409「等」字依据；HTTP_MAP 495 显式注册机理；「8 项族」自定配额注记；覆盖率口径差声明；Task 2 xdist_group 重申；S4 skip 门；排序突变锚时间戳可区分度；fp_str 精度对齐；retrieve AsyncIterator 形态 | P3 | 逐处措辞修正/补行/补注记（本列合并 18 项 P3——全部 R1 落码清偿，零留项） |
| 22 | **R2-B-1 组合互拆**：「`_FONT_REGISTERED` 单布尔字典化」×「6-5b 既有渲染测试零修改」——既有测试 :282 monkeypatch 布尔字面量 False 在字典化守卫下必抛 TypeError，四处 DoD 级零修改承诺不可满足 | P1 | AC-4/S7/Task 3C/DoD 四处 carve out 显式例外（:282 monkeypatch 值 False→空 dict 一行——哨兵类型变更机械适配，零修改口径=除该行外） |
| 23 | **R2-B-2 组合互拆**：预置直写通道 repo.save 绕过服务定时戳，PG now() 事务开始时间同事务恒值→多行预置 updated_at 全同排序退化；AC-3 列表行序断言在 14 场景无载体（悬空） | P2 | Task 0.5/Task 8 补「多模板行预置显式 updated_at 构造（单 now 基准+微秒偏移——6-10 _preset_anchor :280-292 同款）」；AC-3 criterion1 载体钉位（Task 5 CLI 单测+Task 2 仓储序断言组合承载） |
| 24 | **R2-A-1 传播漏网**：:214 BDD checklist 末行把 S2 值域捆进 CLI stderr exit 1 呈现，与 R1 钦定 S2 编程面直调口径矛盾（argparse choices 先拦 exit 2 场景结构性红） | P2 | :214 改「S3/S8/S9 CLI stderr 呈现；S2 编程面直调 pytest.raises 断 494」 |
| 25 | R2 组合/邻位九项 P3：:465-468 锚错位（实为 :470 行内注释）；「校验矩阵七形态」与 AC-7「七形态」术语碰撞（改七格+口径分立注记）；字体资产文件名单点钉死 vs 渠道二择张力（NotoSansSC[-Regular].ttf 模式）；File List 标题漏 6-10 三测试文件类；「三视图族零参数尾位」歧义（改「注册尾位第三位+族内唯一零参数」）；仓储测试实体构造通则（UPDATE 形态必须自带 updated_at）；updated_at 前进端到端单点承载（场景②点名断言）；AC-7 通道分立注记（494 走 post-parse 守卫位/495 走五步定式）；teardown 顺序钦定（L4 对象先行/PG 行后行防孤儿）；7.2 pdf 系等值断言落新文件钉死 | P3 | 逐处落码清偿（R2 全部 12 项零留项） |
| 26 | **R3-1 `GeneratePdfReportUseCase` 修改四清单缺位**——--brand-template 传递链 CLI→use case→服务的必需中间文件全文失踪（现签名固定 `(*, plan_id)` :35-46 亲验），按清单 verbatim 实施必漏改 | P1 | Task 5 落位行+结构图 ▲+File List（10→11）+S14（19→20）+注册零改动维持 v1.0.0 决策五处补位 |
| 27 | **R3-2 导出侧资产全生命周期双不完整**：BLM 八阶段预置链+轻装配未锚（Task 0.5 仅钉模板行）；~25 次导出的 strategic_reports 行+event_outbox 行+WORM PDF（端口 delete 抛 ComplianceLockError 须 bypass_governance 裸删）+归档三面残留清理零提及 | P2 | Task 0.5 补预置 helper 锚（6-5b :600-758/:309-391 直系）+隔离表补三面清理（`_cleanup_report_rows`/`_cleanup_outbox_rows`/`_cleanup_pdf_objects` bypass 直系） |
| 28 | **R3-3 consultant_view 升级落位双写矛盾**（Task 5 绿行「3 处版本升级含 consultant_view」vs Task 6.6 五件分离——lambda 三依赖先落而服务两参 → resolve TypeError 破坏 6-10 全测试面）+**R3-4 验证器 C 白名单自矛盾**（仅枚举 infra 2+fonts，domain 2+application 4 共 6 文件按「白名单外零 brand 词族新文件」自我误伤必红；比较方向未钉——`<=` 多列静默） | P2 | R3-3：Task 5 改「本批 2 处+consultant_view 升级预告（五件同批原子落 Task 6——R3 裁定）」；R3-4：白名单改三层全量 9 文件+fonts+渲染器单列+集合等值（==）双向判别（Subtask 9.1+OD-14 同步） |
| 29 | R3 六项 P3：name 242 守卫晚于 L4 store（非法 name+logo 形态孤儿对象）→服务前置预检；S8 前置依赖 get_render_spec 调用位→钦定前置于聚合查询（免 BLM 预置直达 494）；渲染正例 Logo 资产须可解码（仓内 PNG 测试字节全是截断假体）→Pillow 生成（零新依赖）；T5 同模板修订跨导出追溯无裁定→OD-5 补 MVP 接受注记（PDF 产物即渲染参数固化载体）；6-10 CLI 品牌显示块 :1800-1804 硬编码「默认」联动后自相矛盾→6.2 补三值派生改造；AC-1 UPSERT 验收面无场景承载→载体声明（Task 2+Task 8②组合承载） | P3 | 六项逐处落码清偿（R3 全部 10 项零留项；另 8 条证伪不成立疑点留痕：S11 排序影响不成立/S6 两色分立正确/S3-skip 互扰不成立/五色互斥抽算通过/stsong 两串分立有意/brand_applied 单键充分/T1-T3 时间线全对/Task 6 依赖闭合） |
| 30 | R5 终审特权发现两项（前四轮全漏）：F-1 白名单计数 9↔8 不符（Subtask 9.1+OD-14 两处——花括号枚举恰 8 个 .py，「9」疑沿用结构图 ★9 口径含 ttf 资产，而资产文件名无 brand 词族应归目录单列）；F-2 File List 段落归类错位（generate_pdf_report.py「execute 增透传」是修改动作却列于待创建段） | P3 | F-1 两处「9 个」→「8 个」+fonts 不入集注记；F-2 移行至待修改段+归类勘误注记——随收敛提交清偿（零留项） |

### 🔍 代码审查发现 Review Findings [代码审查/修正必选]

**审查日期:** 2026-11-09（Round 1——五轮循环第一轮）
**审查模式:** full（盲审对抗 + 边界狩猎 + 验收审计 + 运行面实测四视角并行 + C3 双评审员方案评审）

#### 需决策 Decision Needed

- （无——Round 1 零 decision_needed）

#### 已修复 Patch

- [x] **R1-F1【P1】** 集成测试三保存路径测试缺 `_require_services` 门——未迁移 PG 环境 3 FAILED 假红（A1+A4 双源实证：UndefinedTableError 不含「不可用」子串永不命中兜底 skip）→ 三测试 try 内首句补门（对齐 :666/:711/:807 惯例，兜底保留）；修复后未迁移环境实测 6 skipped [tests/integration/test_integration_white_label_report.py]
- [x] **R1-F2【P2】** 495「PG 读写失败」契约面虚设——读路径永不产生 495 且 CLI 单测 stub 绿证了不可达行为（A1+A2 双源）→ **仓储层单点包装**（`_do_get_by_name`/`_do_list` 协议外异常兜底→495 layer=l2，`except BrandTemplateStorageError: raise` 再抛守卫）——契约三处冻结「读写」+`_persist`「防御义务归仓储」同位+全部消费方单点受益（服务三读位/pdf 品牌块/consultant_view 容错链）；impl+Protocol docstring Raises 同步；包装单测两格（with_session 注入 OperationalError——code/layer/cause 三锚）；C3 裁定：仓储层 vs 服务层四问全支持仓储层 [src/infrastructure/.../brand_template_repository.py + src/domain/ports/brand_template_repository.py]
- [x] **R1-F3【P2】** validate_logo_file getsize/open 无 OSError 守卫——权限不可读形态裸逃「伞形」承诺（A2）→ except OSError → 494「不可读」（真实语义链红在 open 位——stat 只需父目录 +x；chmod-000 主格+geteuid==0 动态 skip+monkeypatch getsize TOCTOU 补充格）[src/application/ports/brand_template.py]
- [x] **R1-F5【P3】** 孤儿 logo 补偿窗口——store 成功后 repo.save 失败新写键永久孤儿（A1+A2 双源）→ **本次新写键 best-effort 补偿 delete**（条件 `object_key != existing_logo_key`——首存/修订无既有 logo 两形态自动覆盖；修订既有键不补偿[删除即丢 PG 行引用的 logo]；补偿失败 logger.warning 不掩盖原始异常——Saga 补偿形态 C3 裁定不违红线）；补偿五格单测（双分支 kwargs 锚/朴素条件判别锚/不掩盖锚）[src/application/services/brand_template_service.py]
- [x] **R1-F6【P3】** Logo 像素维度无上限+magic 浅校验——实测 10×20000 PNG 渲染 LayoutError、9000×9000 渲染峰值 RSS 1.1GB（A2 实验实证）→ **保存期 PIL 惰性读头四重校验**（LOGO_MAX_DIMENSION=4000px——字节与像素正交守卫；UnidentifiedImageError→494 顺带根除「PNG magic+垃圾体」浅校验绕过；except 与 F3 分立消息两分）+假体 JPEG 正例改 Pillow 真生成（评审员②抓出的方案级必红遗漏——全仓唯一假体 JPEG）+6 新格（1×4001 超限/magic+垃圾体/4000 恰值边界/空文件/chmod-000/getsize）+494 触发面 B 案拓宽（七形态计数不变——「非合法可解码图像文件」「超限（字节/像素）」）三处冻结文字同步 [src/application/ports/brand_template.py + report_exceptions.py + _code_ranges.py]
- [x] **R1-F7【P3】** 6-10 验收 S7/S8 无残留 skip 门（S3 有门——OD-13 防御不对称，A2）→ `_count_brand_rows` 上提模块级 `_skip_if_brand_templates_residual` helper（S3 改调用纯移动）+S7/S8 两 then 首部接入同门 [tests/acceptance/test_acceptance_consultant_view.py]
- [x] **R1-F8【P3】** `statement: Any` 非必要类型放宽（A1，mypy 实验已证可删）→ 删注解+孤儿 Any import [brand_template_repository.py:215]
- [x] **R1-F9【P3】** 测试死代码恒假三元（`if False else`）→ 收敛直调（grep 定位非行号——A1 行号锚点 :736-746 勘误为 :761，评审员①定谳）[test_pdf_report_generation_service.py]
- [x] **R1-F10【P3】** 损坏 logo 负例恒真形态+TTF 幂等断言冒烟级（A1+A4）→ `pytest.raises(OSError)` 收窄（reportlab 4.5.1+Pillow 12 实测 UnidentifiedImageError⊂OSError——「解码失败族 vs 实现 bug」分立）+幂等双渲染补 byte 相等断言（invariant fixture 显式请求+`_FONT_REGISTERED` 置空隔离——防「跳过+跳过」空转）[test_reportlab_pdf_renderer_brand.py]
- [x] **R1-F17①【P3】** AC-2 空文件负例缺格（A3）→ b"" 文件 → 494 格落 TestValidationMatrix [test_brand_template_service.py]
- [x] **R1-F14/F15【P3 文档】** File List/S14/结构图三处 src 口径漏 exception_handlers.py（20→21 实为 9+12）+S14 测试清单「4 扩展」实为 9（16→21）+test_report_exceptions.py 连 File List 都未列（A3）→ 三处口径同修+S14 双清单补 6 条目（is_file 断言自动增强）+结构图 src 树补 interfaces/ 行（▲ 第 12 个）+测试树补 4 行+验收文件 6 处计数文案——台账历史行不改写（内联勘误标注）[Story + test_acceptance_white_label_report.py]

#### 已推迟 Defer

- [x] **R1-D1【P2→defer】** CLI 裸跑不加载 .env——组合根引擎空密码连库 InvalidPasswordError（A4 定性：全 CLI 命令同构既有装配面，非 6-11 引入）→ **已有 6.8-R1-DF1 台账条目同根因**（python -m 形态 .env 失效三层根因 6-8 在档）——不重复登记，追加「6-11 代码审查 R1 第五连处置注记」（同链复现佐证：InvalidPasswordError 与 embedding 201 同根因两呈现；触发条件不变）
- [x] **R1-D2【P3 维持】** 生产零建桶——OD-3⑦ 已显式裁定取舍（测试面自愈建桶），A2 复核维持留痕不动

#### 记录组（不落码留痕）

- A4 观察项：`brand-template-list` 非空态仍输出空态提示行（:1363 无条件打印+consultant-view 同款两处一致——与验收钉死行为一致，记录不改）
- 弱断言四项维持：`test_single_argument_call_unchanged` 冒烟级/`with_logo` 透传恒真/验收 `assert COLOR_SCHEME_PRESETS and FONT_PRESETS` 近恒真/`created_at is not None` schema 恒真（无害）——记录在案
- AC-6 skip 门构造格（「预置残留行→skip 触发」）：skip 门本体实测在位（S3/S7/S8 三场景），构造格留档载体替代理由（金字塔分布——清点 helper 逻辑三处共用已有在线验证）
- AC-5 textColor 载体：产物内容流色值断言（:291-299）强于 `_style` spy 单元级断言——载体替代理由（A3 论证成立）
- R1-F16 关闭：test_brand_template_presets.py ruff format 实测 already formatted（A3 发现在当前态不成立——可能为早期状态漂移，留痕）
- 证伪留痕 40+ 条（四视角 Agent 报告在档：洗白嫌疑八文件全排除/UPSERT 三契约在位/组合根接线运行时亲验/冻结面 15 hex 零漂移/8 AC 全承载/勾选零虚报）

#### Round 2 修复记录（回归核查+传播完备性双视角 2026-11-09）

**R2-A 回归核查**：R1 十二项修复终态全在位（file:line 锚点齐）+**突变验证 4/4 闭环**（_do_list 包装删→list 格红/get_by_name 格绿判别隔离；补偿条件改坏→4 格红+修订既有键负向锚正确保持绿；LOGO_MAX_DIMENSION 99999→超限格红+边界正例绿；伞形 except 改窄→两格红）+新破口扫描 7 项零 P0-P2（F2 不吞 RuntimeError 结构证明/F6 全正例夹具 Pillow 真生成/F5 误删判别锚+验收真实链 14/14/F7 四轮 12/12 零误 skip）——**R1 修复质量判定：可信**。

**R2-B 传播完备性**：计数口径 grep 全命中分类（4+2 处旧口径全为历史沿革/台账留痕合规）+12 组台账锚点零失实（3 组行号天然漂移注记）+组合交互终态 5 项全过+S14 增强断言复跑绿+15469 时间线取证可信。

**R2 修复 7 项 P3 全清偿**（快评员评级 5/5 优秀+2 新发现采纳）：
- R2-F1：验收 :974 场景 docstring 计数 20/16→21/21（R1-F14 第 7 处漏网——双 Agent 命中）
- R2-F2：Protocol `save_brand_template` docstring 编排「三重→四重校验」+Raises 494 触发面对齐冻结文字+补 495 行（R1 自立 docstring 同步纪律兑现）
- R2-F3：TestValidationMatrix 类 docstring「七格 494×5+242×1+成功×1」→「13 格 494×10+242×1+成功×2」（类内 13 测试函数实数）
- R2-F4：Story OD-6 行 494 枚举拓宽对齐冻结文字（含「单边」统一）
- R2-F5：service 模块 docstring 重复行删一处（R1-F5 编辑拼接残留——R2 抓到 R1 自身破口的实证）
- R2-F6（快评新发现①）：Story :543 Task 4 红行「校验矩阵七格」+ :996 实施记录——内联勘误模式（历史不改写）
- R2-DF1 defer：checkpoint 验收 Qdrant scroll limit=50×残留 52 点稳定假红（Epic 5 存量测试资产缺陷——隔离二次稳定红机理定谳 top-k 截断，非 6-11 回归[零交集]，deferred-work 登记）

**R2 全量回归**：四目录 15467 passed+5 failed（analyst_view/checkpoint×2/redis_ttl 隔离复跑 38 passed——抖动维持原判定；checkpoint archive 二次稳定红→机理定谳 R2-DF1 预存缺陷）。

---

### 下一步 Next Steps

- [x] Story created with `ready-for-dev` status
- [x] 文档审查修订循环完成（R1-R5 五轮收敛 v1.4.0——零 P0/P1 残留，61 项修复全清偿）
- [x] 运行 `dev-story` 开始实施
- [ ] 运行 `code-review` 进行代码审查（循环审查工作流五轮形态——参照 6-9/6-10 周期）
- [ ] Epic 6 收尾：6-11 done 后运行 `retrospective`（epic-6-retrospective optional）

---

**故事版本/Story Version:** v1.7.0
**创建日期/Created:** 2026-11-08
**最后更新/Last Updated:** 2026-11-09
**更新说明/Description:**
- v1.0.0: 创建故事文件（四 Agent 并行调研[报告导出与品牌对接面/品牌配置持久化模式/CLI 组合根契约验收模板/治理面与范围边界]+主会话亲验 20 组锚点；OD-1~OD-14 十四裁定；13 验收场景钉死[R4 注记：历史沿革记载——创建期口径，R1 起现行口径统一为 14 场景]；6-10 对接锚兑现义务清单六项）
- v1.1.0: 文档审查 Round 1（D1 四视角调研[渲染链/持久化 L4/CLI 组合根/治理面]+D2 三视角审查[一致性计数/测试判别力/契约科学性]+主会话亲验三重实验——byte 等价 invariant 实证/排他实验/epics 亲验；P0×1+P1×8+P2×10+P3×18 修复 37 项全清偿：byte 等价 invariant 前置[reproducible builds 对标]/五色键口径统一/metadata 顶层两键/save 编排 get_by_name 先行/排序统一 updated_at/S6 钦定 noto/S2 钦定编程面/建桶自愈/契约版本断言拆分/共享桶口径/SRC 9+10/14 场景/494 七形态重枚举/切块三注记/构造契约必填/updated_at 责任位/轮次勘误/红锚条件化/variable TTF 渠道+18 项 P3；Docs Review Fixes 表 21 行落档）
- v1.2.0: 文档审查 Round 2（R2-A 回归核查[21 行台账逐项 git 对照+八焦点交叉 grep——主位全落地+Edit 误删零发现+新锚点抽测全中]+R2-B 组合交互推演[8 组——2 组冲突/4 组成立带注记/2 组净成立]；P1×1+P2×2+P3×9 修复 12 项全清偿：R2-B-1 字典化×零修改互拆[:282 monkeypatch 布尔→dict 例外 carve out 四处]/R2-B-2 预置直写通道 updated_at 恒值互拆[显式构造义务两处+AC-3 载体钉位]/R2-A-1 :214 S2 口径传播漏网/九项 P3[锚勘误 :470/七格术语分立/资产文件名渠道二择/File List 标题/尾位措辞/仓储构造通则/updated_at 前进单点承载/AC-7 通道分立/teardown 顺序钦定/7.2 承载位钉死]；台账 25 行）
- v1.3.0: 文档审查 Round 3（单深度推演四板块[14 场景三轴完备/模板生命周期六时间线/14 OD 交叉互证/Task 0→9 依赖干跑]——P1×1+P2×3+P3×6 修复 10 项全清偿+8 条证伪不成立疑点留痕：R3-1 GeneratePdfReportUseCase 传递链中间件四清单缺位[--brand-template CLI→use case→服务的必需环节——execute 增 keyword-only 透传+注册零改动维持 v1.0.0，五处补位 10→11 文件 19→20 项]/R3-2 导出侧资产全生命周期双不完整[BLM 八阶段预置链 6-5b :600-758 直系+strategic_reports/event_outbox/WORM PDF bypass_governance 三面清理——端口 delete 抛 ComplianceLockError 亲验]/R3-3 consultant_view 升级双写矛盾[lambda 先落服务两参 TypeError 破坏窗口→五件同批原子落 Task 6]/R3-4 验证器 C 白名单自矛盾[仅枚举 infra 自我误伤 domain/application 6 文件→三层全量 9 文件+集合等值双向判别]/六项 P3[name 前置预检防孤儿 logo/get_render_spec 前置钦定 S8 免预置直达 494/Pillow 生成可解码 Logo/OD-5 修订跨导出 MVP 接受注记/6-10 CLI 显示块 :1800-1804 三值派生改造/AC-1 UPSERT 载体声明]；台账 25→29 行）
- v1.3.0（R4 纯验证轮·版本不递增）：五节全过零 ✗——修复存续双向取证[R3 十项 diff↔终态双在场+R1 五大（invariant 13 处/五色 17 处/两键/get_by_name 先行 10 处/updated_at 降序 9 处）+R2 四项终态存续]/计数终核[14 场景 16 处+20 src 文件三处+OD14/锚13/台账29/矩阵22 全覆盖+版本链四段]/外部锚点 40+ 组全中[含 :282 monkeypatch 布尔/generate_pdf_report :27 单参/ComplianceLockError/6-5b 清理链五组]/红线终扫[五词零命中+三笔提交零 AI 署名]/结构终验[15 hunk 无 Edit 误删+术语终扫全一致]；唯一注记项澄清：footer v1.0.0 沿革行「13 验收场景」历史记载内联注记（成本趋零应做）
- v1.4.0: 文档审查 Round 5 独立终审收敛（六节取证全过——周期闭合[四笔提交链无游离+行数守恒 1090→1103]/关键修复双向取证 6/6[含 invariant 独立复现实验再证——默认态双渲染 byte 不等/invariant=1 下相等]/独立快扫 30+ 锚点全中/全量等效/台账 29 行+证伪 8 条在档零未核销/红线+状态判定[ready-for-dev 维持正确]；特权发现 2 项 P3 随收敛清偿：F-1 白名单计数 9↔8 勘误[枚举恰 8 个 .py——fonts 资产文件名无 brand 词族归目录单列]/F-2 File List generate_pdf_report.py 段落归类勘误[待创建→待修改段]；收敛声明入档见下节——**零 P0/P1/P2 残留，五轮周期收敛，可进 dev-story**）
- v1.5.0: dev-story 实施完成 in-progress→review（Task 0~9 全勾：14/14 验收场景全绿+集成五场景 6 用例+四目录全量两轮 15452/15458 passed+2 skipped+2 预存抖动[analyst_view Redis 跨循环+checkpoint_snapshot Qdrant 最终一致——均与 6-11 零因果面，隔离复跑+单场景双跑+整文件复跑三重绿定谳，组内流量放大共享设施时序窗形态登记代码审查轮复核]+新增文件覆盖率 service 98%/仓储 96%/实体与 VO 100%+整体 91%+mypy 773 零错+ruff 全仓过+变异锚 14 处全实证[实体 2/仓储 2/渲染器 4/服务 5/CLI 3+Task7 补 1/集成 1]+三红线 grep 归零[ports helper 三处裸 ValueError 实施中自查发现并修复为 494 直抛]+:282 monkeypatch carve out 机械适配+deferred-work 14 行处置注记+TTF 资产入仓[外网不可达改本地官方分发物双验证];实施攻坚四留痕：pytest-bdd 同文本单绑定纪律/S8 补 exit code 为 1 独立步骤绑定/pytest-asyncio auto 模式探测协程化[自建 loop 双循环冲突]/每测试三清[SINGLETON 缓存绑定旧 loop→InterfaceError 驱逐重建]——详注见 Dev Agent Record Task 1~9 实施记录）
- v1.6.0: 代码审查 Round 1（四视角并行调研[盲审对抗/边界狩猎/验收审计/运行面实测——双 Agent 独立命中 F2 读写契约虚设]+实测证据链[未迁移环境 3 FAILED 假红复现/畸形 logo RSS 1.1GB 实测/invariant 六断言/组合根 9 端口 resolve 亲验/CLI 真实链 UPSERT 探针]+C3 双评审员方案评审[测试判别力四缺口全采纳：_do_list 独立格/with_session 钦定形态/chmod-000 真链主格/假体 JPEG 必红遗漏/新写键判别锚]+落码 11 项[零 P0/P1×1+P2×2+P3×8]+defer 2+证伪留痕 40+：R1-F1 集成门三测补齐[未迁移环境 6 skipped 实测闭环]/R1-F2 仓储层 495 读路径单点包装[契约三处冻结兑现+ Raises docstring 同步+包装两格]/R1-F3 OSError 伞形守卫/R1-F5 孤儿 logo 新写键补偿[五格判别]/R1-F6 像素维度四重校验[4000px+PIL 深解析——RSS 实证+假体 JPEG 改真生成+494 触发面 B 案拓宽三处冻结文字]/R1-F7 S7/S8 skip 门补层[helper 上提三场景共用]/R1-F8 Any 删除/R1-F9 死代码/R1-F10 OSError 收窄+byte 幂等断言/R1-F17① 空文件格/R1-F14·15 计数勘误[20→21+16→21 三处口径+S14 双清单+结构图两树+验收 6 文案]；全绿证据：服务 31+仓储 17+渲染器/pdf 六文件 135+集成验收 32+验收白标 14 未迁移环境集成 6 skipped）
- v1.7.0: 代码审查 Round 2（回归核查+传播完备性双视角——R2-A 突变验证 4/4 闭环[包装删→list 格红/补偿条件改坏→4 格红+负向锚正确保持绿/阈值爆→超限格红/伞形改窄→两格红——R1 修复质量判定可信]+R2-B 传播核查[计数口径全命中分类合规+12 组台账锚点零失实+组合交互 5 项全过]；修复 7 项 P3 全清偿[快评 5/5 优秀+2 新发现采纳]：R2-F1 验收 :974 场景 docstring 计数[R1-F14 第 7 处漏网双 Agent 命中]/R2-F2 Protocol save docstring 四重校验+494 冻结文字对齐+495 行补齐/R2-F3 校验矩阵类 docstring 七格→13 格[R1-F6 补格后实数]/R2-F4 OD-6 枚举拓宽[含单边统一]/R2-F5 service 模块 docstring 重复行[R1-F5 拼接残留——R2 抓 R1 自身破口实证]/R2-F6 Story :543/:996 七格内联勘误[历史不改写]；R2-DF1 defer：checkpoint 验收 Qdrant scroll limit=50×残留 52 点稳定假红[隔离二次红机理定谳 top-k 截断——Epic 5 存量测试资产缺陷非 6-11 回归零交集，deferred-work 登记承接二择一：filter 定向/残留清理]；R2 全量四目录 15467 passed+5 failed 甄别[analyst_view/checkpoint×2/redis_ttl 隔离绿抖动维持+archive 稳定红→R2-DF1]）

### 🏁 文档审查周期收敛声明（R1-R5 五轮独立终审 v1.4.0）

**周期闭合**：五轮提交链 f49e4e78（R1）→ 088a0426（R2）→ 74d70b55（R3）→ c9233a28（R4 纯验证零修复）→ R5 收敛轮（本声明落档），基线 9258b36d 之上无游离提交；story+sprint-status 全部入库，工作区 clean。

**关键修复取证（R5 六节独立复核 6/6，不轻信自报）**：R1-P0 invariant 前提经独立复现实验再证（默认态双渲染 byte 不等 / `rl_config.invariant=1` 下相等——两模式产物互异）；R1-P1 get_by_name 先行三处一致+L4 键锚定闭合；R2-P1 :282 carve out 四处注记与 monkeypatch 布尔字面量代码现实逐字吻合；R2-P2 预置 updated_at 两处+6-10 `_preset_anchor` :280-292 先例真实；R3-P1 use case 透传五处补位+现状单参签名 :27 亲验；R3-P2 白名单结构图 ▲11 逐点吻合。外部锚点 30+ 组独立抽验全中；术语终态快照零未注记残留；红线双口径（文档面/提交署名）零违例。

**全周期统计**：R1 37 项（P0×1+P1×8+P2×10+P3×18）+ R2 12 项（P1×1+P2×2+P3×9）+ R3 10 项（P1×1+P2×3+P3×6）+ R4 零修复纯验证 + R5 特权发现 2 项 P3——**累计 61 项修复全清偿 + 8 条证伪不成立留痕，零留项**。

**收敛判定**：零 P0/P1/P2 残留（R4 五节纯验证 + R5 独立快扫复证）——文档审查周期收敛，Story 维持 `ready-for-dev`，可进 `dev-story`。
