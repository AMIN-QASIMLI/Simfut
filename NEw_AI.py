# -*- coding: utf-8 -*-
"""
chat_gui_pro_tagged_full.py
Tam versiya — Tag-aware, round-robin, AppData-based logo & DB, Tkinter GUI.
"""
import json
import os
import shutil
import re
from datetime import datetime
from difflib import SequenceMatcher
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText

# Try to import rapidfuzz dynamically (optional, faster fuzzy search)
try:
    import importlib
    _rf = importlib.import_module("rapidfuzz")
    process = getattr(_rf, "process", None)
    fuzz = getattr(_rf, "fuzz", None)
    _RAPIDFUZZ = bool(process and fuzz)
except Exception:
    process = None
    fuzz = None
    _RAPIDFUZZ = False

# Try pillow for image handling (icons)
try:
    from PIL import Image, ImageTk
    _PIL = True
except Exception:
    Image = None
    ImageTk = None
    _PIL = False

# ---------- AppData paths (create dir) ----------
LOCALAPPDATA = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
SIMFUT_DIR = os.path.join(LOCALAPPDATA, "Simfut")
try:
    os.makedirs(SIMFUT_DIR, exist_ok=True)
except Exception:
    pass

DB_PATH = os.path.join(SIMFUT_DIR, "simfut_db.json")
LOG_PATH = os.path.splitext(DB_PATH)[0] + ".chat.log"
APPDATA_LOGO_PNG = os.path.join(SIMFUT_DIR, "logo.png")
APPDATA_LOGO_ICO = os.path.join(SIMFUT_DIR, "logo.ico")
LOCAL_DEFAULT_LOGO = os.path.join(os.path.dirname(__file__), "logo.png")

# ---------- Icon helpers ----------
def _create_ico_from_png(png_path, ico_path, sizes=(16,32,48,64,128)):
    try:
        if not _PIL:
            return False
        img = Image.open(png_path).convert("RGBA")
        frames = []
        for s in sizes:
            fr = img.copy()
            fr = fr.resize((s, s), Image.LANCZOS)
            frames.append(fr)
        frames[0].save(ico_path, format='ICO', sizes=[(s, s) for s in sizes])
        return True
    except Exception:
        return False

def _load_icon_for_root(root, png_or_ico_path):
    try:
        ext = os.path.splitext(png_or_ico_path)[1].lower()
        if ext == ".ico" and os.name == "nt":
            try:
                root.iconbitmap(png_or_ico_path)
                return True
            except Exception:
                pass
        # fallback: PhotoImage for PNG/GIF
        try:
            img = tk.PhotoImage(file=png_or_ico_path)
            root.iconphoto(True, img)
            root._app_icon_image = img
            return True
        except Exception:
            try:
                if _PIL:
                    pil_img = Image.open(png_or_ico_path).convert("RGBA")
                    tkimg = ImageTk.PhotoImage(pil_img)
                    root.iconphoto(True, tkimg)
                    root._app_icon_image = tkimg
                    return True
            except Exception:
                return False
    except Exception:
        return False

def _set_app_icon(self, path):
    if not path or not os.path.exists(path):
        return False
    ok = _load_icon_for_root(self, path)
    if not ok and os.name == "nt" and path.lower().endswith(".png"):
        ico_temp = os.path.splitext(path)[0] + ".temp.ico"
        if _create_ico_from_png(path, ico_temp):
            try:
                self.iconbitmap(ico_temp)
                ok = True
            except Exception:
                ok = ok or False
    # update logo in UI if present
    try:
        if _PIL:
            img = Image.open(path)
            img.thumbnail((64,64), Image.LANCZOS)
            self.logo = ImageTk.PhotoImage(img)
            if hasattr(self, "logo_label") and self.logo_label:
                self.logo_label.config(image=self.logo)
            else:
                try:
                    ttk.Label(self.right_panel, image=self.logo).pack(side=tk.BOTTOM, pady=8)
                except Exception:
                    pass
        else:
            img = tk.PhotoImage(file=path)
            self.logo = img
            if hasattr(self, "logo_label") and self.logo_label:
                self.logo_label.config(image=self.logo)
    except Exception:
        pass
    return ok

