import os
import tkinter as tk
from tkinter import simpledialog, messagebox
import subprocess
import ollama
import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString

def get_prompt_from_user():
    root = tk.Tk()
    root.withdraw()
    prompt = simpledialog.askstring("Útvonal kérés", "Add meg az útvonal igényt (pl. több alternatíva, kerülők, főutak):")
    return prompt

def generate_llm_code(prompt_text):
    response = ollama.chat(
        model="llama3:8b",  # vagy "llama3:8b"
        messages=[
            {"role": "system", "content": "Only return valid, raw Python code. No explanations, no markdown, no triple backticks. The code should generate multiple driving routes using osmnx, save them as route.geojson, and plot them to route.png."},
            {"role": "user", "content": prompt_text}
        ]
    )
    print(response)
    return response['message']['content']

def strip_code_block_fencing(code):
    lines = code.strip().splitlines()
    if lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)

def run_code(code_str):
    temp_file = "temp_route_gen.py"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code_str)

    print("===== LLM-GENERATED CODE START =====")
    print(code_str)
    print("===== LLM-GENERATED CODE END =====")

    try:
        subprocess.run(["python", temp_file], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Hiba", f"Hiba a generált kódban:\n{e}")
    finally:
        os.remove(temp_file)

def main():
    prompt = get_prompt_from_user()
    if not prompt:
        return

    code = generate_llm_code(prompt)
    clean_code = strip_code_block_fencing(code)
    run_code(clean_code)
    run_code(code)

    files = []
    if os.path.exists("route.geojson"):
        files.append("route.geojson")
    if os.path.exists("route.png"):
        files.append("route.png")

    if files:
        messagebox.showinfo("Siker", f"A következő fájlok elkészültek:\n" + "\n".join(files))
    else:
        messagebox.showerror("Hiba", "Nem készült GeoJSON vagy PNG fájl.")

if __name__ == "__main__":
    main()
