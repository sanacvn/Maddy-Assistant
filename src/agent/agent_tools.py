# agent_tools.py — mendefinisikan tools untuk function calling
import json
from obsidian_rag import search_vault, index_vault
from obsidian_writer import create_note, append_to_daily_journal

# Definisi tools untuk LLM (format OpenAI / Anthropic)
OBSIDIAN_TOOLS = [
    {
        "name": "search_obsidian",
        "description": (
            "Cari informasi dari vault Obsidian pengguna. "
            "Gunakan ini ketika user bertanya tentang catatan pribadi, "
            "ide yang pernah ditulis, atau ingin meringkas topik dari second brain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Pertanyaan atau topik yang dicari"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "write_obsidian_note",
        "description": (
            "Buat catatan baru di Obsidian atau tambah ke daily journal. "
            "Gunakan ini ketika user ingin menyimpan ide, brainstorming, atau log harian."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["new_note", "daily_journal"],
                    "description": "new_note untuk file baru, daily_journal untuk tambah ke jurnal hari ini"
                },
                "title": {"type": "string", "description": "Judul catatan (untuk mode new_note)"},
                "content": {"type": "string", "description": "Isi catatan"},
                "folder": {"type": "string", "description": "Subfolder di vault (opsional)"}
            },
            "required": ["mode", "content"]
        }
    }
]

def execute_obsidian_tool(tool_name: str, tool_input: dict) -> str:
    """Eksekusi tool Obsidian dan kembalikan hasilnya sebagai string."""
    if tool_name == "search_obsidian":
        results = search_vault(tool_input["query"])
        if not results:
            return "Tidak ditemukan catatan yang relevan di vault Obsidian."
        
        output = f"Ditemukan {len(results)} catatan relevan:\n\n"
        for r in results:
            output += f"**{r['title']}** (`{r['filepath']}`)\n"
            output += f"{r['content'][:300]}...\n\n"
        return output
    
    elif tool_name == "write_obsidian_note":
        mode = tool_input["mode"]
        content = tool_input["content"]
        
        if mode == "daily_journal":
            path = append_to_daily_journal(content)
            return f"Berhasil ditambahkan ke daily journal: `{path}`"
        
        elif mode == "new_note":
            title = tool_input.get("title", "Untitled")
            folder = tool_input.get("folder", "")
            path = create_note(title, content, folder)
            return f"Catatan baru dibuat: `{path}`"
    
    return "Tool tidak dikenali."