# ---------- Utilities ----------
def ensure_db():
    if not os.path.exists(DB_PATH):
        db = {"meta": {"creation_date": "17.12.2024"}, "suallar": []}
        save_db(db)
        return db
    return load_db()

def load_db(path=DB_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "meta" not in data:
            data["meta"] = {"creation_date": "17.12.2024"}
        if "suallar" not in data:
            data["suallar"] = []
        return data
    except Exception:
        return {"meta": {"creation_date": "17.12.2024"}, "suallar": []}

def save_db(db, path=DB_PATH):
    try:
        dirpath = os.path.dirname(path)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Xəta", f"Veritabanı yazılarkən xəta: {e}")

def backup_db(path=DB_PATH):
    if not os.path.exists(path):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{path}.backup.{ts}.json"
    shutil.copy2(path, backup)
    return backup

def log_chat_line(line):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} {line}\n")
    except Exception:
        pass

def normalize_text(s: str) -> str:
    return s.strip().casefold()

# ---------- Matching ----------
def fuzzy_best_matches(query, corpus, limit=5):
    if _RAPIDFUZZ:
        res = process.extract(query, corpus, scorer=fuzz.WRatio, limit=limit)
        return [(r[0], float(r[1]) / 100.0) for r in res]
    else:
        scored = []
        for c in corpus:
            ratio = SequenceMatcher(None, query, c).ratio()
            scored.append((c, ratio))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

# ---------- Age compute ----------
def compute_age_from_date_string(date_str):
    try:
        created = datetime.strptime(date_str, "%d.%m.%Y").date()
        today = datetime.now().date()
        delta = today - created
        years = delta.days // 365
        months = (delta.days % 365) // 30
        days = (delta.days % 365) % 30
        parts = []
        if years: parts.append(f"{years} il")
        if months: parts.append(f"{months} ay")
        if days: parts.append(f"{days} gün")
        return created.strftime("%d.%m.%Y"), ", ".join(parts) if parts else "0 gün"
    except Exception:
        return None, None

