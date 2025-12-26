import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext, filedialog, Menu
import sqlite3
import pyperclip
from datetime import datetime
import os
import random
import shutil
import winreg

# --- Theme Configurations ---
THEMES = {
    "Dark": {
        "BG_COLOR": "#121212",
        "FRAME_BG": "#1e1e1e",
        "TEXT_COLOR": "#ffffff",
        "ACCENT_COLOR": "#333333",
        "SELECT_BG": "#1976d2"
    },
    "Light": {
        "BG_COLOR": "#f0f0f0",
        "FRAME_BG": "#ffffff",
        "TEXT_COLOR": "#000000",
        "ACCENT_COLOR": "#e0e0e0",
        "SELECT_BG": "#2196f3"
    }
}

def detect_windows_dark_mode():
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except:
        return True

def set_theme(theme_name):
    set_setting("selected_theme", theme_name)

    effective = "Dark" if (theme_name == "System" and detect_windows_dark_mode()) or theme_name == "Dark" else "Light"
    colors = THEMES[effective]

    root.configure(background=colors["BG_COLOR"])
    f1.configure(background=colors["FRAME_BG"], foreground=colors["TEXT_COLOR"])
    f2.configure(background=colors["FRAME_BG"], foreground=colors["TEXT_COLOR"])

    apply_colors_recursive(root, colors)

    listbox.configure(background=colors["ACCENT_COLOR"], foreground=colors["TEXT_COLOR"],
                      selectbackground=colors["SELECT_BG"])
    status_frame.configure(background="#2d2d2d")
    status_label.configure(background="#2d2d2d", foreground="#aaaaaa")

    style.configure("TCombobox", fieldbackground=colors["ACCENT_COLOR"],
                    background=colors["ACCENT_COLOR"], foreground=colors["TEXT_COLOR"],
                    arrowcolor=colors["TEXT_COLOR"])

    # Force layout refresh after theme change
    root.update_idletasks()
    current_geom = root.geometry()
    root.geometry(f"{root.winfo_width()+1}x{root.winfo_height()}")
    root.geometry(current_geom)

def apply_colors_recursive(widget, colors):
    try:
        if isinstance(widget, tk.Label):
            widget.configure(background=colors["FRAME_BG"], foreground=colors["TEXT_COLOR"])
        elif isinstance(widget, tk.Entry):
            widget.configure(background=colors["ACCENT_COLOR"], foreground=colors["TEXT_COLOR"],
                             insertbackground=colors["TEXT_COLOR"])
        elif isinstance(widget, scrolledtext.ScrolledText):
            widget.configure(background=colors["ACCENT_COLOR"], foreground=colors["TEXT_COLOR"],
                             insertbackground=colors["TEXT_COLOR"])
            for child in widget.winfo_children():
                if child.winfo_class() == 'Text':
                    child.configure(background=colors["ACCENT_COLOR"], foreground=colors["TEXT_COLOR"],
                                    insertbackground=colors["TEXT_COLOR"])
        elif isinstance(widget, tk.Checkbutton):
            widget.configure(background=colors["FRAME_BG"], foreground=colors["TEXT_COLOR"],
                             selectcolor=colors["ACCENT_COLOR"], activebackground=colors["FRAME_BG"])
        elif isinstance(widget, (tk.Frame, tk.LabelFrame)):
            widget.configure(background=colors["FRAME_BG"])
    except tk.TclError:
        pass

    if hasattr(widget, 'winfo_children'):
        for child in widget.winfo_children():
            apply_colors_recursive(child, colors)

