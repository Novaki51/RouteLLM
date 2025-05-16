import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString
import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime
import subprocess
import json

# ─────────────────────────────────────
# 1. Egyedi fájlnevek (dátum alapján)
# ─────────────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
geojson_filename = f"utvonal_{timestamp}.geojson"
png_filename = f"utvonal_{timestamp}.png"

# ─────────────────────────────────────
# 2. GUI: input mezők
# ─────────────────────────────────────
root = tk.Tk()
root.withdraw()

start_address = simpledialog.askstring("Útvonaltervezés", "Add meg a kiindulási pontot:")
end_address = simpledialog.askstring("Útvonaltervezés", "Add meg a célpontot:")
task_description = simpledialog.askstring("LLM prompt", "Írd le, milyen típusú útvonalra van szükség (pl. konvoj, bicikli, biztonságos stb.)")

if not start_address or not end_address:
    messagebox.showerror("Hiba", "Mindkét pontot meg kell adni.")
    exit()
model_name = simpledialog.askstring("LLM modell", "Melyik Ollama modellt használjuk? (pl. llama3, mistral, gemma)")

if not model_name:
    messagebox.showwarning("Modell megadása hiányzik", "Alapértelmezett modell: llama3:8b")
    model_name = "llama3:8b"


# ─────────────────────────────────────
# 3. LLM (Ollama) prompt küldése
# ─────────────────────────────────────
try:
    prompt = f"""Tervezd meg az optimális útvonalat Budapest területén a következő paraméterek alapján:
- Kiindulópont: {start_address}
- Célpont: {end_address}
- Speciális igények: {task_description}

Válaszolj JSON-ben, a következő formátumban:
{{
  "network_type": "<drive|bike|walk>",
  "comment": "<egyéb megjegyzés>"
}}"""

    result = subprocess.run(
        ["ollama", "run", model_name, prompt],
        capture_output=True,
        text=True
    )

    llm_output = result.stdout.strip()
    json_start = llm_output.find("{")
    json_end = llm_output.rfind("}") + 1
    llm_json = json.loads(llm_output[json_start:json_end])
    network_type = llm_json.get("network_type", "drive")
except Exception as e:
    messagebox.showwarning("LLM hiba", f"Nem sikerült az LLM válasz feldolgozása. Alapértelmezett: autó\n{str(e)}")
    network_type = "drive"

# ─────────────────────────────────────
# 4. Úthálózat lekérése
# ─────────────────────────────────────
print(f"Úthálózat letöltése ({network_type})...")
G = ox.graph_from_place("Budapest, Hungary", network_type=network_type)

# ─────────────────────────────────────
# 5. Csomópontok, útvonal
# ─────────────────────────────────────
start_coords = ox.geocode(start_address + ", Budapest, Hungary")
end_coords = ox.geocode(end_address + ", Budapest, Hungary")

start_node = ox.nearest_nodes(G, start_coords[1], start_coords[0])
end_node = ox.nearest_nodes(G, end_coords[1], end_coords[0])

route = nx.shortest_path(G, start_node, end_node, weight="length")

# ─────────────────────────────────────
# 6. GeoJSON mentés
# ─────────────────────────────────────
route_coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in route]
route_line = LineString(route_coords)

gdf = gpd.GeoDataFrame(index=[0], geometry=[route_line], crs="EPSG:4326")
gdf.to_file(geojson_filename, driver="GeoJSON")

# ─────────────────────────────────────
# 7. PNG térkép mentése zoomolva
# ─────────────────────────────────────
fig, ax = ox.plot_graph_route(G, route, route_linewidth=4, node_size=0, bgcolor="white", show=False, close=False, figsize=(12, 12))

edge_lines = [LineString([(G.nodes[u]['x'], G.nodes[u]['y']),
                          (G.nodes[v]['x'], G.nodes[v]['y'])]) for u, v in zip(route[:-1], route[1:])]
route_geom = MultiLineString(edge_lines)
buffered = route_geom.buffer(0.001)

ax.set_xlim(buffered.bounds[0], buffered.bounds[2])
ax.set_ylim(buffered.bounds[1], buffered.bounds[3])

plt.savefig(png_filename, dpi=300)
plt.close()

messagebox.showinfo("Siker", f"Fájlok elmentve:\n{geojson_filename}\n{png_filename}")