# ---------- Tag-aware selection with round-robin ----------
def select_answer(user_question, db, context=None, cutoff=0.6, active_tag=None, round_robin_store=None):
    qn = normalize_text(user_question)

    age_triggers = ("nece yasin var", "necə yaşın", "niye deqiq demirsen yasini", "necə yaşın var", "nece yashin var", "nece yashin var?")
    for trig in age_triggers:
        if trig in qn:
            cd = db.get("meta", {}).get("creation_date")
            if not cd:
                for it in db.get("suallar", []):
                    m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})", it.get("cavab",""))
                    if m:
                        cd = m.group(1); break
            if not cd: cd = "17.12.2024"
            created_str, parts = compute_age_from_date_string(cd)
            if created_str:
                return f"Mən fiziki bədənə malik olmayan virtual süni intellektəm; yaradılma tarixim {created_str} və bu vaxta qədər: {parts}."
            else:
                return "Yaşımı hesablamaq üçün yaradılma tarixi düzgün deyil."

    candidates = db.get("suallar", [])

    def filter_by_tag(cands, tag):
        if not tag or tag.lower() in ("", "auto"):
            return cands
        return [c for c in cands if normalize_text(c.get("tag","") or "") == normalize_text(tag)]

    def answers_for_question(cands, question_text):
        return [c for c in cands if normalize_text(c.get("sual","")) == normalize_text(question_text)]

    chosen_tag = active_tag
    if not chosen_tag or normalize_text(str(chosen_tag)) == "auto":
        chosen_tag = None
        if context:
            for who, txt in reversed(context):
                m = re.search(r"Tag[:=]\s*([A-Za-z0-9_-]+)", txt)
                if m:
                    chosen_tag = m.group(1)
                    break
        if not chosen_tag:
            chosen_tag = "auto"

    cands_tagged = filter_by_tag(candidates, None if chosen_tag == "auto" else chosen_tag)
    exact_tagged = answers_for_question(cands_tagged, user_question)
    if exact_tagged:
        key = (normalize_text(user_question), normalize_text(chosen_tag or ""))
        idx = 0
        if round_robin_store is not None:
            idx = round_robin_store.get(key, 0) % len(exact_tagged)
            round_robin_store[key] = (idx + 1) % len(exact_tagged)
        return exact_tagged[idx].get("cavab")

    corpus_tagged = [it.get("sual","") for it in cands_tagged]
    if corpus_tagged:
        matches = fuzzy_best_matches(user_question, corpus_tagged, limit=5)
        if matches and matches[0][1] >= cutoff:
            best_text = matches[0][0]
            matched_entries = [it for it in cands_tagged if it.get("sual","") == best_text]
            key = (normalize_text(best_text), normalize_text(chosen_tag or ""))
            idx = 0
            if round_robin_store is not None and matched_entries:
                idx = round_robin_store.get(key, 0) % len(matched_entries)
                round_robin_store[key] = (idx + 1) % len(matched_entries)
            if matched_entries:
                return matched_entries[idx].get("cavab")

    for it in candidates:
        if normalize_text(it.get("sual","")) == qn:
            return it.get("cavab")

    corpus = [it.get("sual","") for it in candidates]
    if corpus:
        matches = fuzzy_best_matches(user_question, corpus, limit=5)
        if matches and matches[0][1] >= cutoff:
            best_text = matches[0][0]
            matched_entries = [it for it in candidates if it.get("sual","") == best_text]
            key = (normalize_text(best_text), "")
            idx = 0
            if round_robin_store is not None and matched_entries:
                idx = round_robin_store.get(key, 0) % len(matched_entries)
                round_robin_store[key] = (idx + 1) % len(matched_entries)
            if matched_entries:
                return matched_entries[idx].get("cavab")

    return None

