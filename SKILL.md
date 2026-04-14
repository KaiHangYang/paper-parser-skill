---
name: paper-parser
description: CLI tool to search, download, and parse academic papers from arXiv into AI-friendly Markdown using MinerU API.
triggers: paper, arXiv ID, search, download, parse, pp
---

# Paper Parser Skill

CLI tool for automated academic paper processing.

## Core Functions

- **Search**: Fuzzy search arXiv by title or keywords.
- **Download**: Retrieve PDF into ID-based workspace.
- **Parse**: Convert PDF to structured, chapter-split Markdown via MinerU V4 API.
- **Caching**: Incremental processing to avoid redundant API calls.

## Setup

```bash
git clone https://github.com/KaiHangYang/paper-parser-skill.git
cd paper-parser-skill
pip install -e .
```

## Configuration

Default path: `~/.paper-parser/config.yaml`

```yaml
PAPER_WORKSPACE: "~/paper-parser-workspace"
MINERU_API_TOKEN: "required_token"
MINERU_API_BASE_URL: "https://mineru.net/api/v4"
MINERU_API_TIMEOUT: 600
```

## CLI Usage

Alias: `pp`

| Command | Argument | Description |
| --- | --- | --- |
| `pp search` | `<query>` | Search arXiv papers |
| `pp download` | `<id/query>` | Download PDF and metadata |
| `pp parse` | `<id/path>` | Parse PDF into Markdown chapters |
| `pp all` | `<id/query>` | Full workflow: Search -> Download -> Parse |
| `pp path` | `<id/query>` | Get local workspace path |

## Workspace Structure

```text
PAPER_WORKSPACE/
└── <arxiv_id>/
    ├── paper.pdf
    ├── title.md
    └── markdowns/
        ├── 01_Introduction.md
        └── images/
```

## Requirements

- Python >= 3.8
- `requests`, `click`, `PyYAML`, `arxiv`, `rapidfuzz`
- MinerU API Token (Get it at [mineru.net](https://mineru.net/))
