#!/usr/bin/env python3
"""
road_planner_gui.py

A Tkinter GUI that lets you:
 - Open any Google-Maps style screenshot with ≥2 red dots (waypoints).
 - Automatically detect the leftmost/rightmost dots as start/end.
 - Extract and skeletonize the grey road network.
 - Compute K distinct vehicle routes (Yen’s k-shortest simple paths).
 - Display them over the map with Matplotlib.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from itertools import islice
from skimage import io, color, morphology
from skimage.morphology import skeletonize, footprint_rectangle
from skimage.measure import label, regionprops
import networkx as nx
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Routing Core ---

def detect_red_markers(img):
    """Locate all pure-red centroids (R>200,G<80,B<80); need ≥2."""
    red = (img[...,0] > 200) & (img[...,1] < 80) & (img[...,2] < 80)
    lbl = label(red)
    props = regionprops(lbl)
    if len(props) < 2:
        raise RuntimeError(f"Found {len(props)} red markers; need ≥2")
    return [tuple(map(int,p.centroid)) for p in props]

def build_road_mask(img):
    """
    Tight mask of Google-Maps grey roads on light background:
    - exclude green parks & blue water
    - select very low-sat, high-bright greys
    - minimal morphological clean
    """
    hsv = color.rgb2hsv(img)
    gray = color.rgb2gray(img)
    h, s, v = hsv[...,0], hsv[...,1], hsv[...,2]

    # parks & water
    park  = (h>0.2)&(h<0.45)&(s>0.3)&(v>0.2)
    water = (h>0.5)&(h<0.7)&(s>0.3)&(v>0.4)

    # grey roads
    roads = (s<0.15)&(v>0.75)&(v<0.95)&(~park)&(~water)
    roads = morphology.dilation(roads, footprint_rectangle((3,3)))
    roads = morphology.erosion(roads, footprint_rectangle((2,2)))
    return roads

def build_skeleton_graph(road_mask):
    """Skeletonize roads and build 8-connected weighted graph."""
    sk = skeletonize(road_mask)
    pts = set(zip(*np.nonzero(sk)))
    G = nx.Graph()
    neigh = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx)!=(0,0)]
    for y,x in pts:
        for dy,dx in neigh:
            nb = (y+dy, x+dx)
            if nb in pts:
                G.add_edge((y,x), nb, weight=np.hypot(dy,dx))
    return G

def snap_to_graph(pt, nodes):
    """Snap a pixel-coordinate to nearest skeleton node (Manhattan)."""
    arr = np.array(list(nodes))
    d = np.abs(arr - pt).sum(axis=1)
    return tuple(arr[np.argmin(d)])

def plan_k_routes(G, start, end, k=3):
    """
    Generate up to k distinct simple paths from start to end
    via Yen’s algorithm (networkx.shortest_simple_paths).
    """
    gen = nx.shortest_simple_paths(G, source=start, target=end, weight='weight')
    return list(islice(gen, k))

def compress_path(path, G):
    """
    Compress a pixel path to junctions + endpoints for corridor plotting.
    """
    deg = dict(G.degree(path))
    key = {n for n,d in deg.items() if d!=2}
    key |= {path[0], path[-1]}
    out = [path[0]]
    for pt in path[1:]:
        if pt in key:
            out.append(pt)
    return out

# --- GUI & Processing ---

def process_image(path, canvas, ax, k_routes):
    # 1) Load
    img = io.imread(path)
    if img.ndim==3 and img.shape[2]==4:
        img = img[...,:3]

    # 2) Markers
    raw_pts = detect_red_markers(img)
    raw_pts.sort(key=lambda p: p[1])            # sort by x
    start_pt, end_pt = raw_pts[0], raw_pts[-1]

    # 3) Road mask → graph
    road_mask = build_road_mask(img)
    G = build_skeleton_graph(road_mask)

    # 4) Snap
    start_node = snap_to_graph(start_pt, G.nodes())
    end_node   = snap_to_graph(end_pt,   G.nodes())

    # 5) K routes
    routes = plan_k_routes(G, start_node, end_node, k=k_routes)

    # 6) Plot
    ax.clear()
    ax.imshow(img)
    colors = ["red","green","blue","orange","purple"]
    for route, col in zip(routes, colors):
        comp = compress_path(route, G)
        ys, xs = zip(*comp)
        ax.plot(xs, ys, color=col, linewidth=2, label=f"{col}")
    # waypoints
    for pt in raw_pts:
        ax.scatter(pt[1], pt[0], c='red', s=80, zorder=5)
    ax.axis('off')
    ax.legend(loc="lower right", framealpha=0.5)
    canvas.draw()

def on_open(canvas, ax, spin_k):
    fname = filedialog.askopenfilename(
        title="Select Google Maps screenshot",
        filetypes=[("Image files","*.png *.jpg *.jpeg"),("All","*.*")]
    )
    if not fname:
        return
    try:
        k = int(spin_k.get())
        process_image(fname, canvas, ax, k)
    except Exception as e:
        messagebox.showerror("Error", str(e))

if __name__=="__main__":
    root = tk.Tk()
    root.title("Google-Maps Road Route Planner")
    root.geometry("1000x600")

    # Left controls
    ctrl = tk.Frame(root, padx=10, pady=10)
    ctrl.pack(side=tk.LEFT, fill=tk.Y)
    tk.Button(ctrl, text="Open Map…",
              command=lambda: on_open(canvas, ax, spin_k),
              width=20, height=2).pack(pady=(0,20))
    tk.Label(ctrl, text="# of routes:").pack()
    spin_k = tk.Spinbox(ctrl, from_=1, to=5, width=5)
    spin_k.pack(pady=(0,20))

    # Right display
    disp = tk.Frame(root)
    disp.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    fig, ax = plt.subplots(figsize=(6,6))
    canvas = FigureCanvasTkAgg(fig, master=disp)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    root.mainloop()
