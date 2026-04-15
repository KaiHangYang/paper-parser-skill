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
