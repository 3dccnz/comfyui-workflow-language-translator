import json
import re
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from deep_translator import GoogleTranslator
from PIL import PngImagePlugin, Image

# --- Supported languages ---
LANGUAGES = [
    'auto', 'en', 'zh-CN', 'ja', 'ko', 'de', 'fr', 'es', 'ru', 'it',
    'pt', 'ar', 'hi', 'tr', 'nl', 'pl', 'sv', 'fi', 'uk', 'vi'
]

# --- Safe node types for widgets_values ---
SAFE_WIDGETS_NODES = [
    "Note",
    "MarkdownNote",
    "PrimitiveString",
    "String Literal",
    "CLIPTextEncode"
]

# --- Translation detection ---
def contains_foreign(text):
    return bool(re.search(r'[^\x00-\x7F]', text))

def looks_like_identifier(text):
    return bool(re.match(r'^[A-Za-z0-9_\-]+$', text))

def translate_string(text, source_lang, target_lang):
    try:
        translated = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
        return translated if translated.lower() != text.lower() else text
    except Exception:
        return text

# --- Pass 1 (non-ASCII translation only — widgets_values skipped) ---
def process_node_pass1(node, source_lang, target_lang, log_callback):
    if isinstance(node, dict):
        keys_to_update = []
        for key, value in node.items():
            if key == "widgets_values":
                continue  # Skip widgets_values in Pass 1
            new_key = translate_string(key, source_lang, target_lang) if contains_foreign(key) else key
            if new_key != key:
                keys_to_update.append((key, new_key))
            if isinstance(value, str):
                translated_value = translate_string(value, source_lang, target_lang) if contains_foreign(value) else value
                if translated_value != value:
                    log_callback(f"Translated: {value} ➔ {translated_value}")
                node[key] = translated_value
            else:
                process_node_pass1(value, source_lang, target_lang, log_callback)
        for old_key, new_key in keys_to_update:
            node[new_key] = node.pop(old_key)
    elif isinstance(node, list):
        for i in range(len(node)):
            item = node[i]
            if isinstance(item, str):
                translated_item = translate_string(item, source_lang, target_lang) if contains_foreign(item) else item
                if translated_item != item:
                    log_callback(f"Translated: {item} ➔ {translated_item}")
                node[i] = translated_item
            else:
                process_node_pass1(item, source_lang, target_lang, log_callback)

# --- Pass 2 (deep scan safe fields only) ---
def process_groups_pass2(groups, source_lang, target_lang, log_callback):
    for group in groups:
        if "title" in group and isinstance(group["title"], str) and not looks_like_identifier(group["title"]):
            translated = translate_string(group["title"], source_lang, target_lang)
            if translated != group["title"]:
                log_callback(f"Group Title (force): {group['title']} ➔ {translated}")
            group["title"] = translated

def process_nodes_pass2(nodes, source_lang, target_lang, log_callback):
    for node in nodes:
        if "title" in node and isinstance(node["title"], str):
            translated = translate_string(node["title"], source_lang, target_lang)
            if translated != node["title"]:
                log_callback(f"Node Title (force): {node['title']} ➔ {translated}")
            node["title"] = translated

        if "notes" in node and isinstance(node["notes"], str):
            translated = translate_string(node["notes"], source_lang, target_lang)
            if translated != node["notes"]:
                log_callback(f"Notes (force): {node['notes']} ➔ {translated}")
            node["notes"] = translated

        if "parameters" in node and isinstance(node["parameters"], dict):
            for subkey in ["prompt", "positive_prompt", "negative_prompt"]:
                if subkey in node["parameters"] and isinstance(node["parameters"][subkey], str):
                    translated = translate_string(node["parameters"][subkey], source_lang, target_lang)
                    if translated != node["parameters"][subkey]:
                        log_callback(f"Prompt ({subkey}) (force): {node['parameters'][subkey]} ➔ {translated}")
                    node["parameters"][subkey] = translated

        if "widgets" in node and isinstance(node["widgets"], list):
            for widget in node["widgets"]:
                if isinstance(widget, dict):
                    if "label" in widget and isinstance(widget["label"], str):
                        translated = translate_string(widget["label"], source_lang, target_lang)
                        if translated != widget["label"]:
                            log_callback(f"Widget Label (force): {widget['label']} ➔ {translated}")
                        widget["label"] = translated
                    if "default" in widget and isinstance(widget["default"], str):
                        translated = translate_string(widget["default"], source_lang, target_lang)
                        if translated != widget["default"]:
                            log_callback(f"Widget Default (force): {widget['default']} ➔ {translated}")
                        widget["default"] = translated

        if node.get("type") in SAFE_WIDGETS_NODES:
            if "widgets_values" in node and isinstance(node["widgets_values"], list):
                for i, item in enumerate(node["widgets_values"]):
                    if isinstance(item, str):
                        translated = translate_string(item, source_lang, target_lang)
                        if translated != item:
                            log_callback(f"Widgets Value (force): {item} ➔ {translated}")
                        node["widgets_values"][i] = translated

