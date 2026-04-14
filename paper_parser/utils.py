import os
import re
from pathlib import Path
from .config import config

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
