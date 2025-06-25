#!/usr/bin/env python3
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import numpy as np
import matplotlib.pyplot as plt
import csv
from skimage import io, color, morphology
from skimage.morphology import skeletonize, footprint_rectangle
from skimage.measure import label, regionprops
import networkx as nx
from itertools import permutations
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# —————————————————————————————————————
# Road-Only Multi-Point Route Planner with CSV export
# Közvetlenül méterben adja az út hosszát és pontjait,
# kéri, hogy 1 cm dim a valóságban, DPI fix 96,
# és elmenthető CSV-be.
# —————————————————————————————————————

img = None
m_per_px = None
cm_per_px = 2.54 / 96.0  # 96 DPI → cm per pixel
points_meters = []       # tárolt valós koordináták listája

def detect_red_markers(img):
    mask = (img[:, :, 0] > 200) & (img[:, :, 1] < 80) & (img[:, :, 2] < 80)
    lbl = label(mask)
    props = regionprops(lbl)
    if len(props) < 2:
        raise RuntimeError("Legalább 2 piros marker szükséges")
    return [tuple(map(int, p.centroid)) for p in props]

def build_road_mask(img):
    hsv = color.rgb2hsv(img)
    gray = color.rgb2gray(img)
    h,s,v = hsv[...,0], hsv[...,1], hsv[...,2]
    green = (h>0.2)&(h<0.45)&(s>0.3)&(v>0.2)
    water = (h>0.5)&(h<0.7)&(s>0.3)&(v<0.8)
    road = (gray>0.3)&(gray<0.9)&(s<0.25)&(~green)&(~water)
    return morphology.dilation(road, footprint_rectangle((3,3)))

def build_skeleton_graph(road_mask):
    skel = skeletonize(road_mask)
    pts = set(zip(*np.nonzero(skel)))
    G = nx.Graph()
    nbrs = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if (dy,dx)!=(0,0)]
    for y,x in pts:
        for dy,dx in nbrs:
            nb = (y+dy, x+dx)
            if nb in pts:
                G.add_edge((y,x), nb, weight=np.hypot(dy,dx))
    return G

def snap_to_graph(pt, nodes):
    arr = np.array(list(nodes))
    d = np.abs(arr - pt).sum(axis=1)
    return tuple(arr[np.argmin(d)])

def find_tsp_order(G, pts):
    dist = {u: nx.single_source_dijkstra_path_length(G,u,weight='weight') for u in pts}
    best_cost, best_perm = np.inf, None
    for perm in permutations(pts):
        total = 0.0
        for a,b in zip(perm[:-1], perm[1:]):
            total += dist[a].get(b, np.inf)
            if total >= best_cost:
                break
        else:
            best_cost, best_perm = total, perm
    if best_perm is None:
        raise RuntimeError("Nincs érvényes útvonal")
    return best_perm

def process_and_draw(canvas, ax, txt):
    global img, m_per_px, cm_per_px, points_meters
    if img is None or m_per_px is None:
        messagebox.showwarning("Hiba", "Először állítsd be a méretarányt!")
        return
    # detektálás, gráf, útvonal
    pts = detect_red_markers(img)
    G = build_skeleton_graph(build_road_mask(img))
    snapped = [snap_to_graph(p, G.nodes()) for p in pts]
    order = find_tsp_order(G, snapped)
    full = []
    for a,b in zip(order[:-1], order[1:]):
        seg = nx.shortest_path(G, source=a, target=b, weight='weight')
        full += seg if not full else seg[1:]
    # kirajzol
    ax.clear(); ax.imshow(img)
    ys,xs = zip(*full)
    ax.plot(xs, ys, 'r-', linewidth=2)
    for y,x in pts:
        ax.scatter(x, y, c='r', s=80)
    ax.axis('off'); canvas.draw()
    # valós meterek
    total_px = sum(np.hypot(x2-x1, y2-y1) for (y1,x1),(y2,x2) in zip(full[:-1], full[1:]))
    total_m = total_px * m_per_px
    # pontok méterben
    points_meters = [(x * m_per_px, y * m_per_px) for y,x in full]
    # kiírás
    txt.delete('1.0', tk.END)
    txt.insert(tk.END, f"Teljes út hossza: {total_m:.2f} m\n\n")
    txt.insert(tk.END, "Pontok (méterben):\n")
    for i,(xm,ym) in enumerate(points_meters,1):
        txt.insert(tk.END, f"  {i}. ({xm:.2f} m, {ym:.2f} m)\n")

def save_csv():
    global points_meters
    if not points_meters:
        messagebox.showwarning("Hiba", "Nincsenek koordináták, előbb tervezd meg az útvonalat!")
        return
    fn = filedialog.asksaveasfilename(
        defaultextension='.csv', filetypes=[('CSV file','*.csv')])
    if not fn:
        return
    with open(fn, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['index','x(m)','y(m)'])
        for i,(xm,ym) in enumerate(points_meters,1):
            writer.writerow([i, f"{xm:.2f}", f"{ym:.2f}"])
    messagebox.showinfo("Kész", f"Koordináták elmentve: {fn}")

def load_map(canvas, ax):
    global img, m_per_px
    fn = filedialog.askopenfilename(title="Térkép betöltése…",
        filetypes=[('Images','*.png *.jpg *.bmp'),('All files','*.*')])
    if not fn: return
    img = io.imread(fn)
    if img.ndim==3 and img.shape[2]==4: img = img[..., :3]
    m_per_px = None
    ax.clear(); ax.imshow(img); ax.axis('off'); canvas.draw()

def on_set_scale(canvas, ax, txt):
    global m_per_px, cm_per_px
    if img is None:
        messagebox.showinfo("Hiba","Először tölts be egy térképet!")
        return
    m_per_cm = simpledialog.askfloat("Méretarány",
        "1 cm térképen hány méter a valóságban?", minvalue=0.0001)
    if m_per_cm is None: return
    m_per_px = m_per_cm * cm_per_px
    process_and_draw(canvas, ax, txt)

if __name__ == '__main__':
    root = tk.Tk(); root.title("Route Planner CSV export"); root.geometry("1200x650")
    ctrl = tk.Frame(root, width=300, padx=10, pady=10); ctrl.pack(side=tk.LEFT, fill=tk.Y)
    tk.Button(ctrl, text='Térkép betöltése…', width=28, height=2,
              command=lambda: load_map(canvas,ax)).pack(pady=6)
    tk.Button(ctrl, text='Méretarány beállítása', width=28, height=2,
              command=lambda: on_set_scale(canvas,ax,txt_coords)).pack(pady=6)
    tk.Button(ctrl, text='Mentés CSV-be', width=28, height=2,
              command=save_csv).pack(pady=6)
    tk.Label(ctrl, text='Eredmények (méterben):').pack(pady=(20,5))
    txt_coords = tk.Text(ctrl, width=35, height=20); txt_coords.pack(fill=tk.BOTH, expand=True)
    disp = tk.Frame(root); disp.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
    fig,ax = plt.subplots(figsize=(6,6)); canvas = FigureCanvasTkAgg(fig,master=disp)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    root.mainloop()
