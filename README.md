# Paper Parser 🛠️

**Efficient arXiv Search, Download, and AI-Friendly Markdown Parsing.**

`paper-parser` is a CLI tool designed to streamline the academic research workflow. It handles everything from finding a paper on arXiv to converting it into a clean, structured Markdown format that is optimized for LLMs and AI agents.

## 🚀 Why Use Paper Parser?

Standard PDF-to-text tools often produce one massive block of text, which leads to two major problems when working with AI:
1.  **Context Overflow**: Large papers can exceed an LLM's context window.
2.  **Token Waste**: Paying for the entire paper's context when you only need to analyze the "Methodology" or "Conclusion" is expensive and slow.

**The Solution:** `paper-parser` uses the **MinerU V4 API** to extract high-quality Markdown and then **automatically splits the paper into chapters**. This allows AI agents to read the paper **section-by-section**, enabling:
-   ✅ **Granular Context Management**: Only read what matters.
-   ✅ **Significant Token Savings**: Drastically reduce your API bills.
-   ✅ **Higher Accuracy**: Focus the model's attention on specific sections.

---

## ✨ Key Features

-   **🔍 Intelligent Search**: Typos? No problem. Fuzzy-searches arXiv with relevance ranking.
-   **📥 Smart Download**: Downloads PDFs into organized, ID-based directories.
-   **🧩 Section Splitting**: Automatically splits papers into `01_Introduction.md`, `02_Methodology.md`, etc.
-   **📦 Incremental Processing**: Remembers what you've already downloaded and parsed—no redundant API calls.
-   **🖼️ Image Extraction**: Extracts images and maintains correct relative links within the Markdown chapters.
-   **📝 Note Templates**: Automatically generates `title.md` and `summary.md` for your research notes.

---

## 🛠️ Installation

### From PyPI (Recommended)
```bash
pip install paper-parser-skill==v0.1.3
```

### From Source
```bash
# Clone the repository
git clone https://github.com/KaiHangYang/paper-parser-skill.git
cd paper-parser-skill

# Install in editable mode
pip install -e .
```

## ⚙️ Configuration

The first time you run `pp`, it will create a configuration file at `~/.paper-parser/config.yaml`.

```yaml
MINERU_API_TOKEN: "your_token_from_mineru.net"
PAPER_WORKSPACE: "~/paper-parser-workspace"
MINERU_API_TIMEOUT: 600
```
> [!IMPORTANT]
> You need an API token from [MinerU](https://mineru.net/) to use the parsing features.

---

## 📖 Usage Guide

### Basic Commands

```bash
# Search for a paper by keyword or arXiv ID
pp search "LLaMA 3"
pp search 2303.17564

# Download a paper PDF (cached if already downloaded)
pp download 2303.17564

# Find where a paper is stored locally
pp path 2303.17564
```

### Parsing — Synchronous (Blocking ⚠️)

> [!WARNING]
> `pp parse` and `pp all` block until cloud processing completes, which can take several minutes.
> For agent/automation use, prefer the async workflow below.

```bash
# Parse a local PDF or an arXiv paper already downloaded
pp parse 2303.17564
pp parse ./my_local_paper.pdf

# Full workflow in one shot: Search → Download → Parse
pp all 2303.17564
```

### Parsing — Async (Recommended for Agents ✅)

```bash
# Step 1: Submit for parsing and return immediately
#  → auto-downloads PDF if needed, uploads to MinerU, returns batch_id
pp submit 2303.17564

# Step 2: Check status later — downloads results automatically when done
pp check 2303.17564
# → "⏳ Still processing" or "✅ Parsing complete!"
```

> [!TIP]
> `pp submit` is **idempotent**: calling it again on the same paper won't re-upload.
> It checks the existing task status and returns the current state instead.
> All commands (`parse`, `all`, `submit`, `check`) share the same `.parse_task.json` state file,
> so you can freely mix sync and async workflows.

## 📂 Output Structure

```text
PAPER_WORKSPACE/
└── 2303.17564/              # ArXiv ID
    ├── paper.pdf            # Original PDF
    ├── title.md             # Paper metadata
    ├── summary.md           # Note-taking template
    ├── .parse_task.json     # Task state (batch_id, status, timestamps)
    └── markdowns/           # AI-Ready Content
        ├── 01_Introduction.md
        ├── 02_Methods.md
        ├── ...
        └── images/          # Extracted figures & tables
```

## 🤝 Acknowledgments

- [arXiv](https://arxiv.org/) for the academic paper API.
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) for fast fuzzy string matching.
- [MinerU](https://github.com/opendatalab/MinerU) ([mineru.net](https://mineru.net/)) for high-quality PDF-to-Markdown parsing.

## 📜 License

[MIT](LICENSE)
