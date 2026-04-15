import arxiv
from rapidfuzz import fuzz
import requests
import socket
from pathlib import Path

def _make_client(**kwargs):
    """Create an arxiv Client with sensible defaults."""
    return arxiv.Client(
        delay_seconds=3.0,  # respect arXiv rate limits (avoid HTTP 429)
        num_retries=3,
        **kwargs,
    )

def get_by_id(arxiv_id):
    """Fetch a single paper by its arXiv ID. Returns a list of 0 or 1 results.
    
    Uses the id_list API parameter — fast, precise, and doesn't count against
    the search rate limit the same way full-text queries do.
    """
    client = _make_client()
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(30)
        search = arxiv.Search(id_list=[arxiv_id.strip()])
        results = []
        for r in client.results(search):
            paper_id = r.entry_id.split('/')[-1]
            results.append({
                'id': paper_id,
                'title': r.title,
                'pdf_url': r.pdf_url,
                'score': 100,
            })
        return results
    except socket.timeout:
        print("❌ arXiv ID lookup timed out (30s). Check your network/proxy settings.")
        return []
    except Exception as e:
        print(f"❌ arXiv ID lookup failed: {e}")
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)

def search_arxiv(query, max_results=1):
    """
    Search for papers on arXiv with fuzzy matching support.
    Broadens the search and ranks results by similarity to query.
    """
    client = _make_client(page_size=max_results * 5)
    
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(30)

        search = arxiv.Search(
            query=query,
            max_results=max_results * 5,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for r in client.results(search):
            paper_id = r.entry_id.split('/')[-1]
            title = r.title
            score = fuzz.partial_ratio(query.lower(), title.lower())
            
            results.append({
                'id': paper_id,
                'title': title,
                'pdf_url': r.pdf_url,
                'score': score
            })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_results]
        
    except socket.timeout:
        print("❌ arXiv search timed out (30s). Check your network/proxy settings.")
        return []
    except Exception as e:
        print(f"❌ arXiv search failed: {e}")
        return []
    finally:
        socket.setdefaulttimeout(old_timeout)

def download_pdf(pdf_url, output_path):
    """Download PDF from URL to local path."""
    print(f"📥 Downloading: {pdf_url}")
    try:
        response = requests.get(pdf_url, stream=True, timeout=60)
        response.raise_for_status()
        
        # Ensure parent directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"✅ PDF saved: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False
