import time
import json
import requests
import threading
import urllib.robotparser as robotparser
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from concurrent.futures import ThreadPoolExecutor
import http.server
import socketserver
import os

# ---------------- CONFIG ----------------
USER_AGENT = "ThreadCrawl/2.1.5 (+https://example.com/bot-info)"
CRAWL_DELAY = 0.1  # fixed delay, no slider
MAX_PAGES_PER_SITE = 50
OUTPUT_FILE = "src/results.json"
MAX_THREADS = 50
# ----------------------------------------

headers = {"User-Agent": USER_AGENT}

pause_flag = threading.Event()
stop_flag = threading.Event()

results_lock = threading.Lock()
log_lock = threading.Lock()

# ---------------- Web Host ----------------
class WebHostThread(threading.Thread):
    def __init__(self, port=8000):
        super().__init__(daemon=True)
        self.port = port
        self.httpd = None

    def run(self):
        os.chdir("src")
        handler = http.server.SimpleHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", self.port), handler)
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()

# ---------------- Helpers ----------------
def load_sites(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def get_robot_parser(base_url):
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        pass
    return rp

def extract_metadata(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description = None
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    return title, description

# ---------------- Crawl ----------------
def crawl_site(start_url, results, update_gui=None, log_func=None):
    rp = get_robot_parser(start_url)
    domain = urlparse(start_url).netloc
    visited = set()
    queue = [start_url]

    while queue and len(visited) < MAX_PAGES_PER_SITE:
        if stop_flag.is_set():
            break
        pause_flag.wait()

        url = queue.pop(0)
        if url in visited:
            continue
        if not rp.can_fetch(USER_AGENT, url):
            log_func and log_func(f"⛔ Blocked by robots.txt: {url}")
            continue

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            log_func and log_func(f"❌ Failed: {url}")
            continue

        visited.add(url)
        title, description = extract_metadata(response.text)

        with results_lock:
            results.append({"url": url, "title": title, "description": description})

        update_gui and update_gui(url, len(results))
        log_func and log_func(f"✅ Crawled: {url}")

        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True):
            absolute = urljoin(url, link["href"])
            parsed = urlparse(absolute)
            if parsed.scheme in ("http", "https") and parsed.netloc == domain and absolute not in visited:
                queue.append(absolute)

        time.sleep(CRAWL_DELAY)

# ---------------- GUI ----------------
class CrawlerGUI:
    def __init__(self, root):
        self.root = root
        root.title("ThreadCrawler")
        root.geometry("700x550")

        self.results = []
        self.sites = []
        self.running = False
        self.timer = 0

        self.web_host = None
        self.host_running = False

        # Buttons
        tk.Button(root, text="Load Sites", command=self.load_sites).pack(pady=4)
        self.start_btn = tk.Button(root, text="Start Crawl", command=self.start_crawl, state="disabled")
        self.start_btn.pack(pady=4)
        self.pause_btn = tk.Button(root, text="Pause", command=self.pause_resume, state="disabled")
        self.pause_btn.pack(pady=4)
        self.stop_btn = tk.Button(root, text="Stop", command=self.stop_crawl, state="disabled")
        self.stop_btn.pack(pady=4)

        self.host_btn = tk.Button(root, text="Start Web Host", command=self.toggle_host)
        self.host_btn.pack(pady=6)

        self.status = tk.Label(root, text="Status: Idle")
        self.status.pack()
        self.timer_label = tk.Label(root, text="Time: 0s")
        self.timer_label.pack()

        self.log_box = scrolledtext.ScrolledText(root, width=85, height=16, state="disabled")
        self.log_box.pack(pady=8)

        self.update_timer()

    # ---------------- Host ----------------
    def toggle_host(self):
        if not self.host_running:
            self.web_host = WebHostThread()
            self.web_host.start()
            self.host_running = True
            self.host_btn.config(text="Stop Web Host")
            self.log("🌐 Hosting src/index.html at http://localhost:8000")
        else:
            self.web_host.stop()
            self.host_running = False
            self.host_btn.config(text="Start Web Host")
            self.log("🛑 Web host stopped")

    # ---------------- Crawl GUI ----------------
    def load_sites(self):
        file = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file:
            self.sites = load_sites(file)
            self.start_btn.config(state="normal")
            messagebox.showinfo("Loaded", f"{len(self.sites)} sites loaded")

    def start_crawl(self):
        pause_flag.set()
        stop_flag.clear()
        self.running = True
        self.timer = 0
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        threading.Thread(target=self.crawl_all, daemon=True).start()

    def crawl_all(self):
        self.log(f"▶ Starting crawl ({MAX_THREADS} threads)")
        with ThreadPoolExecutor(MAX_THREADS) as ex:
            futures = [ex.submit(crawl_site, s, self.results, self.update_status, self.log) for s in self.sites]
            for f in futures:
                try:
                    f.result()
                except Exception as e:
                    self.log(f"❌ {e}")

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        self.running = False
        self.status.config(text=f"Finished ({len(self.results)} pages)")
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.log("📝 Results saved")

    def pause_resume(self):
        if pause_flag.is_set():
            pause_flag.clear()
            self.pause_btn.config(text="Resume")
            self.status.config(text="Paused")
            self.log("⏸ Paused")
        else:
            pause_flag.set()
            self.pause_btn.config(text="Pause")
            self.log("▶ Resumed")

    def stop_crawl(self):
        stop_flag.set()
        pause_flag.set()
        self.status.config(text="Stopping...")
        self.log("🛑 Stopping crawl")

    def update_status(self, url, count):
        self.status.config(text=f"Crawling: {count} pages")

    def log(self, msg):
        with log_lock:
            self.log_box.config(state="normal")
            self.log_box.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
            self.log_box.see(tk.END)
            self.log_box.config(state="disabled")

    def update_timer(self):
        if self.running and pause_flag.is_set():
            self.timer += 1
            self.timer_label.config(text=f"Time: {self.timer}s")
        self.root.after(1000, self.update_timer)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    root = tk.Tk()
    CrawlerGUI(root)
    root.mainloop()
