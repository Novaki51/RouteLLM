import osmnx as ox
import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString
import tkinter as tk
from tkinter import simpledialog, messagebox
from datetime import datetime
import random

# ───────────────────────────────────────────────
# Függvények
# ───────────────────────────────────────────────
def parse_instruction(instruction):
    parts = [x.strip() for x in instruction.split("-")]
    return parts if len(parts) >= 2 else None

def random_color():
    return "#" + ''.join(random.choices('0123456789ABCDEF', k=6))

# ───────────────────────────────────────────────
# 1. Bemenet bekérése
# ───────────────────────────────────────────────
root = tk.Tk()
root.withdraw()

try:
    num_routes = simpledialog.askinteger("Útvonalak száma", "Hány útvonalat szeretnél megadni?", minvalue=1)
    if not num_routes:
        messagebox.showerror("Hiba", "Nem adtál meg érvényes számot.")
        exit()
except:
    messagebox.showerror("Hiba", "Nem sikerült a szám megadása.")
    exit()

route_list = []
for i in range(num_routes):
    instruction = simpledialog.askstring("Útvonal megadása",
        f"Add meg a(z) {i+1}. útvonalat:\n(pl. Kálvin tér - Hősök tere - Duna Plaza)")
    if not instruction:
        messagebox.showerror("Hiba", "Nem adtál meg útvonalat.")
        exit()
    parsed = parse_instruction(instruction)
    if not parsed:
        messagebox.showerror("Hiba", f"A(z) {i+1}. útvonal nem értelmezhető.")
        exit()
    route_list.append(parsed)

# ───────────────────────────────────────────────
# 2. Úthálózat betöltése és változók előkészítése
# ───────────────────────────────────────────────
print("Úthálózat letöltése...")
G = ox.graph_from_place("Budapest, Hungary", network_type="drive")
timestamp = datetime.now().strftime("%Y%m%d_%H%M")

all_lines = []
all_colors = []
all_paths = []

# ───────────────────────────────────────────────
# 3. Útvonalak feldolgozása
# ───────────────────────────────────────────────
for idx, places in enumerate(route_list):
    print(f"Útvonal #{idx + 1}: {places}")
    try:
        coords = [ox.geocode(place + ", Budapest, Hungary") for place in places]
        nodes = [ox.nearest_nodes(G, lon, lat) for lat, lon in coords]

        full_path = []
        for i in range(len(nodes) - 1):
            segment = nx.shortest_path(G, nodes[i], nodes[i + 1], weight="length")
            full_path.extend(segment if i == 0 else segment[1:])

        route_coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in full_path]
        route_line = LineString(route_coords)
        all_lines.append(route_line)
        all_paths.append(full_path)
        all_colors.append(random_color())

    except Exception as e:
        print(f"Hiba a(z) {idx + 1}. útvonal feldolgozása közben: {e}")

# ───────────────────────────────────────────────
# 4. GeoJSON + PNG mentés egyben
# ───────────────────────────────────────────────
if all_lines:
    # GeoJSON mentés
    gdf = gpd.GeoDataFrame(geometry=all_lines, crs="EPSG:4326")
    geojson_filename = f"utvonal_{timestamp}.geojson"
    gdf.to_file(geojson_filename, driver="GeoJSON")

    # PNG térkép létrehozása
    print("PNG térkép generálása...")
    fig, ax = plt.subplots(figsize=(12, 12))
    ox.plot_graph(G, ax=ax, show=False, close=False, node_size=0, edge_color="#cccccc", bgcolor="white")

    for i, path in enumerate(all_paths):
        xs = [G.nodes[n]['x'] for n in path]
        ys = [G.nodes[n]['y'] for n in path]
        ax.plot(xs, ys, linewidth=3, color=all_colors[i], label=f"Útvonal {i+1}")

        # Csak az adott útvonal élein megjelenő utcanevek
        drawn_streets = set()
        for u, v in zip(path[:-1], path[1:]):
            data = G.get_edge_data(u, v)
            if not data:
                continue
            edge_info = data[0] if 0 in data else next(iter(data.values()))
            edge_name = edge_info.get("name")
            if isinstance(edge_name, list):
                edge_name = ", ".join(edge_name)
            if edge_name and edge_name not in drawn_streets:
                drawn_streets.add(edge_name)
                ux, uy = G.nodes[u]['x'], G.nodes[u]['y']
                vx, vy = G.nodes[v]['x'], G.nodes[v]['y']
                mx, my = (ux + vx) / 2, (uy + vy) / 2
                ax.text(mx, my, edge_name, fontsize=7, color='gray', ha='center', va='center')

    # Jelölőpontok nevekkel
    for i, places in enumerate(route_list):
        for j, place in enumerate(places):
            try:
                coord = ox.geocode(place + ", Budapest, Hungary")
                ax.plot(coord[1], coord[0], marker='o', markersize=6, color=all_colors[i])
                label = "Start" if j == 0 else "End" if j == len(places) - 1 else "Waypoint"
                ax.text(coord[1], coord[0], f"{label}: {place}", fontsize=8, color=all_colors[i], ha='left', va='bottom')
            except Exception as e:
                print(f"Hiba a(z) {place} címkézésekor: {e}")

    # Zoom az útvonalakra
    combined_geom = MultiLineString(all_lines).buffer(0.001)
    ax.set_xlim(combined_geom.bounds[0], combined_geom.bounds[2])
    ax.set_ylim(combined_geom.bounds[1], combined_geom.bounds[3])

    ax.legend()
    png_filename = f"utvonal_{timestamp}.png"
    plt.savefig(png_filename, dpi=300)
    plt.close()

    messagebox.showinfo("Siker", f"Mentve:\n{geojson_filename}\n{png_filename}")
else:
    messagebox.showerror("Hiba", "Nem sikerült útvonalakat létrehozni.")

