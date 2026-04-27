#!/usr/bin/env python3
"""
Knowledge Base Site Generator

Generates a static HTML site from markdown files with a sidebar navigation.
Uses a JSON data file for incremental updates and quick regeneration.
"""

import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
import markdown


DATA_FILE = "data.json"
SITE_DIR = "site"
SOURCE_DIR = "."


def scan_directory(base_path: Path, ignore_dirs: set = None) -> dict:
    """Recursively scan directory for markdown files and build tree structure."""
    if ignore_dirs is None:
        ignore_dirs = {"site", ".git", "__pycache__", "venv", ".venv", "node_modules"}
    
    structure = {"folders": {}, "files": []}
    
    for item in sorted(base_path.iterdir()):
        if item.name.startswith(".") or item.name in ignore_dirs:
            continue
        
        if item.is_dir():
            sub_structure = scan_directory(item, ignore_dirs)
            if sub_structure["folders"] or sub_structure["files"]:
                structure["folders"][item.name] = {
                    "path": str(item),
                    "name": format_name(item.name),
                    "content": sub_structure
                }
        elif item.suffix == ".md":
            title = extract_title(item)
            structure["files"].append({
                "path": str(item),
                "name": item.stem,
                "title": title,
                "mtime": item.stat().st_mtime
            })
    
    return structure


def format_name(name: str) -> str:
    """Convert folder/file names to display names."""
    name = re.sub(r"^\d+-", "", name)
    name = name.replace("-", " ").replace("_", " ")
    return name.title()


def extract_title(file_path: Path) -> str:
    """Extract title from markdown file (first H1 heading)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
                if line and not line.startswith("#"):
                    break
        return format_name(file_path.stem)
    except Exception:
        return format_name(file_path.stem)


def load_data() -> dict:
    """Load existing data.json or return empty structure."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"meta": {}, "structure": {}}


