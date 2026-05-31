from pathlib import Path
from datetime import datetime
import frontmatter

VAULT_PATH = "/path/to/obsidian/vault"

def create_note(title: str, content: str, folder: str = "") -> str:
    """Buat file .md baru di vault Obsidian."""
    safe_title = title.replace("/", "-").replace(":", "-")
    target_dir = Path(VAULT_PATH) / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = target_dir / f"{safe_title}.md"
    
    # Buat dengan frontmatter standar Obsidian
    post = frontmatter.Post(
        content,
        title=title,
        created=datetime.now().isoformat(),
        tags=[]
    )
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
    
    return str(filepath.relative_to(VAULT_PATH))

def append_to_note(filepath_rel: str, text: str) -> bool:
    """Tambah teks ke akhir catatan yang sudah ada."""
    filepath = Path(VAULT_PATH) / filepath_rel
    
    if not filepath.exists():
        return False
    
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"\n{text}")
    
    return True

def append_to_daily_journal(text: str) -> str:
    """Tambah entri ke daily journal hari ini."""
    today = datetime.now().strftime("%Y-%m-%d")
    journal_path = f"Journal/{today}.md"
    full_path = Path(VAULT_PATH) / journal_path
    
    if not full_path.exists():
        create_note(today, f"# {today}\n\n", folder="Journal")
    
    timestamp = datetime.now().strftime("%H:%M")
    append_to_note(journal_path, f"\n- {timestamp} {text}")
    
    return journal_path