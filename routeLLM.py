import os
import json
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import simpledialog, messagebox
import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString

# ───────────────────────────────
# 1. Interaktív felhasználói bemenet
# ───────────────────────────────
root = tk.Tk()
root.withdraw()

start_address = simpledialog.askstring("Kiindulópont", "Add meg a kiindulási címet:")
end_address = simpledialog.askstring("Célpont", "Add meg a célcímet:")
prompt_input = simpledialog.askstring("Útvonal leírás", "Írd le az igényeket (pl. konvoj, waypointok, kitérő):")
model_name = simpledialog.askstring("LLM modell (Ollama)", "Melyik Ollama modellt használjuk? (pl. llama3)", initialvalue="llama3:8b")

if not start_address or not end_address:
    messagebox.showerror("Hiba", "Kiindulópont és célpont kötelező!")
    exit()

# ───────────────────────────────
# 2. JSON választ kérünk az LLM-től (Ollama CLI)
# ───────────────────────────────
llm_prompt = f"""
Tervezd meg az útvonalat Budapest területén.
- Kiindulópont: {start_address}
- Célpont: {end_address}
- Igény: {prompt_input}

Kérek kizárólag érvényes JSON-t az alábbi mezőkkel:
{{
  "network_type": "drive|bike|walk",
  "waypoints": ["hely1", "hely2"],
  "split_routes": true|false,
  "priority": "safety|speed",
  "allow_detour_km": float
}}
"""
#print(llm_prompt)
try:
    result = subprocess.run(
        ["ollama", "run", model_name, llm_prompt],
        capture_output=True,
        text=True,
    )

    response_text = result.stdout.strip()
    print(response_text)
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1
    config = json.loads(response_text[json_start:json_end])

    network_type = config.get("network_type", "drive")
    waypoints = config.get("waypoints", [])
    split_routes = config.get("split_routes", False)
    priority = config.get("priority", "length")  # 'safety' vagy 'speed'
    detour_km = config.get("allow_detour_km", 0.0)

except Exception as e:
    messagebox.showwarning("LLM hiba", f"Nem sikerült feldolgozni az LLM választ, alapértelmezést használunk.\n{e}")
    network_type = "drive"
    waypoints = []
    split_routes = False
    priority = "length"
    detour_km = 0.0

# ───────────────────────────────
# 3. OSM úthálózat betöltése
# ───────────────────────────────
print(f"Úthálózat betöltése ({network_type})...")
G = ox.graph_from_place("Budapest, Hungary", network_type=network_type)

def geocode_node(address):
    latlon = ox.geocode(address + ", Budapest, Hungary")
    return ox.nearest_nodes(G, latlon[1], latlon[0])

locations = [start_address] + waypoints + [end_address]
node_list = [geocode_node(loc) for loc in locations]

# ───────────────────────────────
# 4. Útvonal kiszámítása
# ───────────────────────────────
routes = []

if split_routes and len(locations) > 2:
    for i in range(len(locations) - 1):
        routes.append(nx.shortest_path(G, node_list[i], node_list[i+1], weight="length"))
else:
    full_route = []
    for i in range(len(locations) - 1):
        segment = nx.shortest_path(G, node_list[i], node_list[i+1], weight="length")
        if i > 0:
            segment = segment[1:]
        full_route += segment
    routes = [full_route]

# ───────────────────────────────
# 5. Fájlnevek létrehozása
# ───────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
geojson_filename = f"utvonal_{timestamp}.geojson"
png_filename = f"utvonal_{timestamp}.png"

# ───────────────────────────────
# 6. GeoJSON mentése
# ───────────────────────────────
gdf_list = []
all_edges = []

for route in routes:
    coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in route]
    line = LineString(coords)
    gdf_list.append(line)
    all_edges += [
        LineString([(G.nodes[u]['x'], G.nodes[u]['y']),
                    (G.nodes[v]['x'], G.nodes[v]['y'])])
        for u, v in zip(route[:-1], route[1:])
    ]

gdf = gpd.GeoDataFrame(geometry=gdf_list, crs="EPSG:4326")
gdf.to_file(geojson_filename, driver="GeoJSON")

# ───────────────────────────────
# 7. PNG térkép generálása
# ───────────────────────────────
fig, ax = ox.plot_graph_routes(G, routes, route_colors='r', route_linewidth=4, node_size=0, bgcolor="white", show=False, close=False, figsize=(12, 12))
combined = MultiLineString(all_edges).buffer(0.001)
ax.set_xlim(combined.bounds[0], combined.bounds[2])
ax.set_ylim(combined.bounds[1], combined.bounds[3])
plt.savefig(png_filename, dpi=300)
plt.close()

# ───────────────────────────────
# 8. Visszajelzés
# ───────────────────────────────
messagebox.showinfo("Siker", f"Útvonal mentve:\n{geojson_filename}\n{png_filename}")