# --- Database ---
def init_db():
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS prompts
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     title TEXT UNIQUE,
                     category TEXT,
                     tags TEXT,
                     positive TEXT,
                     negative TEXT,
                     last_used TEXT,
                     favorite INTEGER DEFAULT 0)''')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    if not cursor.fetchone():
        cursor.execute('''CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('selected_theme', 'System')")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_category', 'Pony')")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('window_geometry', '900x1100+300+100')")
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key, value):
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_unique_categories():
    try:
        conn = sqlite3.connect("prompt_vault.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM prompts")
        db_cats = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
    except:
        db_cats = []
    defaults = ["Juggernaut", "Pony", "IPA Subgraph", "Upscale", "Video Gen"]
    return sorted(list(set(db_cats + defaults)))

def refresh_dropdowns():
    new_cats = get_unique_categories()
    cat_combo['values'] = new_cats
    f_menu['values'] = ["All", "Favorites"] + new_cats
    last_cat = get_setting("last_category")
    if last_cat and last_cat in new_cats:
        cat_combo.set(last_cat)

def apply_pony_formatting(pos, neg):
    if pony_var.get():
        pos_prefix = "score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, "
        if not pos.lower().startswith("score_9"):
            pos = pos_prefix + pos
        neg_prefix = "score_6, score_5, score_4, low quality, worst quality, bad anatomy, bad hands, missing fingers, "
        if not neg.lower().startswith("score_6"):
            neg = neg_prefix + neg
    if realism_var.get():
        pos += ", source_real, realistic, photo, photorealistic"
        neg += ", source_pony, source_anime, source_cartoon, drawing, illustration"
    return pos.strip(", "), neg.strip(", ")

# --- Prompt Functions ---
def save_prompt():
    title = title_entry.get().strip()
    cat = cat_combo.get().strip()
    tags = tags_entry.get().strip().lower()
    pos = pos_entry.get("1.0", tk.END).strip()
    neg = neg_entry.get("1.0", tk.END).strip()
    pos, neg = apply_pony_formatting(pos, neg)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not title or not pos or not cat:
        messagebox.showwarning("Input Error", "Title, Category, and Positive Prompt are required.")
        return

    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO prompts (title, category, tags, positive, negative, last_used) VALUES (?, ?, ?, ?, ?, ?)",
                   (title, cat, tags, pos, neg, now))
    conn.commit()
    conn.close()
    set_setting("last_category", cat)
    messagebox.showinfo("Success", f"'{title}' saved/updated!")
    clear_fields()
    load_prompts()
    refresh_dropdowns()

def clear_fields():
    title_entry.delete(0, tk.END)
    tags_entry.delete(0, tk.END)
    pos_entry.delete("1.0", tk.END)
    neg_entry.delete("1.0", tk.END)

def load_selected(event=None):
    try:
        idx = listbox.curselection()[0]
        text = listbox.get(idx)
        title = text.split("] ", 1)[1].lstrip("★ ")
        conn = sqlite3.connect("prompt_vault.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, category, tags, positive, negative FROM prompts WHERE title=?", (title,))
        row = cursor.fetchone()
        conn.close()
        if row:
            clear_fields()
            title_entry.insert(0, row[0])
            cat_combo.set(row[1])
            tags_entry.insert(0, row[2])
            pos_entry.insert("1.0", row[3])
            neg_entry.insert("1.0", row[4])
    except:
        pass

def copy_positive():
    pos, _ = apply_pony_formatting(pos_entry.get("1.0", tk.END).strip(), "")
    pyperclip.copy(pos)
    messagebox.showinfo("Copied", "Positive prompt copied!")

def copy_negative():
    _, neg = apply_pony_formatting("", neg_entry.get("1.0", tk.END).strip())
    pyperclip.copy(neg)
    messagebox.showinfo("Copied", "Negative prompt copied!")

def copy_both():
    pos, neg = apply_pony_formatting(pos_entry.get("1.0", tk.END).strip(), neg_entry.get("1.0", tk.END).strip())
    pyperclip.copy(f"{pos}\n\nNegative Prompt:\n{neg}")
    messagebox.showinfo("Copied", "Both prompts copied!")