# ---------- GUI ----------
class ChatGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simfut")
        self.geometry("920x560")
        self.minsize(720, 480)
        self.db = ensure_db()
        self.context = []
        self.context_max = 8
        self.round_robin = {}
        self.active_tag = "auto"
        self._build_ui()

    def _build_ui(self):
        # menus
        menubar = tk.Menu(self)
        filem = tk.Menu(menubar, tearoff=False)
        filem.add_command(label="Backup Veritabanı", command=self._backup)
        filem.add_command(label="Restore Veritabanı...", command=self._restore)
        filem.add_separator()
        filem.add_command(label="Çıx", command=self._on_exit)
        menubar.add_cascade(label="Fayl", menu=filem)

        tools = tk.Menu(menubar, tearoff=False)
        tools.add_command(label="Sual/Cavabları İdarə et...", command=self._manage)
        menubar.add_cascade(label="Alətlər", menu=tools)

        # Settings menu
        settings = tk.Menu(menubar, tearoff=False)
        settings.add_command(label="Ikon yüklə...", command=lambda: self._prompt_load_icon())
        settings.add_command(label="Ikonu sıfırla", command=lambda: self._reset_icon())
        menubar.add_cascade(label="Ayarlar", menu=settings)

        self.config(menu=menubar)

        # style tweaks
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TButton", font=("Consolas", 10), foreground="black")

        # layout frames
        left = ttk.Frame(self); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        right = ttk.Frame(self, width=300); right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,8), pady=8)
        self.right_panel = right

        self.chat_display = ScrolledText(left, state="disabled", wrap="word", font=("Consolas", 10))
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        ttk.Label(right, text="Giriş (sual):").pack(anchor="w")
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(right, textvariable=self.entry_var, font=("Consolas", 10))
        self.entry.pack(fill=tk.X)
        self.entry.bind("<Return>", lambda e: self._send())

        ttk.Button(right, text="Göndər", command=self._send).pack(fill=tk.X, pady=6)
        ttk.Separator(right).pack(fill=tk.X, pady=6)
        ttk.Label(right, text="Uyğunluqlar:").pack(anchor="w")
        self.match_list = tk.Listbox(right, height=6, font=("Consolas", 10))
        self.match_list.pack(fill=tk.X)
        self.match_list.bind("<Double-1>", self._match_double)

        ttk.Label(right, text="Həssaslıq (cutoff):").pack(anchor="w", pady=(8,0))
        self.cut = tk.DoubleVar(value=0.6)
        ttk.Scale(right, from_=0.2, to=0.95, variable=self.cut).pack(fill=tk.X)

        # Active tag combobox
        ttk.Label(right, text="Aktiv Tag:").pack(anchor="w", pady=(8,0))
        self.tag_var = tk.StringVar(value="auto")
        tags_list = self._gather_tags()
        self.tag_combo = ttk.Combobox(right, textvariable=self.tag_var, values=["auto"] + tags_list, state="readonly")
        self.tag_combo.pack(fill=tk.X)
        self.tag_combo.bind("<<ComboboxSelected>>", lambda e: self._on_tag_change())

        ttk.Button(right, text="Sual/Cavab idarə", command=self._manage).pack(fill=tk.X, pady=(8,0))
        ttk.Button(right, text="Söhbəti təmizlə", command=self._clear_chat).pack(fill=tk.X, pady=(4,0))

        self.status = tk.StringVar(value="Hazır")
        ttk.Label(self, textvariable=self.status).pack(side=tk.BOTTOM, anchor="w", padx=8, pady=(0,8))

        # Load logo from AppData or bundled default
        try:
            if os.path.exists(APPDATA_LOGO_PNG) and _PIL:
                img = Image.open(APPDATA_LOGO_PNG)
                img.thumbnail((64,64), Image.LANCZOS)
                self.logo = ImageTk.PhotoImage(img)
                self.logo_label = ttk.Label(right, image=self.logo)
                self.logo_label.pack(side=tk.BOTTOM, pady=8)
            else:
                if os.path.exists(LOCAL_DEFAULT_LOGO):
                    try:
                        shutil.copy2(LOCAL_DEFAULT_LOGO, APPDATA_LOGO_PNG)
                        if _PIL:
                            img = Image.open(APPDATA_LOGO_PNG)
                            img.thumbnail((64,64), Image.LANCZOS)
                            self.logo = ImageTk.PhotoImage(img)
                            self.logo_label = ttk.Label(right, image=self.logo)
                            self.logo_label.pack(side=tk.BOTTOM, pady=8)
                    except Exception:
                        try:
                            if _PIL:
                                img = Image.open(LOCAL_DEFAULT_LOGO)
                                img.thumbnail((64,64), Image.LANCZOS)
                                self.logo = ImageTk.PhotoImage(img)
                                self.logo_label = ttk.Label(right, image=self.logo)
                                self.logo_label.pack(side=tk.BOTTOM, pady=8)
                        except Exception:
                            self.logo_label = None
                else:
                    self.logo_label = None
        except Exception:
            self.logo_label = None

        # set taskbar / window icon if available
        if os.path.exists(APPDATA_LOGO_PNG):
            _set_app_icon(self, APPDATA_LOGO_PNG)
        elif os.path.exists(LOCAL_DEFAULT_LOGO):
            try:
                shutil.copy2(LOCAL_DEFAULT_LOGO, APPDATA_LOGO_PNG)
                _set_app_icon(self, APPDATA_LOGO_PNG)
            except Exception:
                _set_app_icon(self, LOCAL_DEFAULT_LOGO)

    # Tag helpers
    def _gather_tags(self):
        tags = sorted({(it.get("tag") or "").strip() for it in self.db.get("suallar", []) if (it.get("tag") or "").strip()})
        return tags

    def _refresh_tag_combo(self):
        tags_list = self._gather_tags()
        vals = ["auto"] + tags_list
        try:
            self.tag_combo['values'] = vals
        except Exception:
            pass

    def _on_tag_change(self):
        self.active_tag = self.tag_var.get()

    # Icon UI helpers
    def _prompt_load_icon(self):
        f = filedialog.askopenfilename(title="Icon seçin", filetypes=[("Image/ICO", "*.png;*.ico;*.gif;*.jpg"), ("All files","*.*")])
        if not f:
            return
        try:
            dest = APPDATA_LOGO_PNG if os.path.splitext(f)[1].lower() != ".ico" else APPDATA_LOGO_ICO
            shutil.copy2(f, dest)
        except Exception:
            dest = f
        ok = _set_app_icon(self, dest)
        if ok:
            messagebox.showinfo("Ok", "Ikon tətbiq olundu.")
            self.status.set("Ikon yükləndi.")
        else:
            messagebox.showwarning("Xəta", "Ikon tətbiq edilə bilmədi (format dəstəklənmir).")

    def _reset_icon(self):
        if os.path.exists(LOCAL_DEFAULT_LOGO):
            try:
                shutil.copy2(LOCAL_DEFAULT_LOGO, APPDATA_LOGO_PNG)
                _set_app_icon(self, APPDATA_LOGO_PNG)
                messagebox.showinfo("Ok", "Ikon sıfırlandı.")
                self.status.set("Ikon sıfırlandı.")
            except Exception:
                messagebox.showwarning("Xəta", "Ikon sıfırlanarkən problem oldu.")
        else:
            messagebox.showwarning("Xəbərdarlıq", "Default logo.png tapılmadı.")

    # Logging / chat
    def _log(self, who, text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert(tk.END, f"{who}: {text}\n")
        self.chat_display.configure(state="disabled")
        self.chat_display.see(tk.END)
        log_chat_line(f"{who}: {text}")
        self.context.append((who, text))
        if len(self.context) > self.context_max:
            self.context.pop(0)

    def _send(self):
        q = self.entry_var.get().strip()
        if not q:
            return
        self._log("Siz", q)
        self.entry_var.set("")
        ans = select_answer(q, self.db, context=self.context, cutoff=self.cut.get(), active_tag=self.active_tag, round_robin_store=self.round_robin)
        if ans:
            self._log("Simfut", ans)
            self.status.set("Cavab tapıldı.")
            return
        corpus = [it.get("sual","") for it in self.db.get("suallar", [])]
        matches = fuzzy_best_matches(q, corpus, limit=5)
        self.match_list.delete(0, tk.END)
        for m, score in matches:
            self.match_list.insert(tk.END, f"{m}  ({score:.2f})")
        if matches and matches[0][1] >= self.cut.get():
            best = matches[0][0]
            for it in self.db.get("suallar", []):
                if it.get("sual","") == best:
                    self._log("Simfut (təklif)", it.get("cavab"))
                    self.status.set(f"Təklif göstərildi (uyğunluq {matches[0][1]:.2f}).")
                    return
        self.status.set("Yeni sual — öyrətmək üçün pəncərə açılır.")
        self._teach_dialog(q)

    def _match_double(self, event):
        sel = self.match_list.curselection()
        if not sel: return
        txt = self.match_list.get(sel[0])
        q = txt.split("  (")[0]
        for it in self.db.get("suallar", []):
            if it.get("sual","") == q:
                self._log("Simfut (seçilmiş)", it.get("cavab"))
                self.status.set("Seçilmiş cavab göstərildi.")
                return

    def _teach_dialog(self, question):
        td = TeachDialog(self, question, self.db, self._gather_tags())
        self.wait_window(td)
        if td.result is None:
            self._log("Simfut", "Öyrədilmədi.")
            return
        normalized = normalize_text(question)
        for it in self.db.get("suallar", []):
            if normalize_text(it.get("sual","")) == normalized:
                if not messagebox.askyesno("Duplicate", "Belə bir sual artıq var. Üzərinə yazılsın?"):
                    return
                it.update({"cavab": td.result["cavab"], "tag": td.result.get("tag","")})
                save_db(self.db)
                self._log("Simfut", "Mövcud sual yeniləndi.")
                if td.result.get("send_now"):
                    self._log("Simfut (yeni)", td.result["cavab"])
                self._refresh_tag_combo()
                return
        self.db.setdefault("suallar", []).append({"sual": question, "cavab": td.result["cavab"], "tag": td.result.get("tag","")})
        save_db(self.db)
        self._log("Simfut", "Yeni sual əlavə edildi.")
        if td.result.get("send_now"):
            self._log("Simfut (yeni)", td.result["cavab"])
        self._refresh_tag_combo()

    def _manage(self):
        md = ManageDialog(self, self.db)
        self.wait_window(md)
        save_db(self.db)
        self._log("Simfut", "Veritabanı yeniləndi.")
        self._refresh_tag_combo()

    def _backup(self):
        b = backup_db()
        if b:
            messagebox.showinfo("Backup", f"Yedək yaradıldı: {b}")
        else:
            messagebox.showwarning("Backup", "Veritabanı tapılmadı.")

    def _restore(self):
        f = filedialog.askopenfilename(title="Restore JSON seç", filetypes=[("JSON faylları","*.json"), ("Bütün","*.*")])
        if not f: return
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "suallar" in data:
                self.db = data
                save_db(self.db)
                messagebox.showinfo("Restore", "Uğurla yükləndi.")
                self._refresh_tag_combo()
        except Exception as e:
            messagebox.showerror("Xəta", str(e))

    def _clear_chat(self):
        if messagebox.askyesno("Təmizlə", "Söhbəti təmizləmək istədiyinizdən əminsiniz?"):
            self.chat_display.configure(state="normal")
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.configure(state="disabled")
            self.context.clear()
            self.status.set("Söhbət təmizləndi.")

    def _on_exit(self):
        if messagebox.askyesno("Çıxış", "Çıxmaq istəyirsiniz?"):
            self.destroy()

# ---------- TeachDialog and ManageDialog ----------
class TeachDialog(tk.Toplevel):
    def __init__(self, parent, question, db, tags_list=None):
        super().__init__(parent)
        self.transient(parent); self.grab_set()
        self.title("Öyrət — cavab əlavə et")
        self.geometry("460x300"); self.resizable(False, False)
        self.result = None; self.db = db
        ttk.Label(self, text=f"Sual: {question}", wraplength=430).pack(anchor="w", padx=8, pady=(8,0))
        ttk.Label(self, text="Cavab:").pack(anchor="w", padx=8, pady=(8,0))
        self.txt = tk.Text(self, height=6, font=("Consolas",10)); self.txt.pack(fill=tk.BOTH, padx=8, pady=(0,6))
        ttk.Label(self, text="Tag (istəyə bağlı):").pack(anchor="w", padx=8)
        self.tag = tk.StringVar()
        vals = [""] + (tags_list or [])
        self.tag_combo = ttk.Combobox(self, textvariable=self.tag, values=vals); self.tag_combo.pack(fill=tk.X, padx=8, pady=(0,6))
        self.send_now = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="İndi chat-ə göndər", variable=self.send_now).pack(anchor="w", padx=8)
        fr = ttk.Frame(self); fr.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(fr, text="Saxla", command=self._save).pack(side=tk.LEFT)
        ttk.Button(fr, text="Keç", command=self._skip).pack(side=tk.LEFT, padx=6)
        ttk.Button(fr, text="İmtina", command=self._cancel).pack(side=tk.RIGHT)

    def _save(self):
        val = self.txt.get("1.0", tk.END).strip()
        if not val:
            messagebox.showwarning("Xəbərdarlıq", "Cavab boş ola bilməz.")
            return
        self.result = {"cavab": val, "tag": self.tag.get().strip(), "send_now": bool(self.send_now.get())}
        self.destroy()

    def _skip(self):
        self.result = None; self.destroy()

    def _cancel(self):
        self.result = None; self.destroy()

