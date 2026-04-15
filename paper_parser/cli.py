import click
import os
from pathlib import Path
from . import arxiv_client, mineru_client, utils
from .config import DEFAULT_CONFIG_PATH
from .mineru_client import TASK_FILENAME
from .utils import is_arxiv_id

@click.group(help=f"""
Paper Parser CLI - Search, Download, and Parse academic papers.

Configuration is stored in: {DEFAULT_CONFIG_PATH}
""")
def cli():
    pass

@cli.command()
@click.argument('query')
@click.option('--limit', default=5, help='Number of results to show.')
def search(query, limit):
    """Search for papers on arXiv."""
    results = arxiv_client.search_arxiv(query, max_results=limit)
    if not results:
        click.echo("No papers found.")
        return

    for i, res in enumerate(results, 1):
        click.echo(f"{i}. Id: {res['id']}")
        click.echo(f"   Title: {res['title']}")
        click.echo(f"   Link: {res['pdf_url']}")

@cli.command()
@click.argument('query_or_id')
@click.option('--force', is_flag=True, help='Force re-download even if PDF exists.')
def download(query_or_id, force):
    """Download a paper PDF by arXiv ID or query."""
    click.echo(f"🔍 Finding paper: {query_or_id}")
    
    # 1. Resolve paper
    is_id = arxiv_client.search_arxiv(f"id:{query_or_id}") if is_arxiv_id(query_or_id) else []
    results = is_id if is_id else arxiv_client.search_arxiv(query_or_id, max_results=1)
    
    if not results:
        click.echo("❌ Paper not found.")
        return
    
    paper = results[0]
    click.echo(f"📄 Found: {paper['title']}")
    
    # 2. Setup directory and metadata
    paper_dir = utils.get_paper_dir(paper['id'])
    pdf_path = paper_dir / "paper.pdf"
    title_path = paper_dir / "title.md"
    title_path.write_text(f"# {paper['title']}\n", encoding='utf-8')
    
    summary_path = paper_dir / "summary.md"
    if not summary_path.exists():
        summary_path.write_text(f"# Summary: {paper['title']}\n\n## Key Takeaways\n\n- \n", encoding='utf-8')
    
    # 3. Download (with cache check)
    if not force and pdf_path.exists():
        click.echo(f"⏭️  Skipping Download: PDF already exists in {paper_dir}")
        return

    if arxiv_client.download_pdf(paper['pdf_url'], pdf_path):
        click.echo(f"✅ Paper downloaded to: {paper_dir}")

@cli.command()
@click.argument('target')
@click.option('--output-dir', help='Force output directory')
@click.option('--force', is_flag=True, help='Force re-parsing even if results exist.')
def parse(target, output_dir, force):
    """Parse a PDF using MinerU API. TARGET can be a local PDF path or an arXiv ID."""
    pdf_path = None
    final_output_dir = None

    # Case 1: Local File
    if os.path.isfile(target):
        pdf_path = Path(target)
        final_output_dir = Path(output_dir) if output_dir else pdf_path.parent / "paper"
        click.echo(f"📄 Local PDF detected: {pdf_path}")
    
    # Case 2: arXiv ID (or something else)
    else:
        # Resolve ID to folder
        paper_dir = utils.get_paper_dir(target)
        pdf_path = paper_dir / "paper.pdf"
        final_output_dir = Path(output_dir) if output_dir else paper_dir
        
        if not pdf_path.exists():
            click.echo(f"❌ Error: {target} is not a file, and no paper.pdf found in workspace for ID [{target}].")
            click.echo(f"   Try 'pp download {target}' first.")
            return
        
        click.echo(f"📚 arXiv paper detected: [{target}]")

    # Incremental check
    if not force and (final_output_dir / "markdowns").exists():
        click.echo(f"⏭️  Skipping: Results already exist in {final_output_dir}")
        return

    click.echo(f"🔄 Parsing {pdf_path}...")
    try:
        mineru_client.parse_paper(str(pdf_path), str(final_output_dir))
        click.echo(f"✅ Parsing complete. Results in {final_output_dir}")
    except ValueError as e:
        click.echo(str(e))
    except Exception as e:
        click.echo(f"❌ Error during parsing: {e}")