def add_lora_syntax():
    name = title_entry.get().strip()
    if not name:
        messagebox.showwarning("Error", "Enter a LoRA name in Title first.")
        return
    pos_entry.insert(tk.INSERT, f"<lora:{name}:1.0>")

def delete_prompt():
    try:
        idx = listbox.curselection()[0]
        text = listbox.get(idx)
        title = text.split("] ", 1)[1].lstrip("★ ")
        if messagebox.askyesno("Delete", f"Delete '{title}'?"):
            conn = sqlite3.connect("prompt_vault.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompts WHERE title=?", (title,))
            conn.commit()
            conn.close()
            load_prompts()
    except:
        pass

def toggle_favorite():
    try:
        idx = listbox.curselection()[0]
        text = listbox.get(idx)
        title = text.split("] ", 1)[1].lstrip("★ ")
        conn = sqlite3.connect("prompt_vault.db")
        cursor = conn.cursor()
        cursor.execute("SELECT favorite FROM prompts WHERE title=?", (title,))
        fav = 1 - cursor.fetchone()[0]
        cursor.execute("UPDATE prompts SET favorite=? WHERE title=?", (fav, title))
        conn.commit()
        conn.close()
        load_prompts()
    except:
        pass

def random_prompt():
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    query = "SELECT title FROM prompts WHERE 1=1"
    params = []
    cat = filter_var.get()
    search = search_var.get().strip().lower()
    if cat == "Favorites":
        query += " AND favorite = 1"
    elif cat != "All":
        query += " AND category = ?"
        params.append(cat)
    if search:
        query += " AND (lower(title) LIKE ? OR lower(tags) LIKE ? OR lower(positive) LIKE ? OR lower(negative) LIKE ? OR lower(category) LIKE ?)"
        params += [f'%{search}%'] * 5
    cursor.execute(query, params)
    titles = [r[0] for r in cursor.fetchall()]
    conn.close()
    if not titles:
        messagebox.showinfo("Random", "No prompts match current filter.")
        return
    title = random.choice(titles)
    load_selected_title(title)

