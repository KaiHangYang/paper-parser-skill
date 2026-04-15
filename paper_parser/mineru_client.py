import os
import time
import json
import random
import requests
import zipfile
import io
import re
import shutil
from pathlib import Path
from .config import config

TASK_FILENAME = ".parse_task.json"

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
        """Step 3: Poll for completion with exponential backoff + jitter + HTTP retry."""
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        timeout = config.get("MINERU_API_TIMEOUT", 600)
        base_interval = 10   # 初始轮询间隔 (s)
        max_interval = 60    # 最大轮询间隔 (s)
        max_http_retries = 3
        start_time = time.time()
        interval = base_interval

        print(f"[*] Waiting for conversion (Timeout: {timeout}s, initial interval: {base_interval}s)...")
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"❌ MinerU conversion timed out after {timeout} seconds.")

            # HTTP 请求 + 重试
            response = None
            for attempt in range(max_http_retries):
                try:
                    response = requests.get(url, headers=self._get_headers(), timeout=30)
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    if attempt == max_http_retries - 1:
                        raise
                    retry_wait = 2 ** attempt + random.random()
                    print(f"[!] Request failed ({e}), retrying in {retry_wait:.1f}s...")
                    time.sleep(retry_wait)

            result = response.json()
            if result.get("code") != 0:
                raise Exception(f"Status Check Error: {result.get('msg')}")

            extract_results = result["data"].get("extract_result", [])
            if not extract_results:
                # 排队中：指数增大间隔，加 jitter 避免惊群
                jitter = random.uniform(0, 2)
                print(f"[.] Queuing... {int(elapsed)}s elapsed, next check in {interval + jitter:.1f}s")
                time.sleep(interval + jitter)
                interval = min(interval * 1.5, max_interval)
                continue

            file_state = extract_results[0]
            state = file_state.get("state")

            if state == "done":
                print("[+] Conversion finished!")
                return file_state.get("full_zip_url")
            elif state == "failed":
                raise Exception("Conversion failed on server side.")
            else:
                # 处理中：进度已开始，稍微缩短间隔
                interval = max(base_interval, int(interval * 0.8))
                jitter = random.uniform(0, 1)
                print(f"[.] State: {state}, next check in {interval}s... ({int(elapsed)}s elapsed)")
                time.sleep(interval + jitter)

    # -------------------------------------------------------------------------
    # Async / Agent-friendly API
    # -------------------------------------------------------------------------

    def submit_parse(self, pdf_path, output_dir, force=False):
        """Upload PDF and persist task state. Returns immediately without waiting.

        Idempotent - safe to call multiple times:
          - No task file       → upload and submit
          - Status pending/running → skip re-upload, run check_parse once and return
          - Status done        → return immediately (already complete)
          - Status failed      → resubmit (treat as fresh)
          - force=True         → always resubmit regardless of current state
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        task_file = output_path / TASK_FILENAME

        # 如果 task 文件存在，先读取它来决八分支
        if not force and task_file.exists():
            task_data = json.loads(task_file.read_text(encoding="utf-8"))
            status = task_data.get("status", "pending")

            if status == "done":
                print("[+] Task already completed. Skipping submission.")
                return {"status": "done", "output_dir": task_data["output_dir"],
                        "batch_id": task_data["batch_id"]}

            if status in ("pending", "running"):
                elapsed = int(time.time() - task_data["submitted_at"])
                print(f"[.] Task already submitted (batch_id: {task_data['batch_id']}, "
                      f"{elapsed}s ago). Checking current state...")
                # 单次查询并更新任务状态后返回
                return self.check_parse(str(task_file))

            # status == "failed": fall through to resubmit
            print(f"[!] Previous task failed (batch_id: {task_data['batch_id']}). Resubmitting...")

        elif force and task_file.exists():
            old = json.loads(task_file.read_text(encoding="utf-8"))
            print(f"[!] Force resubmit (previous batch_id: {old.get('batch_id')}).")

        # 新提交（首次、failed、force 三种情况）
        batch_id = self.upload_pdf(pdf_path)
        task_data = {
            "batch_id": batch_id,
            "submitted_at": time.time(),
            "pdf_path": str(Path(pdf_path).absolute()),
            "output_dir": str(output_path.absolute()),
            "status": "pending",
        }
        task_file.write_text(json.dumps(task_data, indent=2), encoding="utf-8")
        print(f"[+] Task submitted. batch_id: {batch_id}")
        print(f"[+] Task state saved to: {task_file}")
        return task_data

    def check_parse(self, task_file):
        """Single (non-blocking) status check for a previously submitted task.
        
        Returns a dict with 'status' key:
          - 'done'    → results downloaded and ready in output_dir
          - 'pending' → still queuing/processing, check again later
          - raises Exception on failure
        """
        task_path = Path(task_file)
        if not task_path.exists():
            raise FileNotFoundError(f"Task file not found: {task_file}")

        task_data = json.loads(task_path.read_text(encoding="utf-8"))
        batch_id = task_data["batch_id"]
        output_dir = task_data["output_dir"]
        elapsed = int(time.time() - task_data["submitted_at"])

        # 已完成/失败的情况直接返回
        if task_data.get("status") == "done":
            print("[+] Task already completed.")
            return {"status": "done", "output_dir": output_dir}
        if task_data.get("status") == "failed":
            raise Exception(f"Task was previously marked as failed. batch_id: {batch_id}")

        # 单次状态查询
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        response.raise_for_status()

        result = response.json()
        if result.get("code") != 0:
            raise Exception(f"API Error: {result.get('msg')}")

        extract_results = result["data"].get("extract_result", [])
        if not extract_results:
            print(f"[.] Still queuing... ({elapsed}s since submission)")
            return {"status": "pending", "state": "queuing", "elapsed": elapsed}

        file_state = extract_results[0]
        state = file_state.get("state")

        if state == "done":
            print("[+] Conversion done! Downloading results...")
            zip_url = file_state.get("full_zip_url")
            chapter_count = self.process_results(zip_url, output_dir)

            task_data["status"] = "done"
            task_data["completed_at"] = time.time()
            task_path.write_text(json.dumps(task_data, indent=2), encoding="utf-8")

            return {"status": "done", "chapters": chapter_count, "output_dir": output_dir}

        elif state == "failed":
            task_data["status"] = "failed"
            task_path.write_text(json.dumps(task_data, indent=2), encoding="utf-8")
            raise Exception("Conversion failed on server side.")

        else:
            print(f"[.] Current state: {state} ({elapsed}s since submission)")
            return {"status": "pending", "state": state, "elapsed": elapsed}

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
    """Synchronous: upload → poll (with backoff) → download. For CLI use."""
    client = MinerUClient()
    batch_id = client.upload_pdf(pdf_path)
    zip_url = client.poll_status(batch_id)
    if zip_url:
        return client.process_results(zip_url, output_dir)
    return 0


def submit_paper(pdf_path, output_dir, force=False):
    """Async step 1: idempotent submit. Returns result dict. For agent use."""
    client = MinerUClient()
    return client.submit_parse(pdf_path, output_dir, force=force)


def check_paper(task_file):
    """Async step 2: single (non-blocking) status check. For agent use.
    
    Returns dict with 'status': 'done' | 'pending'.
    When 'done', results are already downloaded to output_dir.
    """
    client = MinerUClient()
    return client.check_parse(task_file)