@cli.command()
@click.argument('target')
@click.option('--output-dir', help='Force output directory')
@click.option('--force', is_flag=True, help='Force re-submit even if task already exists.')
def submit(target, output_dir, force):
    """[Async] Submit a PDF for parsing and return immediately. TARGET can be a local PDF path or an arXiv ID.

    For arXiv IDs, the PDF is downloaded automatically if not already cached.
    Idempotent: if a task is already pending/running, checks its current status instead of resubmitting.
    Use 'pp check' later (or again) to retrieve results once done.
    """
    if os.path.isfile(target):
        # Case 1: Local file path
        pdf_path = Path(target)
        final_output_dir = Path(output_dir) if output_dir else pdf_path.parent / "paper"
        click.echo(f"📄 Local PDF detected: {pdf_path}")
    else:
        # Case 2: arXiv ID — resolve, download if needed, then submit
        click.echo(f"🔍 Finding paper: {target}")
        is_id = arxiv_client.search_arxiv(f"id:{target}") if is_arxiv_id(target) else []
        results = is_id if is_id else arxiv_client.search_arxiv(target, max_results=1)

        if not results:
            click.echo("❌ Paper not found on arXiv.")
            return

        paper = results[0]
        click.echo(f"📚 Found: {paper['title']}")

        paper_dir = utils.get_paper_dir(paper['id'])
        pdf_path = paper_dir / "paper.pdf"
        final_output_dir = Path(output_dir) if output_dir else paper_dir

        # Write metadata
        title_path = paper_dir / "title.md"
        title_path.write_text(f"# {paper['title']}\n", encoding='utf-8')
        summary_path = paper_dir / "summary.md"
        if not summary_path.exists():
            summary_path.write_text(f"# Summary: {paper['title']}\n\n## Key Takeaways\n\n- \n", encoding='utf-8')

        # Auto-download PDF if not cached
        if pdf_path.exists():
            click.echo(f"⏭️  PDF already cached: {pdf_path}")
        else:
            click.echo(f"⬇️  Downloading PDF...")
            if not arxiv_client.download_pdf(paper['pdf_url'], pdf_path):
                return

    try:
        result = mineru_client.submit_paper(str(pdf_path), str(final_output_dir), force=force)
        status = result.get("status")

        if status == "done":
            click.echo(f"✅ Already complete! Results in: {result['output_dir']}")
            if "chapters" in result:
                click.echo(f"📚 {result['chapters']} chapters extracted.")
        elif status == "pending":
            batch_id = result.get("batch_id", "—")
            state   = result.get("state", "pending")
            elapsed = result.get("elapsed")
            if elapsed is not None:
                # 来自 check_parse（任务正在运行）
                click.echo(f"⏳ Still processing (state: {state}, {elapsed}s since submission).")
                click.echo(f"   batch_id: {batch_id}")
                click.echo(f"   Run 'pp check {target}' again later.")
            else:
                # 全新提交
                click.echo(f"✅ Submitted!")
                click.echo(f"   batch_id : {batch_id}")
                click.echo(f"   task file: {final_output_dir / TASK_FILENAME}")
                click.echo(f"⏳ Run 'pp check {target}' later to retrieve results.")
    except ValueError as e:
        click.echo(str(e))
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument('target')
@click.option('--output-dir', help='Force output directory')
def check(target, output_dir):
    """[Async] Check the status of a submitted parsing task. TARGET can be a local PDF path or an arXiv ID.

    If parsing is complete, results are downloaded automatically.
    """
    if os.path.isfile(target):
        pdf_path = Path(target)
        final_output_dir = Path(output_dir) if output_dir else pdf_path.parent / "paper"
    else:
        paper_dir = utils.get_paper_dir(target)
        final_output_dir = Path(output_dir) if output_dir else paper_dir

    task_file = final_output_dir / TASK_FILENAME
    if not task_file.exists():
        click.echo(f"❌ No task found in {final_output_dir}.")
        click.echo(f"   Use 'pp submit {target}' to submit for async parsing.")
        return

    click.echo(f"🔍 Checking task status...")
    try:
        result = mineru_client.check_paper(str(task_file))
        if result["status"] == "done":
            click.echo(f"✅ Parsing complete!")
            click.echo(f"📂 Results in: {result['output_dir']}")
            if "chapters" in result:
                click.echo(f"📚 {result['chapters']} chapters extracted.")
        else:
            state = result.get('state', 'unknown')
            elapsed = result.get('elapsed', 0)
            click.echo(f"⏳ Still processing (state: {state}, {elapsed}s since submission).")
            click.echo(f"   Run 'pp check {target}' again later.")
    except Exception as e:
        click.echo(f"❌ Error: {e}")


