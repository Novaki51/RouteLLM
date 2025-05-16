import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import LineString
from shapely.geometry import MultiLineString
from descartes import PolygonPatch

# IX. kerület autós úthálózat
G = ox.graph_from_place("Budapest IX., Hungary", network_type="drive")

# Pontok geokódolása
origin = ox.geocode("Kálvin tér, Budapest")
destination = ox.geocode("Ferenc tér, Budapest")

# Csomópontok hozzárendelése
origin_node = ox.nearest_nodes(G, origin[1], origin[0])
destination_node = ox.nearest_nodes(G, destination[1], destination[0])

# Legrövidebb útvonal kiszámítása
route = nx.shortest_path(G, origin_node, destination_node, weight="length")

# List of (x, y) = (lon, lat) tuples
route_coords = [(G.nodes[n]['x'], G.nodes[n]['y']) for n in route]

# Create LineString and GeoDataFrame
route_line = LineString(route_coords)
gdf = gpd.GeoDataFrame(index=[0], geometry=[route_line], crs="EPSG:4326")

# Save to GeoJSON
gdf.to_file("budapest_park_to_ferenc_ter1.geojson", driver="GeoJSON")

# Térkép mentése képként
fig, ax = ox.plot_graph_route(G, route, route_linewidth=4, node_size=0, bgcolor="white")
plt.savefig("budapest_park_to_ferenc_ter1.png")

# ... az útvonal már ki van számolva, route, G elérhető

fig, ax = ox.plot_graph_route(
    G,
    route,
    route_linewidth=4,
    node_size=0,
    bgcolor="white",
    show=False,
    close=False,
    figsize=(12, 12)  # nagyobb kép
)

# Automatikus zoom az útvonal köré
edge_lines = [LineString([(G.nodes[u]['x'], G.nodes[u]['y']),
                          (G.nodes[v]['x'], G.nodes[v]['y'])]) for u, v in zip(route[:-1], route[1:])]

# Határvonal meghatározása
route_geom = MultiLineString(edge_lines)
buffered = route_geom.buffer(0.001)  # kis környezet

ax.set_xlim(buffered.bounds[0], buffered.bounds[2])
ax.set_ylim(buffered.bounds[1], buffered.bounds[3])

# Mentés
plt.savefig("budapest_park_to_ferenc_ter_zoomed.png", dpi=300)
plt.close()
