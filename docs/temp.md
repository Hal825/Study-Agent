 Bash(cd "d:/Code/VScode/Study-Agent/backend" && for f in app/prompts/templates/note/*.md app/prompts/templates/vision/*.j2; do echo "=== $f ===" && head -20
      "$f" &&…)
  ⎿  === app/prompts/templates/note/cornell.md ===
     你是一位专业的学习笔记整理助手。请将用户提供的内容整理为**康奈尔笔记**格式，要求如下：
     … +51 lines (ctrl+o to expand)
  ⎿  Allowed by auto mode classifier

  Thought for 8s (ctrl+o to expand)

● 以下是为「笔记生成」流程各个环节、工具/Agent、以及所使用 Prompt 的完整清单：
  
  ---
  笔记生成流水线 (NoteGenerationSkill)

  Agent 图执行顺序：parse → extract → analyze → confirm → generate

  环节1: parse    ─── ContentParser (纯本地,无LLM)
  环节2: extract  ─── EntityExtractor (LLM, DeepSeekProvider)
  环节3: analyze  ─── StructureAnalyzer (LLM, DeepSeekProvider)
  环节4: confirm  ─── Human-in-the-Loop (无LLM)
  环节5: generate ─── LLMService.generate() (DeepSeekProvider)

  ┌───────────┬───────────────────────┬──────┬────────────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
  │   环节    │         Tool          │ LLM? │                      Prompt 来源                       │                    Prompt 位置                    │
  ├───────────┼───────────────────────┼──────┼────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 1. parse  │ ContentParser         │ 否   │ 无                                                     │ —                                                 │
  ├───────────┼───────────────────────┼──────┼────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 2.        │ EntityExtractor       │ 是   │ ENTITY_EXTRACTION_PROMPT                               │ app/tools/entity_extractor.py:41                  │
  │ extract   │                       │      │                                                        │                                                   │
  ├───────────┼───────────────────────┼──────┼────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 3.        │ StructureAnalyzer     │ 是   │ STRUCTURE_ANALYSIS_PROMPT                              │ app/tools/structure_analyzer.py:52                │
  │ analyze   │                       │      │                                                        │                                                   │
  ├───────────┼───────────────────────┼──────┼────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 4.        │ 无 (中断)             │ 否   │ 无                                                     │ —                                                 │
  │ confirm   │                       │      │                                                        │                                                   │
  ├───────────┼───────────────────────┼──────┼────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 5.        │ LLMService.generate() │ 是   │ System: templates/note/{template}.md<br>User:          │ app/prompts/templates/note/*.md (4                │
  │ generate  │                       │      │ _build_enriched_user_message()                         │ 个)<br>app/skills/note_gen.py:244                 │
  └───────────┴───────────────────────┴──────┴────────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘

  ---
  视觉预处理流水线 (VisionPreprocessorTool)

  图片 → compress → Qwen VL → clean → Markdown

  ┌──────────┬────────────────────────┬──────────┬───────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
  │   环节   │          Tool          │   LLM?   │            Prompt 来源            │                             Prompt 位置                             │
  ├──────────┼────────────────────────┼──────────┼───────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ 图片识别 │ VisionPreprocessorTool │ 是 (Qwen │ DEFAULT_PROMPT (hardcoded) <br>或 │ app/tools/vision_preprocessor.py:63 <br>模板副本:                   │
  │          │                        │  VL)     │  custom_prompt 参数覆盖           │ app/prompts/templates/vision/extract_math.j2                        │
  └──────────┴────────────────────────┴──────────┴───────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

  ---
  Prompt 详细清单

  A. EntityExtractor (环节2 — extract)

  文件: app/tools/entity_extractor.py:41

  类型: System Prompt（硬编码在 Python）

  内容摘要:
  你是一位知识提取专家。请从以下学习内容中提取关键知识实体。
  要求：
  1. 为每个实体标注类别（概念/术语/人物/公式/事件）
  2. 标注重要程度（high/medium/low）
  3. 提供每个实体在原文中的简要上下文
  4. 标注实体之间的关联关系
  输出格式：JSON { entities: [{name, category, importance, context, related}] }
  - temperature=0.3, max_tokens=2048
  - User Message: "学习内容：\n\n{content[:8000]}" + 章节结构摘要

  B. StructureAnalyzer (环节3 — analyze)

  文件: app/tools/structure_analyzer.py:52

  类型: System Prompt（硬编码在 Python）

  内容摘要:
  你是一位知识结构分析专家。请分析以下学习内容的结构。
  要求：
  1. 判断内容类型（article/lecture/notes/unknown）
  2. 评估内容层次深度（1-3）
  3. 识别 3-5 个核心主题，列出子主题
  4. 建议一个学习笔记的大纲
  5. 评估复杂度（simple/medium/complex）
  6. 预估学习时间（分钟）
  输出格式：JSON { content_type, hierarchy_depth, main_topics, suggested_outline, complexity, estimated_study_time_minutes }
  - temperature=0.3, max_tokens=2048
  - User Message: 字数 + 章节结构 + 内容前 3000 字

  C. 笔记生成 System Prompt (环节5 — generate)

  文件: app/prompts/templates/note/*.md（4 个模板，通过 PromptRegistry 按 key 加载）

  ┌──────────────┬─────────┬───────────────────────────┐
  │     Key      │ 模板 ID │           文件            │
  ├──────────────┼─────────┼───────────────────────────┤
  │ note/outline │ outline │ templates/note/outline.md │
  ├──────────────┼─────────┼───────────────────────────┤
  │ note/summary │ summary │ templates/note/summary.md │
  ├──────────────┼─────────┼───────────────────────────┤
  │ note/cornell │ cornell │ templates/note/cornell.md │
  ├──────────────┼─────────┼───────────────────────────┤
  │ note/qa      │ qa      │ templates/note/qa.md      │
  └──────────────┴─────────┴───────────────────────────┘

  共同角色声明: "你是一位专业的学习笔记整理助手"

  各自格式规则:

  ┌─────────┬────────────────────────────────────────────────────────────────────┐
  │  模板   │                              核心规则                              │
  ├─────────┼────────────────────────────────────────────────────────────────────┤
  │ outline │ 多级 Markdown 标题、无序/有序列表、加粗术语、末尾「总结回顾」      │
  ├─────────┼────────────────────────────────────────────────────────────────────┤
  │ summary │ 连贯段落、二级标题分段、> 引用块、开头「概述」+ 结尾「总结」       │
  ├─────────┼────────────────────────────────────────────────────────────────────┤
  │ cornell │ Markdown 表格（线索栏/笔记栏）、5-8 个关键问题、表格下方「总结栏」 │
  ├─────────┼────────────────────────────────────────────────────────────────────┤
  │ qa      │ ## Q1: 问题 + **答：** 回答、--- 分隔、5-8 个关键问题              │
  └─────────┴────────────────────────────────────────────────────────────────────┘

  User Message: 由 _build_enriched_user_message() 动态构建（app/skills/note_gen.py:244），注入所有前序 Tool 产出：
  ## 原始学习内容
  {content}

  ## 内容结构
  {parsed_sections}

  ## 已识别的核心概念
  {key_concepts}

  ## 建议的笔记大纲
  {suggested_outline}

  内容类型: {content_type}
  复杂度: {complexity}
  预估学习时间: {estimated_study_time_minutes} 分钟
  语言: {parsed_language}
  - temperature=0.7, max_tokens=4096

  D. VisionPreprocessorTool (图片 OCR 识别)

  文件: app/tools/vision_preprocessor.py:63（硬编码副本） + app/prompts/templates/vision/extract_math.j2（模板文件）

  类型: User Message（多模态 image_url + text）

  内容摘要:
  你是一个顶级的学术文档OCR专家，尤其擅长数学公式识别。
  1. 数学公式用 LaTeX: 行间 $$...$$, 行内 $...$
  2. 分式/根号/上下标/积分/求和 必须精确识别
  3. 表格用 Markdown 管道符
  4. 普通文字按段落输出，保留换行
  5. 只输出提取内容，不要解释性文字
  - temperature=0.1, max_tokens=4096

  ---
  汇总

  ┌───────────────────┬──────┬───────────────────────────────────────────────────────────────────────┐
  │       类型        │ 数量 │                                 位置                                  │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ 无 LLM 环节       │ 2 个 │ parse (ContentParser) + confirm (中断)                                │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ LLM 环节          │ 3 个 │ extract + analyze + generate                                          │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ Vision 识别       │ 1 个 │ VisionPreprocessorTool (Qwen VL)                                      │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ Prompt 模板文件   │ 5 个 │ templates/note/ × 4 + templates/vision/ × 1                           │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ 硬编码 Prompt     │ 3 个 │ ENTITY_EXTRACTION_PROMPT + STRUCTURE_ANALYSIS_PROMPT + DEFAULT_PROMPT │
  ├───────────────────┼──────┼───────────────────────────────────────────────────────────────────────┤
  │ 动态构建 User Msg │ 1 个 │ _build_enriched_user_message() in note_gen.py                         │
  └───────────────────┴──────┴───────────────────────────────────────────────────────────────────────┘