@cli.command()
@click.argument('query_or_id')
def path(query_or_id):
    """Find the local path of a processed paper."""
    click.echo(f"🔍 Locating paper: {query_or_id}")
    
    is_id = arxiv_client.search_arxiv(f"id:{query_or_id}") if is_arxiv_id(query_or_id) else []
    results = is_id if is_id else arxiv_client.search_arxiv(query_or_id, max_results=1)
    
    if not results:
        click.echo("❌ Paper not found on arXiv.")
        return
    
    paper = results[0]
    paper_dir = utils.get_paper_dir(paper['id'])
    
    if paper_dir.exists() and any(paper_dir.iterdir()):
        click.echo(f"📍 Local path: {paper_dir.absolute()}")
    else:
        click.echo(f"❓ Paper found on arXiv ([{paper['id']}]), but not processed locally yet.")
        click.echo(f"   Use 'pp all \"{paper['id']}\"' to download and parse it.")

@cli.command()
@click.argument('query_or_id')
@click.option('--force', is_flag=True, help='Force re-parsing.')
def all(query_or_id, force):
    """Run full workflow: Search -> Download -> Parse."""
    click.echo(f"🚀 Starting full workflow for: {query_or_id}")
    
    is_id = arxiv_client.search_arxiv(f"id:{query_or_id}") if is_arxiv_id(query_or_id) else []
    results = is_id if is_id else arxiv_client.search_arxiv(query_or_id, max_results=1)
    
    if not results:
        click.echo("❌ Paper not found.")
        return
    
    paper = results[0]
    click.echo(f"📄 Found: {paper['title']}")
    
    paper_dir = utils.get_paper_dir(paper['id'])
    pdf_path = paper_dir / "paper.pdf"
    title_path = paper_dir / "title.md"
    title_path.write_text(f"# {paper['title']}\n", encoding='utf-8')
    
    summary_path = paper_dir / "summary.md"
    if not summary_path.exists():
        summary_path.write_text(f"# Summary: {paper['title']}\n\n## Key Takeaways\n\n- \n", encoding='utf-8')
    
    # 3. Download (with cache check)
    if not force and pdf_path.exists():
        click.echo(f"⏭️  Skipping Download: PDF already exists in {paper_dir}")
    else:
        if not arxiv_client.download_pdf(paper['pdf_url'], pdf_path):
            return
    
    # Reuse parse logic via ctx or just repeat here for simplicity
    if not force and (paper_dir / "markdowns").exists():
        click.echo(f"⏭️  Skipping Parsing: Results already exist in {paper_dir}")
    else:
        click.echo("🔄 Parsing with MinerU API...")
        try:
            mineru_client.parse_paper(str(pdf_path), str(paper_dir))
            click.echo(f"\n🎉 Workflow complete!")
            click.echo(f"📂 Folder: {paper_dir}")
        except ValueError as e:
            click.echo(str(e))
        except Exception as e:
            click.echo(f"❌ Error during parsing: {e}")

if __name__ == '__main__':
    cli()
