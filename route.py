import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString
import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime
import os

# ───────────────────────────────────────
# 1. Dátum alapú fájlnév
# ───────────────────────────────────────
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
geojson_filename = f"utvonal_{timestamp}.geojson"
png_filename = f"utvonal_{timestamp}.png"

# ───────────────────────────────────────
# 2. INPUT bekérése grafikus ablakból
# ───────────────────────────────────────
root = tk.Tk()
root.withdraw()

start_address = simpledialog.askstring("Útvonaltervezés", "Add meg a kiindulási pontot:")
end_address = simpledialog.askstring("Útvonaltervezés", "Add meg a célpontot:")

if not start_address or not end_address:
    messagebox.showerror("Hiba", "Mindkét pontot meg kell adni.")
    exit()

# ───────────────────────────────────────
# 3. Úthálózat letöltése
# ───────────────────────────────────────
print("Úthálózat letöltése...")
G = ox.graph_from_place("Budapest, Hungary", network_type="drive")

# ───────────────────────────────────────
# 4. Helyek geokódolása és útvonal
# ───────────────────────────────────────
print("Helyszínek geokódolása...")
start_coords = ox.geocode(start_address + ", Budapest, Hungary")
end_coords = ox.geocode(end_address + ", Budapest, Hungary")

start_node = ox.nearest_nodes(G, start_coords[1], start_coords[0])
end_node = ox.nearest_nodes(G, end_coords[1], end_coords[0])

print("Útvonal számítása...")
route = nx.shortest_path(G, start_node, end_node, weight="length")

# ───────────────────────────────────────
# 5. GeoJSON mentés
# ───────────────────────────────────────
route_coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in route]
route_line = LineString(route_coords)

gdf = gpd.GeoDataFrame(index=[0], geometry=[route_line], crs="EPSG:4326")
gdf.to_file(geojson_filename, driver="GeoJSON")

# ───────────────────────────────────────
# 6. PNG térkép mentés (zoomolva)
# ───────────────────────────────────────
print("Kép generálása...")
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