def extract_workflow_json_and_key(png_path):
    img = Image.open(png_path)
    meta = img.info
    candidate_keys = ["workflow", "workflow_json", "comfyui_workflow", "parameters", "prompt"]

    for key in candidate_keys:
        if key in meta:
            try:
                return json.loads(meta[key]), key
            except:
                continue

    raise ValueError("No embedded ComfyUI workflow JSON found in PNG.")

# --- GUI ---
class TranslatorApp:
    def __init__(self, root):
        self.root = root
        root.title("ComfyUI Workflow Language Translator - Created by 3dccnz")
        root.geometry("800x750")
        root.resizable(False, False)

        self.input_file = ""
        self.output_file = ""

        tk.Label(root, text="ComfyUI Workflow Language Translator - Created by 3dccnz", font=("Arial", 16, "bold")).pack(pady=10)

        tk.Button(root, text="Select Input File (.json or .png)", command=self.select_input_file, width=50).pack(pady=5)
        tk.Button(root, text="Select Output JSON File", command=self.select_output_file, width=50).pack(pady=5)

        self.source_lang = tk.StringVar(value='auto')
        self.target_lang = tk.StringVar(value='en')
        self.enable_pass2 = tk.BooleanVar(value=True)

        lang_frame = tk.Frame(root)
        lang_frame.pack(pady=10)

        tk.Label(lang_frame, text="Source:").pack(side="left", padx=5)
        ttk.Combobox(lang_frame, textvariable=self.source_lang, values=LANGUAGES, width=10).pack(side="left")
        tk.Label(lang_frame, text="Target:").pack(side="left", padx=5)
        ttk.Combobox(lang_frame, textvariable=self.target_lang, values=LANGUAGES, width=10).pack(side="left")

        options_frame = tk.Frame(root)
        options_frame.pack(pady=5)
        tk.Checkbutton(options_frame, text="Deep Text Scan (Translate group titles, node titles & widget fields)", variable=self.enable_pass2).pack()
        tk.Label(options_frame, text="Tip: Use for translating renamed nodes, widgets, prompts, and group labels.", fg="gray").pack()

        tk.Button(root, text="Translate & Save", command=self.run_translation, width=50, bg="#4CAF50", fg="white").pack(pady=10)
        tk.Button(root, text="Info / Disclaimer", command=self.show_info, width=50, bg="#2196F3", fg="white").pack(pady=5)

        self.log = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=28)
        self.log.pack(padx=10, pady=5)

    def log_message(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.root.update()

    def show_info(self):
        info_text = (
            "ComfyUI Workflow Language Translator — Created by 3dccnz\n\n"
            "This tool allows ComfyUI workflows to be translated between different languages, including embedded JSON inside .json and .png files.\n\n"
            "The system uses Google's unofficial web translation API for processing text fields.\n\n"
            "⚠ Important Notes:\n"
            "- Not guaranteed to translate 100% of all workflow fields.\n"
            "- Certain technical fields may remain untranslated or translate incorrectly.\n"
            "- Workflow structure may occasionally break depending on node configurations.\n"
            "- All converted workflows should be fully tested by the user before production use.\n\n"
            "Use at your own discretion. This tool is designed to assist but not replace careful validation.\n\n"
            "Created for private & personal use."
        )
        messagebox.showinfo("ComfyUI Translator Info", info_text)

    def select_input_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON or PNG files", "*.json *.png")])
        if path:
            self.input_file = path
            self.log_message(f"Selected input: {path}")

    def select_output_file(self):
        path = filedialog.asksaveasfilename(filetypes=[("JSON files", "*.json")])
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            self.output_file = path
            self.log_message(f"Selected output JSON: {path}")

    def run_translation(self):
        if not self.input_file or not self.output_file:
            messagebox.showwarning("Missing Info", "Please select both input and output file paths.")
            return

        source_lang = self.source_lang.get()
        target_lang = self.target_lang.get()
        run_second_pass = self.enable_pass2.get()

        try:
            if self.input_file.lower().endswith(".json"):
                with open(self.input_file, 'r', encoding='utf-8') as infile:
                    data = json.load(infile)
            elif self.input_file.lower().endswith(".png"):
                self.log_message("Extracting workflow JSON from PNG...")
                data, _ = extract_workflow_json_and_key(self.input_file)
            else:
                raise ValueError("Unsupported file type.")

            self.log_message("Starting Pass 1 (non-ASCII only, safe mode)...")
            process_node_pass1(data, source_lang, target_lang, self.log_message)

            if run_second_pass:
                self.log_message("Starting Pass 2 (deep text scan)...")
                if "groups" in data:
                    process_groups_pass2(data["groups"], source_lang, target_lang, self.log_message)
                if "nodes" in data:
                    process_nodes_pass2(data["nodes"], source_lang, target_lang, self.log_message)

            with open(self.output_file, 'w', encoding='utf-8') as outfile:
                json.dump(data, outfile, ensure_ascii=False, indent=2)

            self.log_message("✅ Translation complete!")
            messagebox.showinfo("Done", "File translated and saved successfully!")

        except Exception as e:
            self.log_message(f"❌ Error: {e}")
            messagebox.showerror("Error", str(e))

# --- START ---
if __name__ == "__main__":
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()