class ManageDialog(tk.Toplevel):
    def __init__(self, parent, db):
        super().__init__(parent)
        self.title("İdarəetmə"); self.geometry("760x420")
        self.db = db
        left = ttk.Frame(self); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        right = ttk.Frame(self, width=320); right.pack(side=tk.RIGHT, fill=tk.Y, padx=8, pady=8)
        ttk.Label(left, text="Sual/Cavablar").pack(anchor="w")
        self.lb = tk.Listbox(left, font=("Consolas",10)); self.lb.pack(fill=tk.BOTH, expand=True)
        self._refresh()
        fr = ttk.Frame(left); fr.pack(fill=tk.X, pady=6)
        ttk.Button(fr, text="Yenilə", command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(fr, text="Yeni", command=self._new).pack(side=tk.LEFT, padx=6)
        ttk.Button(fr, text="Sil", command=self._delete).pack(side=tk.LEFT, padx=6)
        ttk.Button(fr, text="Diskə yaz", command=lambda: save_db(self.db)).pack(side=tk.RIGHT)
        ttk.Label(right, text="Preview").pack(anchor="w")
        self.preview = tk.Text(right, height=12, state="disabled", font=("Consolas",10)); self.preview.pack(fill=tk.X)
        ttk.Button(right, text="Göndər Chat-ə", command=self._send_to_chat).pack(fill=tk.X, pady=(8,0))
        ttk.Button(right, text="Axtar", command=self._search).pack(fill=tk.X, pady=4)
        self.lb.bind("<<ListboxSelect>>", self._on_select)

    def _refresh(self):
        self.lb.delete(0, tk.END)
        for i,it in enumerate(self.db.get("suallar", [])):
            q = it.get("sual","").replace("\n"," ")[:60]
            tag = it.get("tag","")
            disp = f"{i+1:03d}: {q}" + (f" [{tag}]" if tag else "")
            self.lb.insert(tk.END, disp)

    def _on_select(self, e=None):
        sel = self.lb.curselection()
        if not sel: return
        idx = sel[0]; it = self.db["suallar"][idx]
        self.preview.configure(state="normal"); self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, f"Sual:\n{it.get('sual')}\n\nCavab:\n{it.get('cavab')}\n\nTag: {it.get('tag','')}")
        self.preview.configure(state="disabled")

    def _new(self):
        q = simpledialog.askstring("Yeni sual", "Sual:")
        if not q: return
        a = simpledialog.askstring("Yeni cavab", "Cavab:")
        if a is None: return
        tag = simpledialog.askstring("Tag", "Tag (isteğe bağlı):", initialvalue="")
        self.db.setdefault("suallar", []).append({"sual": q, "cavab": a, "tag": tag or ""})
        self._refresh()

    def _delete(self):
        sel = self.lb.curselection()
        if not sel: return
        if messagebox.askyesno("Silmək", "Silmək istədiyinizə əminsiniz?"):
            del self.db["suallar"][sel[0]]
            self._refresh()
            self.preview.configure(state="normal"); self.preview.delete("1.0", tk.END); self.preview.configure(state="disabled")

    def _send_to_chat(self):
        sel = self.lb.curselection()
        if not sel:
            messagebox.showinfo("Məlumat", "Seçin."); return
        it = self.db["suallar"][sel[0]]
        try:
            self.master._log("Simfut (idarə)", it.get("cavab"))
            messagebox.showinfo("Ok", "Göndərildi.")
        except Exception as e:
            messagebox.showerror("Xəta", str(e))

    def _search(self):
        q = simpledialog.askstring("Axtar", "Axtar:")
        if not q: return
        for i,it in enumerate(self.db.get("suallar", [])):
            if q.lower() in it.get("sual","").lower():
                self.lb.selection_clear(0, tk.END); self.lb.selection_set(i); self.lb.see(i); self._on_select(); return
        messagebox.showinfo("Tapılmadı", "Uyğun sual tapılmadı.")

# ---------- Run ----------
if __name__ == "__main__":
    app = ChatGUI()
    app.mainloop()
