import osmnx as ox
import matplotlib.pyplot as plt

# Beállítjuk a térképek követelményeit
ox.config(log_console=False)

# Válasszunk egy települést (pl. Budapest)
G = ox.graph_from_place('Budapest', network_type='drive')

# Generáljuk az útvonalakat
routes = []
for i in range(5):  # két útvonalat generálunk
    route = ox.shortest_path(G, 'Déli pályaudvar', 'Pestszentlőrinc', method='dijkstra')
    routes.append(route)

# Mentjük az útvonalakat GeoJSON formátumban
import geopy.geodesic as geodesic
from shapely.geometry import LineString

route_geojson = []
for route in routes:
    coords = [(G.nodes[u]['x'], G.nodes[u]['y']) for u in route]
    geojson_route = {
        'type': 'Feature',
        'geometry': {'type': 'LineString', 'coordinates': coords},
        'properties': {}
    }
    route_geojson.append(geojson_route)

import json
with open('route.geojson', 'w') as f:
    json.dump(route_geojson, f)

# Részletekkel vonva rajzoljuk az útvonalakat
fig, ax = plt.subplots(figsize=(10, 8))
ox.plot_graph(G, node_zorder=2, edge_color='gray')
for route in routes:
    coords = [(G.nodes[u]['x'], G.nodes[u]['y']) for u in route]
    ax.plot([c[0] for c in coords], [c[1] for c in coords], 'r', alpha=0.5)
plt.savefig('route.png')