---
name: paper-parser-skill
description: CLI tool to search, download, and parse academic papers from arXiv into AI-friendly Markdown using MinerU API.
version: 0.1.2
author: KaiHangYang
homepage: https://github.com/KaiHangYang/paper-parser-skill
triggers: paper, arXiv ID, search, download, parse, agent-friendly
metadata:
  openclaw:
    requires:
      config:
        - ~/.paper-parser/config.yaml
---

# Paper Parser Skill

CLI tool for automated academic paper processing.

## 🛡️ Data Privacy & Security

> [!IMPORTANT]
> **External Data Processing**: This skill transmits PDF files and paper metadata to [MinerU](https://mineru.net/) (opendatalab) for layout analysis and Markdown conversion. Please ensure you trust the service and understand their data handling policies before providing an API token in the configuration file.

**Security & Provenance:**
- **Open Source**: The full source code is available on [GitHub](https://github.com/KaiHangYang/paper-parser-skill).
- **Verified Package**: This tool is published on [PyPI](https://pypi.org/project/paper-parser-skill/) as a standard Python package.
- **Local Control**: All search results and downloaded PDFs are stored locally in your specified workspace.

## 🚀 Setup

```bash
pip install paper-parser-skill
```

## ⚙️ Configuration

Default path: `~/.paper-parser/config.yaml`

```yaml
PAPER_WORKSPACE: "~/paper-parser-workspace"
MINERU_API_TOKEN: "required_token"
MINERU_API_BASE_URL: "https://mineru.net/api/v4"
MINERU_API_TIMEOUT: 600
```

## 📖 CLI Usage

Alias: `pp`

| Command | Argument | Description |
| --- | --- | --- |
| `pp search` | `<query>` | Search arXiv papers |
| `pp download` | `<id/query>` | Download PDF and metadata |
| `pp parse` | `<id/path>` | Parse PDF into Markdown chapters |
| `pp all` | `<id/query>` | Full workflow: Search -> Download -> Parse |
| `pp path` | `<id/query>` | Get local workspace path |

## 📂 Workspace Structure

```text
PAPER_WORKSPACE/
└── <arxiv_id>/
    ├── paper.pdf
    ├── title.md
    └── markdowns/
        ├── 01_Introduction.md
        └── images/
```

## 🛠️ Requirements

- Python >= 3.8
- `requests`, `click`, `PyYAML`, `arxiv`, `rapidfuzz`
- **MinerU API Token**: Required for the parsing stage. Add it to your `config.yaml` file. Get one at [mineru.net](https://mineru.net/).
