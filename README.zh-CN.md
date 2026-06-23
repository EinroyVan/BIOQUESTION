# Questioner

自然科学文献学习工作流：**提取知识点 → 生成测验 → 批改评分**。

适用于物理学、化学、生物学、地球科学、天文学、材料科学等自然科学领域。提供 Streamlit 网页界面与命令行工具。

**English:** [README.md](README.md)

## 功能

- 上传 **TXT** 或 **PDF**（扫描版 PDF 自动 OCR）
- 提取实体、机制、结论，并附原文引用
- **Normal 模式**：5 道不定项（每题 10 分）+ 3 道逻辑题（每题 6 分，全对满分、答错 0 分）+ 2 道简答题（每题 16 分），总分 100
- **Easy 模式**：4 道单选题（A–D 四选一）+ 1 道简答题，仅反馈不计分
- **Custom 模式**：自定义各题型数量
- 多 LLM 后端：**Google Gemini**、**OpenAI**、**Anthropic Claude**、**OpenAI 兼容接口**
- 界面多语言（Google 翻译）：中文、English、日本語、한국어 等
- 本地个人成绩统计（需填写昵称）；团队排行榜占位接口

## 安装

```bash
cd Questioner   # 或你的克隆目录
python -m pip install -r requirements.txt
python -m pip install -e .
copy .env.example .env   # Windows
# cp .env.example .env  # Linux / macOS
```

### API 密钥（`.env`）

| 提供商 | 环境变量 |
|--------|----------|
| Google Gemini（默认） | `GOOGLE_API_KEY`、`GOOGLE_MODEL` |
| OpenAI | `OPENAI_API_KEY`、`OPENAI_MODEL`，可选 `OPENAI_BASE_URL` |
| Anthropic | `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL` |
| OpenAI 兼容 | `OPENAI_COMPAT_API_KEY`、`OPENAI_COMPAT_BASE_URL`、`OPENAI_COMPAT_MODEL` |

在 Streamlit 侧边栏选择 LLM 提供商（仅当前会话生效，不修改 `.env`）。

界面翻译通过 `deep-translator` 调用 Google 翻译，**不消耗 LLM API 额度**。

## 网页界面（推荐）

```bash
python -m streamlit run app.py
```

浏览器打开 http://localhost:8502

Windows 也可双击 `start.bat`。

## 命令行

```bash
python main.py extract -i examples/literature_sample.txt -o output/knowledge.json
python main.py quiz -k output/knowledge.json -o output/quiz.json
python main.py grade -q output/quiz.json -I -o output/grading.json
python main.py pipeline -i examples/literature_sample.txt -d output
```

CLI 默认提供商可在 `.env` 中设置 `LLM_PROVIDER=google`（或 `openai`、`anthropic`、`openai_compatible`）。

## 项目结构

```
Questioner/
├── app.py              # Streamlit 入口
├── main.py             # CLI 入口
├── questioner/         # Python 包
├── examples/
└── .streamlit/         # 端口 8502
```

## 评分说明

- **单选 / 不定项 / 逻辑题**：根据出题时生成的标准答案，由脚本自动判分（不消耗 LLM tokens）。
- **逻辑题**：独立评分规则——答对 6 分，答错 0 分，不适用不定项的部分得分规则。
- **简答题**：由 LLM 批改，支持部分得分。

## 逻辑题（Q6–Q8）

- 顶部一次性展示母题 A–E 选项说明
- 每道子题给出 α、β 两个描述，选择 A–E 之一即可

## 个人统计

- Normal / Custom 模式提交前需填写昵称（≤ 12 个全角字符）
- 数据保存在本地 `output/stats/`

## 安全

切勿将 `.env` 提交到版本库。仅以 `.env.example` 为模板。

## 许可证

MIT
