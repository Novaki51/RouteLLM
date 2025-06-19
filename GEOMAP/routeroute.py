import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import osmnx as ox
import networkx as nx
import pandas as pd
import sys
import subprocess
import ollama
import re
from PIL import Image

class RoutePlannerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Budapest útvonaltervező (kép/szöveg)")

        self.left_frame = tk.Frame(master)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right_frame = tk.Frame(master, width=320)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.fig, self.ax = plt.subplots(figsize=(6, 7))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.left_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- INPUT választó gombok ---
        ttk.Label(self.right_frame, text="Válaszd ki a bemenet típusát:", font=('Arial', 12, 'bold')).pack(pady=15)
        self.input_mode = tk.StringVar(value="text")
        ttk.Radiobutton(self.right_frame, text="Szöveges cím", variable=self.input_mode, value="text").pack(anchor='w', padx=10)
        ttk.Radiobutton(self.right_frame, text="Kép (piros pontokkal)", variable=self.input_mode, value="image").pack(anchor='w', padx=10)
        self.mode_button = ttk.Button(self.right_frame, text="Tovább", command=self.next_step)
        self.mode_button.pack(pady=10)

        # --- Szöveges input mezők ---
        self.text_input_frame = tk.Frame(self.right_frame)
        ttk.Label(self.text_input_frame, text="Indulási pont (pl. Kálvin tér, Budapest):").pack(pady=(20,5))
        self.start_entry = ttk.Entry(self.text_input_frame, width=30)
        self.start_entry.pack()
        ttk.Label(self.text_input_frame, text="Érkezési pont (pl. Népliget, Budapest):").pack(pady=(20,5))
        self.end_entry = ttk.Entry(self.text_input_frame, width=30)
        self.end_entry.pack()
        self.plan_text_button = ttk.Button(self.text_input_frame, text="Útvonal tervezése", command=self.plan_text_route)
        self.plan_text_button.pack(pady=30)

        # --- Kép input mező ---
        self.image_input_frame = tk.Frame(self.right_frame)
        self.image_path_var = tk.StringVar()
        ttk.Label(self.image_input_frame, text="Válassz egy képet (piros pontokkal):").pack(pady=(20,5))
        self.image_select_button = ttk.Button(self.image_input_frame, text="Kép kiválasztása", command=self.select_image)
        self.image_select_button.pack()
        self.selected_image_label = ttk.Label(self.image_input_frame, textvariable=self.image_path_var)
        self.selected_image_label.pack(pady=10)
        self.plan_image_button = ttk.Button(self.image_input_frame, text="Képalapú útvonal tervezése", command=self.plan_image_route)
        self.plan_image_button.pack(pady=30)

        self.plot_blank_map()  # Elsőként mindig Budapest üres úthálózata

    def plot_blank_map(self):
        self.ax.clear()
        # Budapest: teljes város autós úthálózat (letöltve, ha még nincs cache-ben)
        self.base_graph = ox.graph_from_place("Budapest, Hungary", network_type='drive')
        ox.plot_graph(self.base_graph, ax=self.ax, show=False, close=False, bgcolor='w', node_size=0, edge_color="#cccccc")
        self.ax.set_title("Budapest úthálózata", fontsize=14)
        self.canvas.draw()

    def next_step(self):
        # Bemenet típus szerint GUI elemek aktiválása
        for widget in self.right_frame.winfo_children():
            if widget not in [self.mode_button, ]:
                widget.pack_forget()
        if self.input_mode.get() == "text":
            self.text_input_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.image_input_frame.pack(fill=tk.BOTH, expand=True)

    # --- Szöveges mód: OSMnx alapú routing, LLM NEM kell ---
    def plan_text_route(self):
        start = self.start_entry.get()
        end = self.end_entry.get()
        if not start or not end:
            messagebox.showwarning("Hiányzó adat", "Adj meg mindkét címet!")
            return
        try:
            G = self.base_graph
            start_latlon = ox.geocode(start)
            end_latlon = ox.geocode(end)
            start_node = ox.distance.nearest_nodes(G, start_latlon[1], start_latlon[0])
            end_node = ox.distance.nearest_nodes(G, end_latlon[1], end_latlon[0])
            route = nx.shortest_path(G, start_node, end_node, weight='length')
            # Projekció Budapest UTM zónába, x-y
            G_proj = ox.project_graph(G)
            route_proj = nx.shortest_path(G_proj, start_node, end_node, weight='length')
            xys = [(G_proj.nodes[n]['x'], G_proj.nodes[n]['y']) for n in route_proj]
            df = pd.DataFrame(xys, columns=['X', 'Y'])
            df.to_csv("route_xy.csv", index=False)

            self.plot_route_on_base_map(xys, title=f"{start} → {end} (x-y)")
            messagebox.showinfo("Siker", "Az útvonal kimentve: route_xy.csv")
        except Exception as e:
            messagebox.showerror("Hiba", f"Nem sikerült az útvonaltervezés:\n{e}")

    # --- Képes mód: LLM detektálja a pontokat, routing OSMnx-szel ---
    def select_image(self):
        filepath = filedialog.askopenfilename(
            title="Válassz egy képet",
            filetypes=[("PNG képek", "*.png"), ("JPG képek", "*.jpg *.jpeg"), ("Minden", "*.*")]
        )
        if filepath:
            self.image_path_var.set(filepath)

    def plan_image_route(self):
        filepath = self.image_path_var.get()
        if not filepath:
            messagebox.showwarning("Hiányzó adat", "Előbb válassz ki egy képet!")
            return
        # 1. Képből pontdetektálás LLM-mel
        try:
            points = self.detect_points_with_llm(filepath)
            if len(points) < 2:
                messagebox.showerror("Hiba", "Nem sikerült legalább két piros pontot találni!")
                return
            # 2. Képpontokból geo-koordináta konvertálás (pl. minta alapján, vagy referencia)
            # (itt példaként lineáris transzformáció - fejlett esetben referenciakép alapján)
            # Feltételezzük: Budapest-térképes mintaképnél a sarkok koordinátáit is ismerjük,
            # és lineáris arányosítást végzünk (pl. egy referenciakép alapján, vagy adott min/max lat-lon)
            # Példaként: (referenciapontok használata!)
            # user egy mintaképet ad, aminek pl. bal-felső és jobb-alsó sarkánál megadja a valós geo koordinátákat!
            geo_points = self.image_pixels_to_geocoords(points, filepath)
            if len(geo_points) < 2:
                messagebox.showerror("Hiba", "Nem sikerült legalább két földrajzi pontot számolni!")
                return

            # 3. OSMnx routing a detektált pontok között
            G = self.base_graph
            start_latlon, end_latlon = geo_points[0], geo_points[1]
            start_node = ox.distance.nearest_nodes(G, start_latlon[1], start_latlon[0])
            end_node = ox.distance.nearest_nodes(G, end_latlon[1], end_latlon[0])
            route = nx.shortest_path(G, start_node, end_node, weight='length')
            # UTM projekció
            G_proj = ox.project_graph(G)
            route_proj = nx.shortest_path(G_proj, start_node, end_node, weight='length')
            xys = [(G_proj.nodes[n]['x'], G_proj.nodes[n]['y']) for n in route_proj]
            df = pd.DataFrame(xys, columns=['X', 'Y'])
            df.to_csv("route_xy.csv", index=False)

            self.plot_route_on_base_map(xys, title=f"Képes útvonal (x-y)")
            messagebox.showinfo("Siker", "A képalapú útvonal kimentve: route_xy.csv")
        except Exception as e:
            messagebox.showerror("Hiba", f"Kép alapú útvonaltervezési hiba:\n{e}")

    def detect_points_with_llm(self, image_path, model="llava:13b"):
        # Ollama multimodális LLM-hez prompt
        prompt = (
            "A képen piros körrel jelölt pontokat kell keresned, amelyek a térkép start és cél helyét jelentik. "
            "Add vissza az összes piros pont pixel koordinátáját egy python listaként, pl: [(x1, y1), (x2, y2), ...]. "
            "Csak a python listát add vissza, semmi mást!"
        )
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
        # Feltételezzük, hogy az Ollama multimodális API képes ilyen kérésre (pl. LLaVA)
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            images=[image_bytes]
        )
        text = response['message']['content']
        # Kinyerjük a python listát
        points = eval(re.search(r"(\[.*\])", text, re.DOTALL).group(1))
        return points

    def image_pixels_to_geocoords(self, points, filepath):
        # Ehhez kell egy referencia: pl. a kép bal-felső (x0, y0) pixeléhez tartozik (lat0, lon0),
        # jobb-alsó (x1, y1) pixeléhez tartozik (lat1, lon1) geo koordináta.
        # Ezt vagy a user adja meg, vagy a képfájl nevénél van, vagy előre beégeted.
        # Itt most példaként Budapest teljes térképén:
        # bal-felső sarkánál (lat0, lon0) = (47.54, 19.00)
        # jobb-alsó sarkánál (lat1, lon1) = (47.42, 19.15)
        img = Image.open(filepath)
        width, height = img.size
        lat0, lon0 = 47.54, 19.00
        lat1, lon1 = 47.42, 19.15
        geo_points = []
        for (x, y) in points:
            lat = lat0 + (lat1 - lat0) * (y / height)
            lon = lon0 + (lon1 - lon0) * (x / width)
            geo_points.append((lat, lon))
        return geo_points

    def plot_route_on_base_map(self, xys, title="Útvonal (x-y)"):
        self.ax.clear()
        # (1) Budapest projekciós úthálózat lekérése vagy már cache-elt változat használata:
        try:
            G_proj = ox.project_graph(self.base_graph)
        except Exception:
            G_proj = self.base_graph  # ha már projektált

        # (2) Úthálózat kirajzolása szürke színnel
        ox.plot_graph(
            G_proj, ax=self.ax, show=False, close=False,
            bgcolor='w', node_size=0, edge_color="#bbbbbb"
        )

        # (3) Útvonal rárajzolása piros vastag vonallal
        xs, ys = zip(*xys)
        self.ax.plot(xs, ys, color='red', linewidth=4, alpha=0.9, zorder=10, label="Útvonal (x-y)")

        self.ax.set_xlabel("X (meter)")
        self.ax.set_ylabel("Y (meter)")
        self.ax.set_title(title, fontsize=13)
        margin = 50
        self.ax.set_xlim(min(xs) - margin, max(xs) + margin)
        self.ax.set_ylim(min(ys) - margin, max(ys) + margin)
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = RoutePlannerGUI(root)
    root.mainloop()