def load_selected_title(title):
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT title, category, tags, positive, negative FROM prompts WHERE title=?", (title,))
    row = cursor.fetchone()
    cursor.execute("UPDATE prompts SET last_used=? WHERE title=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), title))
    conn.commit()
    conn.close()
    if row:
        clear_fields()
        title_entry.insert(0, row[0])
        cat_combo.set(row[1])
        tags_entry.insert(0, row[2])
        pos_entry.insert("1.0", row[3])
        neg_entry.insert("1.0", row[4])
    load_prompts()
    messagebox.showinfo("Random Prompt", f"Loaded: {title}")

def backup_database():
    name = f"prompt_vault_backup_{datetime.now().strftime('%Y-%m-%d')}.db"
    file = filedialog.asksaveasfilename(initialfile=name, defaultextension=".db", filetypes=[("Database", "*.db")])
    if file:
        try:
            shutil.copyfile("prompt_vault.db", file)
            messagebox.showinfo("Backup", "Database backed up successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Backup failed: {e}")

def restore_database():
    file = filedialog.askopenfilename(filetypes=[("Database", "*.db")])
    if file and messagebox.askyesno("Restore", "This will overwrite your current database. Continue?"):
        try:
            shutil.copyfile(file, "prompt_vault.db")
            messagebox.showinfo("Restore", "Database restored! Reloading...")
            load_prompts()
            refresh_dropdowns()
        except Exception as e:
            messagebox.showerror("Error", f"Restore failed: {e}")

def load_prompts(event=None):
    listbox.delete(0, tk.END)
    search = search_var.get().strip().lower()
    cat = filter_var.get()
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    query = "SELECT title, category, favorite FROM prompts WHERE 1=1"
    params = []
    if cat == "Favorites":
        query += " AND favorite = 1"
    elif cat != "All":
        query += " AND category = ?"
        params.append(cat)
    if search:
        query += " AND (lower(title) LIKE ? OR lower(tags) LIKE ? OR lower(positive) LIKE ? OR lower(negative) LIKE ? OR lower(category) LIKE ?)"
        params += [f'%{search}%'] * 5
    query += " ORDER BY last_used DESC"
    cursor.execute(query, params)
    for row in cursor.fetchall():
        star = "★ " if row[2] else ""
        listbox.insert(tk.END, f"[{row[1]}] {star}{row[0]}")
    conn.close()
    update_status()

def update_status():
    conn = sqlite3.connect("prompt_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM prompts")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM prompts WHERE favorite=1")
    favs = cursor.fetchone()[0]
    visible = listbox.size()
    view = filter_var.get() if filter_var.get() != "All" else "All"
    if search_var.get().strip():
        view = f"Search: '{search_var.get()}'"
    status_label.config(text=f"{visible} shown • {total} total • {favs} favorites • {view}")
    conn.close()

def show_about():
    about = tk.Toplevel(root)
    about.title("About AI Prompt Vault")
    about.geometry("420x560")
    about.configure(background="#1e1e1e")
    about.resizable(False, False)

    img_path = os.path.join(os.path.dirname(__file__), "moon_key.png") if __file__ else "moon_key.png"
    if os.path.exists(img_path):
        try:
            img = tk.PhotoImage(file=img_path).subsample(2, 2)
            tk.Label(about, image=img, background="#1e1e1e").pack(pady=20)
            tk.Label(about, image=img).image = img
        except:
            pass

    tk.Label(about, text="AI Prompt Vault", font=("Arial", 20, "bold"), foreground="#bb86fc", background="#1e1e1e").pack(pady=10)
    tk.Label(about, text="Version 7.6", font=("Arial", 12), foreground="#ffffff", background="#1e1e1e").pack()
    info = "\nYour personal Stable Diffusion prompt manager\nwith Pony support, themes, backup, and inspiration tools.\n\nMade with passion for AI art ❤️"
    tk.Label(about, text=info, foreground="#cccccc", background="#1e1e1e", justify="center").pack(pady=20)
    tk.Button(about, text="Close", command=about.destroy, background="#7b1fa2", foreground="white").pack()

def on_closing():
    geom = f"{root.winfo_width()}x{root.winfo_height()}+{root.winfo_x()}+{root.winfo_y()}"
    set_setting("window_geometry", geom)
    root.destroy()

# --- GUI Setup ---
root = tk.Tk()
root.iconbitmap("vault.ico")
root.title("AI Prompt Vault v7.6")
style = ttk.Style()
style.theme_use('clam')

# Menu
menubar = Menu(root)
theme_menu = Menu(menubar, tearoff=0)
theme_menu.add_command(label="Dark", command=lambda: set_theme("Dark"))
theme_menu.add_command(label="Light", command=lambda: set_theme("Light"))
theme_menu.add_command(label="System (Follow Windows)", command=lambda: set_theme("System"))
menubar.add_cascade(label="Theme", menu=theme_menu)
help_menu = Menu(menubar, tearoff=0)
help_menu.add_command(label="About", command=show_about)
menubar.add_cascade(label="Help", menu=help_menu)
root.config(menu=menubar)

# Main layout with grid for better resizing
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=1)

f1 = tk.LabelFrame(root, text=" Prompt Entry & Tools ", padx=10, pady=10)
f1.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
f1.grid_columnconfigure(1, weight=1)
f1.grid_rowconfigure(2, weight=1)
f1.grid_rowconfigure(3, weight=1)

tk.Label(f1, text="Title / LoRA Name:").grid(row=0, column=0, sticky="w", pady=5)
title_entry = tk.Entry(f1, width=40)
title_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=5)

pony_var = tk.BooleanVar(value=True)
realism_var = tk.BooleanVar()
tk.Checkbutton(f1, text="Pony Mode (full scoring)", variable=pony_var).grid(row=0, column=3, padx=10)
tk.Checkbutton(f1, text="Realism Mode", variable=realism_var).grid(row=0, column=4, padx=10)

