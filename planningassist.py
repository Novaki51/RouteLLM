#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from skimage import io, color, morphology
from skimage.morphology import skeletonize, footprint_rectangle
from skimage.measure import label, regionprops
import networkx as nx
from itertools import permutations

# Matplotlib → Tkinter backend
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

def detect_red_markers(img):
    """
    Find all pure-red centroids in the image (R>200, G,B<80).
    Must find at least 2 markers.
    """
    red_mask = (img[:, :, 0] > 200) & (img[:, :, 1] < 80) & (img[:, :, 2] < 80)
    lbl = label(red_mask)
    props = regionprops(lbl)
    if len(props) < 2:
        raise RuntimeError(f"Found {len(props)} red markers; need at least 2")
    return [tuple(map(int, p.centroid)) for p in props]

def build_road_mask(img):
    """
    Return a boolean mask of grey roads, excluding green parks & water.
    """
    hsv = color.rgb2hsv(img)
    gray = color.rgb2gray(img)
    hue, sat, val = hsv[...,0], hsv[...,1], hsv[...,2]

    # Mask parks (green) and water (blue)
    green = (hue > 0.2) & (hue < 0.45) & (sat > 0.3) & (val > 0.2)
    water = (hue > 0.5) & (hue < 0.7) & (sat > 0.3) & (val < 0.8)

    # Grey roads = mid-bright gray + low saturation, excluding parks & water
    road = (gray > 0.3) & (gray < 0.9) & (sat < 0.25) & (~green) & (~water)
    # Fill small gaps with a 3×3 rectangle footprint
    return morphology.dilation(road, footprint_rectangle((3,3)))

def build_skeleton_graph(road_mask):
    """
    Skeletonize the road mask and build an 8-connected graph of skeleton pixels.
    """
    skel = skeletonize(road_mask)
    pts = set(zip(*np.nonzero(skel)))
    G = nx.Graph()
    neighbors = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx) != (0,0)]
    for y, x in pts:
        for dy, dx in neighbors:
            nb = (y+dy, x+dx)
            if nb in pts:
                G.add_edge((y, x), nb, weight=np.hypot(dy, dx))
    return G

def snap_to_graph(pt, nodes):
    """
    Snap a (row, col) point to the nearest graph node by Manhattan distance.
    """
    arr = np.array(list(nodes))
    d = np.abs(arr - pt).sum(axis=1)
    return tuple(arr[np.argmin(d)])

def find_tsp_order(G, pts):
    """
    Given graph G and a list of waypoint-nodes pts,
    brute-force the best permutation minimizing total graph-distance.
    """
    # Precompute all-pairs shortest-path lengths among the waypoints
    dist = {u: nx.single_source_dijkstra_path_length(G, u, weight='weight')
            for u in pts}

    best_cost = np.inf
    best_perm = None
    for perm in permutations(pts):
        total = 0.0
        for a, b in zip(perm[:-1], perm[1:]):
            d = dist[a].get(b, np.inf)
            total += d
            if total >= best_cost:
                break
        else:
            best_cost = total
            best_perm = perm

    if best_perm is None:
        raise RuntimeError("No valid path visiting all waypoints")
    return best_perm

def process_image(path, canvas, ax):
    # Load image
    img = io.imread(path)
    if img.ndim == 3 and img.shape[2] == 4:
        img = img[..., :3]

    # 1) Detect all red markers
    raw_pts = detect_red_markers(img)

    # 2) Build road mask and skeleton graph
    road_mask = build_road_mask(img)
    G = build_skeleton_graph(road_mask)

    # 3) Snap all markers to graph nodes
    snapped = [snap_to_graph(pt, G.nodes()) for pt in raw_pts]

    # 4) Find optimal visiting order (TSP)
    order = find_tsp_order(G, snapped)

    # 5) Reconstruct full path by concatenating shortest subpaths
    full_path = []
    for a, b in zip(order[:-1], order[1:]):
        seg = nx.shortest_path(G, source=a, target=b, weight='weight')
        if not full_path:
            full_path.extend(seg)
        else:
            full_path.extend(seg[1:])

    # 6) Plot on the Matplotlib axes
    ax.clear()
    ax.imshow(img)
    ys, xs = zip(*full_path)
    ax.plot(xs, ys, 'r-', linewidth=2)
    # Mark original waypoints
    for pt in raw_pts:
        ax.scatter(pt[1], pt[0], c='r', s=80)
    ax.axis('off')
    canvas.draw()

def on_open(canvas, ax):
    fname = filedialog.askopenfilename(
        title="Open Map Image",
        filetypes=[("Image files","*.png *.jpg *.jpeg *.bmp"),("All files","*.*")]
    )
    if not fname:
        return
    try:
        process_image(fname, canvas, ax)
    except Exception as e:
        messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Road-Only Multi-Point Route Planner")
    root.geometry("1000x600")

    # Left control panel with the upload button
    ctrl = tk.Frame(root, width=200, padx=10, pady=10)
    ctrl.pack(side=tk.LEFT, fill=tk.Y)
    btn = tk.Button(ctrl, text="Open Map…",
                    command=lambda: on_open(canvas, ax),
                    width=20, height=2)
    btn.pack(pady=20)

    # Right display panel with embedded Matplotlib
    disp = tk.Frame(root)
    disp.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    fig, ax = plt.subplots(figsize=(6,6))
    canvas = FigureCanvasTkAgg(fig, master=disp)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    root.mainloop()
