import arxiv
from rapidfuzz import fuzz
import requests
from pathlib import Path

def search_arxiv(query, max_results=1):
    """
    Search for papers on arXiv with fuzzy matching support.
    Broadens the search and ranks results by similarity to query.
    """
    client = arxiv.Client()
    
    # 1. Expand the search results pool for better fuzzy matching coverage
    try:
        search = arxiv.Search(
            query=query,
            max_results=max_results * 5,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for r in client.results(search):
            paper_id = r.entry_id.split('/')[-1]
            title = r.title
            
            # 2. Calculate fuzzy similarity score between query and title
            score = fuzz.partial_ratio(query.lower(), title.lower())
            
            results.append({
                'id': paper_id,
                'title': title,
                'pdf_url': r.pdf_url,
                'score': score
            })
        
        # 3. Sort by fuzzy score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # 4. Limit to the requested number of results
        return results[:max_results]
        
    except Exception as e:
        print(f"arXiv search failed: {e}")
        return []

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
