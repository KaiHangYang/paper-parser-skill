import os
import time
import requests
import zipfile
import io
import re
import shutil
from pathlib import Path
from .config import config

class MinerUClient:
    def __init__(self, token=None, base_url=None):
        self.token = token or config.get("MINERU_API_TOKEN")
        self.base_url = base_url or config.get("MINERU_API_BASE_URL")
        
    def _validate_token(self):
        if not self.token:
            raise ValueError(
                "❌ MinerU API Token is missing!\n"
                "Please configure it in ~/.paper-parser/config.yaml\n"
                "Set the 'MINERU_API_TOKEN' field."
            )

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def upload_pdf(self, pdf_path):
        """Step 1 & 2: Get upload URL and upload PDF."""
        self._validate_token()
        
        url = f"{self.base_url}/file-urls/batch"
        file_name = os.path.basename(pdf_path)
        data = {
            "files": [
                {"name": file_name, "data_id": str(int(time.time()))}
            ],
            "model_version": "vlm"
        }
        
        print(f"[*] Requesting upload URL for {file_name}...")
        response = requests.post(url, headers=self._get_headers(), json=data)
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"API Error: {result.get('msg')}")
            
        upload_url = result["data"]["file_urls"][0]
        batch_id = result["data"]["batch_id"]
        
        print(f"[*] Uploading {pdf_path}...")
        with open(pdf_path, "rb") as f:
            resp = requests.put(upload_url, data=f)
            resp.raise_for_status()
        print("[+] Upload successful.")
        
        return batch_id

    def poll_status(self, batch_id):
        """Step 3: Poll for completion."""
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        timeout = config.get("MINERU_API_TIMEOUT", 600)
        start_time = time.time()
        
        print(f"[*] Waiting for conversion to complete (Timeout: {timeout}s)...")
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"❌ MinerU conversion timed out after {timeout} seconds.")

            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"Status Check Error: {result.get('msg')}")
                
            extract_results = result["data"].get("extract_result", [])
            if not extract_results:
                print(f"[.] Still processing (queueing)... {int(elapsed)}s elapsed")
                time.sleep(5)
                continue
                
            file_state = extract_results[0]
            state = file_state.get("state")
            
            if state == "done":
                print("[+] Conversion finished!")
                return file_state.get("full_zip_url")
            elif state == "failed":
                raise Exception("Conversion failed on server side.")
            else:
                print(f"[.] Current state: {state}. Polling in 5s... ({int(elapsed)}s elapsed)")
                time.sleep(5)

    def process_results(self, zip_url, output_dir):
        """Step 4: Download and process result ZIP."""
        print(f"[*] Downloading results...")
        response = requests.get(zip_url)
        response.raise_for_status()
        
        paper_dir = Path(output_dir)
        paper_dir.mkdir(parents=True, exist_ok=True)
        markdowns_dir = paper_dir / "markdowns"
        markdowns_dir.mkdir(exist_ok=True)
        images_dir = markdowns_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Temp directory for extraction
        temp_dir = paper_dir / "_temp_mineru"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        temp_images_dir = temp_dir / "images"
        temp_images_dir.mkdir()
        
        md_content = ""
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            for name in z.namelist():
                if name.endswith("full.md"):
                    md_content = z.read(name).decode("utf-8")
                elif "images/" in name and not name.endswith("/"):
                    filename = os.path.basename(name)
                    if filename:
                        with z.open(name) as source, open(temp_images_dir / filename, "wb") as target:
                            shutil.copyfileobj(source, target)

        if not md_content:
            shutil.rmtree(temp_dir)
            raise Exception("Error: Could not find 'full.md' in the result ZIP.")
        
        # Process images and references
        processed_md = self._process_images(md_content, temp_images_dir, images_dir)
        
        # Split into chapters
        chapter_count = self._split_chapters(processed_md, markdowns_dir)
        
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"[+] Done! {chapter_count} chapters saved to 'markdowns/'. Images saved to 'images/'.")
        return chapter_count

    def _process_images(self, md_content, temp_images_dir, final_images_dir):
        md_img_pattern = re.compile(r'!\[([^\]]*)\]\(images/([^)]+)\)')
        html_img_pattern = re.compile(r'<img[^>]+src="images/([^"]+)"[^>]*>')
        
        unique_refs = []
        for match in md_img_pattern.finditer(md_content):
            if match.group(2) not in unique_refs:
                unique_refs.append(match.group(2))
        for match in html_img_pattern.finditer(md_content):
            if match.group(1) not in unique_refs:
                unique_refs.append(match.group(1))
                
        mapping = {}
        for i, old_name in enumerate(unique_refs, 1):
            new_name = f"{i}.jpg"
            old_path = temp_images_dir / old_name
            new_path = final_images_dir / new_name
            
            if old_path.exists():
                shutil.move(str(old_path), str(new_path))
                mapping[old_name] = new_name

        def md_replace(match):
            alt, name = match.groups()
            return f"![{alt}](images/{mapping.get(name, name)})"
            
        def html_replace(match):
            name = match.group(1)
            return f'<img src="images/{mapping.get(name, name)}" />'

        md_content = md_img_pattern.sub(md_replace, md_content)
        md_content = html_img_pattern.sub(html_replace, md_content)
        return md_content

    def _split_chapters(self, md_content, output_folder):
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        headers = [(m.start(), len(m.group(1)), m.group(2).strip()) for m in header_pattern.finditer(md_content)]

        if not headers:
            (output_folder / "00_Complete.md").write_text(md_content.strip() + '\n', encoding='utf-8')
            return 1

        for i, (start, level, title) in enumerate(headers):
            end = headers[i + 1][0] if i + 1 < len(headers) else len(md_content)
            content = md_content[start:end].strip()
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            safe_title = re.sub(r'\s+', '_', safe_title)[:80]
            filename = f"{i+1:02d}_{safe_title}.md"
            (output_folder / filename).write_text(content + '\n', encoding='utf-8')
        
        return len(headers)

def parse_paper(pdf_path, output_dir):
    """Convenience function to run the full MinerU workflow."""
    client = MinerUClient()
    batch_id = client.upload_pdf(pdf_path)
    zip_url = client.poll_status(batch_id)
    if zip_url:
        return client.process_results(zip_url, output_dir)
    return 0