def save_data(data: dict):
    """Save data to JSON file."""
    data["meta"]["generated"] = datetime.now().isoformat()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def convert_markdown_to_html(md_path: str, html_path: str):
    """Convert a markdown file to HTML with styling."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    md = markdown.Markdown(extensions=[
        "tables",
        "fenced_code",
        "codehilite",
        "toc",
        "nl2br"
    ])
    html_content = md.convert(md_content)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{extract_title(Path(md_path))}</title>
<style>
:root {{
  --bg: #0f1117;
  --card-bg: #1a1d27;
  --border: #2a2d3a;
  --text: #e1e4ed;
  --text-muted: #8b8fa3;
  --accent-blue: #60a5fa;
  --accent-green: #34d399;
  --accent-purple: #a78bfa;
  --accent-orange: #fb923c;
  --accent-cyan: #22d3ee;
  --code-bg: #1e2130;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.7;
  padding: 2rem 3rem;
  max-width: 900px;
  margin: 0 auto;
}}
h1, h2, h3, h4, h5, h6 {{
  color: var(--text);
  margin: 1.5rem 0 0.75rem 0;
  font-weight: 600;
}}
h1 {{
  font-size: 2rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--accent-blue);
  margin-bottom: 1.5rem;
}}
h2 {{
  font-size: 1.5rem;
  color: var(--accent-cyan);
  margin-top: 2rem;
}}
h3 {{
  font-size: 1.25rem;
  color: var(--accent-purple);
}}
p {{ margin: 0.75rem 0; }}
a {{ color: var(--accent-blue); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{
  font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
  font-size: 0.85em;
  background: var(--code-bg);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}}
pre {{
  background: var(--code-bg);
  padding: 1rem;
  border-radius: 8px;
  overflow-x: auto;
  margin: 1rem 0;
  border: 1px solid var(--border);
}}
pre code {{
  background: none;
  padding: 0;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0;
}}
th, td {{
  border: 1px solid var(--border);
  padding: 0.6rem 1rem;
  text-align: left;
}}
th {{
  background: var(--card-bg);
  color: var(--accent-cyan);
  font-weight: 600;
}}
tr:nth-child(even) {{ background: rgba(26, 29, 39, 0.5); }}
ul, ol {{ margin: 0.75rem 0; padding-left: 1.5rem; }}
li {{ margin: 0.3rem 0; }}
blockquote {{
  border-left: 4px solid var(--accent-purple);
  padding-left: 1rem;
  margin: 1rem 0;
  color: var(--text-muted);
  font-style: italic;
}}
hr {{
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}}
strong {{ color: var(--accent-orange); }}
.codehilite {{ background: var(--code-bg); border-radius: 8px; }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""
    
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def get_folder_icon(name: str) -> str:
    """Get appropriate icon for folder based on name."""
    icons = {
        "databases": "🗄️",
        "distributed": "🔗",
        "messaging": "📨",
        "caching": "⚡",
        "apis": "🔌",
        "scalability": "📈",
        "reliability": "🛡️",
        "sre": "🛡️",
        "system": "🏗️",
        "design": "🏗️",
    }
    name_lower = name.lower()
    for key, icon in icons.items():
        if key in name_lower:
            return icon
    return "📁"


def get_file_icon(name: str) -> str:
    """Get appropriate icon for file based on name."""
    icons = {
        "readme": "📋",
        "glossary": "📖",
        "index": "📋",
        "overview": "📄",
        "deep-dive": "🔬",
        "comparison": "⚖️",
        "faq": "❓",
    }
    name_lower = name.lower()
    for key, icon in icons.items():
        if key in name_lower:
            return icon
    return "📄"


def generate_tree_html(structure: dict, base_path: str = "") -> str:
    """Generate HTML tree structure for sidebar."""
    html_parts = ["<ul>"]
    
    for folder_key, folder_data in sorted(structure.get("folders", {}).items()):
        folder_name = folder_data.get("name", folder_key)
        icon = get_folder_icon(folder_key)
        content = folder_data.get("content", {})
        file_count = count_files(content)
        
        html_parts.append(f'''<li>
<div class="folder" onclick="toggle(this)">
<span class="arrow">&#9660;</span>
<span class="fi">{icon}</span>
<span class="fl">{folder_name}</span>
<span class="badge">{file_count}</span>
</div>''')
        
        sub_html = generate_tree_html(content, f"{base_path}/{folder_key}" if base_path else folder_key)
        html_parts.append(sub_html)
        html_parts.append("</li>")
    
    for file_data in structure.get("files", []):
        file_name = file_data.get("name", "")
        title = file_data.get("title", file_name)
        html_path = file_data.get("path", "").replace(".md", ".html")
        icon = get_file_icon(file_name)
        
        html_parts.append(f'''<li>
<div class="leaf" onclick="nav(this,'{html_path}')">
<span class="li">{icon}</span>
<span class="ll">{title}</span>
</div>
</li>''')
    
    html_parts.append("</ul>")
    return "\n".join(html_parts)


def count_files(structure: dict) -> int:
    """Count total files in structure."""
    count = len(structure.get("files", []))
    for folder_data in structure.get("folders", {}).values():
        count += count_files(folder_data.get("content", {}))
    return count


def generate_index_html(structure: dict) -> str:
    """Generate the main index.html with sidebar navigation."""
    tree_html = generate_tree_html(structure)
    total_files = count_files(structure)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knowledge Base</title>
<style>
:root {{
  --bg: #0f1117;
  --sidebar-bg: #13151e;
  --card-bg: #1a1d27;
  --border: #2a2d3a;
  --text: #e1e4ed;
  --text-muted: #8b8fa3;
  --accent-blue: #60a5fa;
  --accent-green: #34d399;
  --accent-purple: #a78bfa;
  --accent-orange: #fb923c;
  --accent-pink: #f472b6;
  --accent-cyan: #22d3ee;
  --accent-yellow: #fbbf24;
  --hover-bg: #1e2130;
  --active-bg: #1a2744;
  --indent: 1.4rem;
  --sidebar-w: 340px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ height: 100%; overflow: hidden; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  display: flex;
  flex-direction: column;
}}
code {{ font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace; font-size: 0.85em; }}
a {{ color: var(--accent-blue); text-decoration: none; }}
.layout {{ display: flex; flex: 1; overflow: hidden; }}

.sidebar {{
  width: var(--sidebar-w); min-width: var(--sidebar-w);
  background: var(--sidebar-bg); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}}
.sidebar-header {{
  padding: 0.9rem 1rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}
.sidebar-header h1 {{
  font-size: 1.1rem;
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}}
.sidebar-header .count {{
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-left: auto;
}}
.sidebar-actions {{
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  display: flex;
  gap: 0.3rem;
}}
.sidebar-actions button {{
  background: var(--card-bg);
  border: 1px solid var(--border);
  color: var(--text-muted);
  font-family: inherit;
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
}}
.sidebar-actions button:hover {{
  color: var(--text);
  border-color: var(--accent-blue);
}}
.sidebar-tree {{
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 0.5rem 0;
}}
.sidebar-tree::-webkit-scrollbar {{ width: 5px; }}
.sidebar-tree::-webkit-scrollbar-track {{ background: transparent; }}
.sidebar-tree::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}

.tree ul {{ list-style: none; padding-left: 0; }}
.tree ul ul {{ padding-left: var(--indent); }}
.folder {{
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.7rem;
  font-weight: 600;
  font-size: 0.82rem;
  transition: background 0.1s;
}}
.folder:hover {{ background: var(--hover-bg); }}
.folder .arrow {{
  display: inline-block;
  width: 0.8rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.6rem;
  transition: transform 0.12s;
  flex-shrink: 0;
}}
.folder.collapsed .arrow {{ transform: rotate(-90deg); }}
.folder .fi {{ flex-shrink: 0; font-size: 0.85rem; }}
.folder .fl {{
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--accent-cyan);
}}
.folder .badge {{
  font-size: 0.55rem;
  padding: 0px 5px;
  border-radius: 3px;
  font-weight: 600;
  flex-shrink: 0;
  background: #1a3327;
  color: var(--accent-green);
  font-family: 'SF Mono', monospace;
}}
.folder.collapsed + ul {{ display: none; }}
.leaf {{
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.7rem;
  transition: background 0.1s;
  cursor: pointer;
}}
.leaf:hover {{ background: var(--hover-bg); }}
.leaf.active {{ background: var(--active-bg); }}
.leaf .li {{ flex-shrink: 0; font-size: 0.78rem; width: 1rem; text-align: center; }}
.leaf .ll {{
  font-size: 0.82rem;
  color: var(--accent-blue);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}}
.leaf .ll:hover {{ color: var(--accent-cyan); }}

.resize-handle {{
  width: 4px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.15s;
  flex-shrink: 0;
}}
.resize-handle:hover, .resize-handle.dragging {{ background: var(--accent-blue); }}

.content {{
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg);
}}
.content-bar {{
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--card-bg);
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
  min-height: 2.2rem;
}}
.content-bar .path {{
  font-family: 'SF Mono', monospace;
  font-size: 0.78rem;
  color: var(--text-muted);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.content-bar .open-ext {{
  font-size: 0.72rem;
  color: var(--text-muted);
  border: 1px solid var(--border);
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
  flex-shrink: 0;
}}
.content-bar .open-ext:hover {{
  color: var(--accent-blue);
  border-color: var(--accent-blue);
}}
.content iframe {{
  flex: 1;
  border: none;
  background: var(--bg);
}}
.content .welcome {{
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.8rem;
  color: var(--text-muted);
}}
.welcome .big {{ font-size: 3rem; }}
.welcome p {{ font-size: 0.9rem; }}
.welcome .hint {{ font-size: 0.78rem; color: var(--border); }}
</style>
</head>
<body>
<div class="layout">
  <div class="sidebar" id="sidebar">
    <div class="sidebar-header">
      <h1>Knowledge Base</h1>
      <span class="count">{total_files} docs</span>
    </div>
    <div class="sidebar-actions">
      <button onclick="expandAll()">Expand All</button>
      <button onclick="collapseAll()">Collapse All</button>
    </div>
    <div class="sidebar-tree">
      <div class="tree">
{tree_html}
      </div>
    </div>
  </div>
  <div class="resize-handle" id="resizeHandle"></div>
  <div class="content" id="content">
    <div class="content-bar" id="contentBar" style="display:none;">
      <span class="path" id="contentPath"></span>
      <a class="open-ext" id="openExt" href="#" target="_blank">Open in new tab &#8599;</a>
    </div>
    <div class="welcome" id="welcome">
      <span class="big">📚</span>
      <p>Select a document from the sidebar</p>
      <span class="hint">Click any file to view its contents</span>
    </div>
    <iframe id="viewer" style="display:none;"></iframe>
  </div>
</div>
<script>
function toggle(el) {{ el.classList.toggle('collapsed'); }}
function expandAll() {{ document.querySelectorAll('.folder.collapsed').forEach(f => f.classList.remove('collapsed')); }}
function collapseAll() {{ document.querySelectorAll('.folder:not(.collapsed)').forEach(f => f.classList.add('collapsed')); }}

function nav(el, url) {{
  document.querySelectorAll('.leaf.active').forEach(l => l.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('welcome').style.display = 'none';
  var f = document.getElementById('viewer');
  f.style.display = 'block';
  f.src = url;
  var b = document.getElementById('contentBar');
  b.style.display = 'flex';
  document.getElementById('contentPath').textContent = url;
  document.getElementById('openExt').href = url;
}}

(function() {{
  var h = document.getElementById('resizeHandle');
  var s = document.getElementById('sidebar');
  var d = false;
  h.addEventListener('mousedown', function(e) {{
    d = true;
    h.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  }});
  document.addEventListener('mousemove', function(e) {{
    if (!d) return;
    var w = Math.max(200, Math.min(600, e.clientX));
    s.style.width = w + 'px';
    s.style.minWidth = w + 'px';
  }});
  document.addEventListener('mouseup', function() {{
    if (d) {{
      d = false;
      h.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }}
  }});
}})();
</script>
</body>
</html>
'''


def process_files(structure: dict, src_base: str, dest_base: str):
    """Process all markdown files and convert to HTML."""
    for file_data in structure.get("files", []):
        md_path = file_data["path"]
        html_path = os.path.join(dest_base, md_path.replace(".md", ".html"))
        convert_markdown_to_html(md_path, html_path)
        print(f"  Converted: {md_path}")
    
    for folder_data in structure.get("folders", {}).values():
        process_files(folder_data.get("content", {}), src_base, dest_base)


def main():
    print("Knowledge Base Site Generator")
    print("=" * 40)
    
    print("\n[1/4] Scanning directory structure...")
    structure = scan_directory(Path(SOURCE_DIR))
    
    data = {"meta": {}, "structure": structure}
    
    print("[2/4] Saving data.json...")
    save_data(data)
    
    print("[3/4] Creating site directory...")
    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(SITE_DIR)
    
    print("[4/4] Generating HTML files...")
    process_files(structure, SOURCE_DIR, SITE_DIR)
    
    index_html = generate_index_html(structure)
    with open(os.path.join(SITE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("  Generated: index.html")
    
    total = count_files(structure)
    print(f"\nDone! Generated {total} pages in '{SITE_DIR}/'")
    print(f"Open {SITE_DIR}/index.html in a browser to view.")


if __name__ == "__main__":
    main()