tk.Label(f1, text="Category:").grid(row=1, column=0, sticky="w", pady=5)
cat_combo = ttk.Combobox(f1, width=38)
cat_combo.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

tk.Label(f1, text="Positive Prompt:").grid(row=2, column=0, sticky="nw", pady=(10,2))
pos_entry = scrolledtext.ScrolledText(f1, height=10)
pos_entry.grid(row=2, column=1, columnspan=4, sticky="nsew", pady=5)

tk.Label(f1, text="Negative Prompt:").grid(row=3, column=0, sticky="nw")
neg_entry = scrolledtext.ScrolledText(f1, height=7)
neg_entry.grid(row=3, column=1, columnspan=4, sticky="nsew", pady=5)

tk.Label(f1, text="Tags:").grid(row=4, column=0, sticky="w", pady=5)
tags_entry = tk.Entry(f1)
tags_entry.grid(row=4, column=1, columnspan=4, sticky="ew", pady=5)

btn_row = tk.Frame(f1)
btn_row.grid(row=5, column=0, columnspan=5, pady=15)
tk.Button(btn_row, text="➕ Add LoRA Syntax", command=add_lora_syntax, width=18).pack(side="left", padx=5)
tk.Button(btn_row, text="💾 Save / Update", command=save_prompt, font=('Arial', 10, 'bold'), width=18).pack(side="left", padx=5)

f2 = tk.LabelFrame(root, text=" Your Prompt Vault ", padx=10, pady=10)
f2.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0,10))
f2.grid_rowconfigure(3, weight=1)
f2.grid_columnconfigure(0, weight=1)

search_var = tk.StringVar()
search_var.trace_add("write", load_prompts)
tk.Label(f2, text="Search:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
tk.Entry(f2, textvariable=search_var, width=60).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

tk.Label(f2, text="Filter:").grid(row=1, column=0, sticky="w", padx=5, pady=(10,0))
filter_var = tk.StringVar(value="All")
f_menu = ttk.Combobox(f2, textvariable=filter_var, state="readonly", width=30)
f_menu.grid(row=1, column=1, sticky="w", padx=5, pady=2)
f_menu.bind("<<ComboboxSelected>>", load_prompts)

listbox = tk.Listbox(f2, font=("Arial", 11))
listbox.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=10, padx=10)
listbox.bind("<Double-Button-1>", load_selected)

b_row = tk.Frame(f2)
b_row.grid(row=4, column=0, columnspan=2, pady=10)
tk.Button(b_row, text="📋 Positive", command=copy_positive, width=15).pack(side="left", padx=4)
tk.Button(b_row, text="📋 Negative", command=copy_negative, width=15).pack(side="left", padx=4)
tk.Button(b_row, text="📋 Both", command=copy_both, width=15).pack(side="left", padx=4)
tk.Button(b_row, text="🗑 Delete", command=delete_prompt, width=15).pack(side="left", padx=4)
tk.Button(b_row, text="⭐ Favorite", command=toggle_favorite, width=15).pack(side="left", padx=4)
tk.Button(b_row, text="🎲 Random", command=random_prompt, width=15).pack(side="left", padx=8)
tk.Button(b_row, text="💾 Backup", command=backup_database, width=15).pack(side="left", padx=8)
tk.Button(b_row, text="📥 Restore", command=restore_database, width=15).pack(side="left", padx=8)

status_frame = tk.Frame(root, relief="sunken", bd=1)
status_frame.grid(row=2, column=0, sticky="ew")
status_label = tk.Label(status_frame, anchor="w", padx=10)
status_label.pack(side="left")

# --- Startup ---
init_db()
root.geometry(get_setting("window_geometry", "900x1100+300+100"))
set_theme(get_setting("selected_theme", "System"))
load_prompts()
refresh_dropdowns()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()
