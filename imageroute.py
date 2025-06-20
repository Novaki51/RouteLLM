import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from skimage import io, color, morphology
from skimage.morphology import skeletonize, footprint_rectangle
from skimage.measure import label, regionprops
import networkx as nx
from itertools import permutations
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

def detect_red_markers(img):
    red_mask = (img[:, :, 0] > 200) & (img[:, :, 1] < 80) & (img[:, :, 2] < 80)
    lbl = label(red_mask)
    props = regionprops(lbl)
    if len(props) < 2:
        raise RuntimeError(f"Found {len(props)} red markers; need at least 2")
    return [tuple(map(int, p.centroid)) for p in props]

def build_road_mask(img):
    hsv = color.rgb2hsv(img)
    gray = color.rgb2gray(img)
    hue, sat, val = hsv[...,0], hsv[...,1], hsv[...,2]
    green = (hue > 0.2) & (hue < 0.45) & (sat > 0.3) & (val > 0.2)
    water = (hue > 0.5) & (hue < 0.7) & (sat > 0.3) & (val < 0.8)
    road = (gray > 0.3) & (gray < 0.9) & (sat < 0.25) & (~green) & (~water)
    return morphology.dilation(road, footprint_rectangle((3,3)))

def build_skeleton_graph(road_mask):
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
    arr = np.array(list(nodes))
    d = np.abs(arr - pt).sum(axis=1)
    return tuple(arr[np.argmin(d)])

def find_tsp_order(G, pts):
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
    # 6) Plot on axes
    ax.clear()
    ax.imshow(img)
    ys, xs = zip(*full_path)
    ax.plot(xs, ys, 'r-', linewidth=2)
    for pt in raw_pts:
        ax.scatter(pt[1], pt[0], c='r', s=80)
    ax.axis('off')
    canvas.draw()
    # Save image dialog
    save_img = messagebox.askyesno("Save Result", "Do you want to save the plotted route image?")
    if save_img:
        filetypes = [("PNG Image", "*.png"), ("All files", "*.*")]
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=filetypes)
        if file_path:
            fig = ax.get_figure()
            fig.savefig(file_path, bbox_inches='tight', dpi=150)
            messagebox.showinfo("Saved", f"Image saved as: {file_path}")
    # Save CSV dialog
    save_csv = messagebox.askyesno("Save Route CSV", "Do you want to save the pixel coordinates of the route as CSV?")
    if save_csv:
        filetypes = [("CSV file", "*.csv"), ("All files", "*.*")]
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=filetypes)
        if file_path:
            pd.DataFrame({'X': xs, 'Y': ys}).to_csv(file_path, index=False)
            messagebox.showinfo("Saved", f"CSV saved as: {file_path}")

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
    ctrl = tk.Frame(root, width=200, padx=10, pady=10)
    ctrl.pack(side=tk.LEFT, fill=tk.Y)
    btn = tk.Button(ctrl, text="Open Map…",
                    command=lambda: on_open(canvas, ax),
                    width=20, height=2)
    btn.pack(pady=20)
    disp = tk.Frame(root)
    disp.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    fig, ax = plt.subplots(figsize=(6,6))
    canvas = FigureCanvasTkAgg(fig, master=disp)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    root.mainloop()
