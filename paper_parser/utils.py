import os
import re
from pathlib import Path
from .config import config

# arXiv ID 格式：
#   新式: YYMM.NNNNN[vN]   e.g. 2312.10997, 2312.10997v2
#   旧式: category/NNNNNNN[vN]  e.g. cs/0611088, hep-th/9901001v3
_ARXIV_ID_RE = re.compile(
    r"^\d{4}\.\d{4,5}(v\d+)?$"          # 新式
    r"|^[a-z][\w-]*(\.[A-Z]{2})?/\d{7}(v\d+)?$"  # 旧式
)

def is_arxiv_id(s: str) -> bool:
    """Return True if *s* looks like a valid arXiv paper ID."""
    return bool(_ARXIV_ID_RE.match(s.strip()))

def sanitize_id(paper_id):
    """Sanitize arXiv ID to be used as a directory name."""
    # Replace slashes in older IDs (e.g., hep-th/9901001) with underscores
    return re.sub(r'[\\/:*?"<>|]', '_', paper_id)

def get_work_dir():
    """Get the base workspace directory from config."""
    workspace = config.get("PAPER_WORKSPACE")
    # Resolve ~ if present
    workspace_path = Path(os.path.expanduser(workspace))
    workspace_path.mkdir(parents=True, exist_ok=True)
    return workspace_path

def get_paper_dir(paper_id):
    """Get the directory for a specific paper using its ID."""
    base_dir = get_work_dir()
    safe_id = sanitize_id(paper_id)
    paper_dir = base_dir / safe_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    return paper_dir

def get_cached_paper(paper_id):
    """Look up a paper from local cache by arXiv ID.
    
    Returns a result dict (same shape as arxiv_client results) if found,
    or None if the paper has not been downloaded locally.
    """
    base_dir = get_work_dir()
    safe_id = sanitize_id(paper_id)
    paper_dir = base_dir / safe_id

    title_path = paper_dir / "title.md"
    pdf_path = paper_dir / "paper.pdf"

    if not paper_dir.exists() or not title_path.exists():
        return None

    # Parse title from "# <title>" format
    try:
        raw = title_path.read_text(encoding="utf-8").strip()
        title = raw.lstrip("#").strip() if raw.startswith("#") else raw
    except Exception:
        title = paper_id

    return {
        "id": paper_id,
        "title": title,
        "pdf_url": f"https://arxiv.org/pdf/{paper_id}",
        "score": 100,
        "_cached": True,
        "_has_pdf": pdf_path.exists(),
    }
