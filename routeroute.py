import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import osmnx as ox
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class TextRoutePlanner:
    def __init__(self, master):
        self.master = master
        self.master.title("OSMnx Route Planner - Export XY CSV")
        self.frame = tk.Frame(master)
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.right = tk.Frame(master, width=340)
        self.right.pack(side=tk.RIGHT, fill=tk.Y)

        self.fig, self.ax = plt.subplots(figsize=(7,7))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.right, text="Start address (e.g. Kálvin tér, Budapest):").pack(pady=(20,5))
        self.start_entry = ttk.Entry(self.right, width=32)
        self.start_entry.pack()
        ttk.Label(self.right, text="End address (e.g. Népliget, Budapest):").pack(pady=(20,5))
        self.end_entry = ttk.Entry(self.right, width=32)
        self.end_entry.pack()
        self.plan_btn = ttk.Button(self.right, text="Plan route", command=self.plan_route)
        self.plan_btn.pack(pady=10)
        self.save_btn = ttk.Button(self.right, text="Save x-y CSV", command=self.save_csv, state=tk.DISABLED)
        self.save_btn.pack(pady=10)

        # Output area for X-Y coordinates
        ttk.Label(self.right, text="Route X-Y coordinates:").pack(pady=(15, 2))
        self.xy_text = tk.Text(self.right, height=10, width=36, state=tk.DISABLED)
        self.xy_text.pack(pady=(0, 8))

        self.xys = None  # Holds last planned route for saving
        self.base_graph = None
        self.plot_blank_map()

    def plot_blank_map(self):
        self.ax.clear()
        try:
            self.base_graph = ox.graph_from_place("Budapest, Hungary", network_type='drive')
            ox.plot_graph(self.base_graph, ax=self.ax, show=False, close=False, bgcolor='w', node_size=0, edge_color="#cccccc")
            self.ax.set_title("Budapest road network", fontsize=14)
        except Exception:
            self.ax.set_title("Could not load map!", fontsize=14)
        self.canvas.draw()
        self.show_xy_coords(None)

    def show_xy_coords(self, xys):
        self.xy_text.config(state=tk.NORMAL)
        self.xy_text.delete(1.0, tk.END)
        if not xys:
            self.xy_text.insert(tk.END, "No route calculated yet.\n")
        else:
            self.xy_text.insert(tk.END, "  X\t\tY\n")
            for x, y in xys:
                self.xy_text.insert(tk.END, f"{x:.2f}\t{y:.2f}\n")
        self.xy_text.config(state=tk.DISABLED)

    def plan_route(self):
        start = self.start_entry.get().strip()
        end = self.end_entry.get().strip()
        self.xys = None
        self.save_btn['state'] = tk.DISABLED
        self.show_xy_coords(None)
        if not start or not end:
            messagebox.showwarning("Missing input", "Please enter start and end address!")
            return
        try:
            G = self.base_graph
            start_latlon = ox.geocode(start)
            end_latlon = ox.geocode(end)
            start_node = ox.distance.nearest_nodes(G, start_latlon[1], start_latlon[0])
            end_node = ox.distance.nearest_nodes(G, end_latlon[1], end_latlon[0])
            # Project to UTM for accurate plotting and export
            G_proj = ox.project_graph(G)
            route_proj = nx.shortest_path(G_proj, start_node, end_node, weight='length')
            xys = [(G_proj.nodes[n]['x'], G_proj.nodes[n]['y']) for n in route_proj]
            self.xys = xys

            # Plot with tight zoom
            self.ax.clear()
            ox.plot_graph(G_proj, ax=self.ax, show=False, close=False, bgcolor='w', node_size=0, edge_color="#bbbbbb")
            xs, ys = zip(*xys)
            self.ax.plot(xs, ys, color='red', linewidth=4, alpha=0.9, zorder=10, label="Route (x-y)")
            margin = 100  # meters
            self.ax.set_xlim(min(xs) - margin, max(xs) + margin)
            self.ax.set_ylim(min(ys) - margin, max(ys) + margin)
            self.ax.set_title(f"{start} → {end}", fontsize=13)
            self.ax.legend()
            self.canvas.draw()
            self.save_btn['state'] = tk.NORMAL  # Now allow saving
            self.show_xy_coords(xys)
        except Exception as e:
            messagebox.showerror("Error", f"Route planning failed:\n{e}")
            self.show_xy_coords(None)

    def save_csv(self):
        if not self.xys:
            messagebox.showerror("Error", "No route calculated yet!")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            pd.DataFrame(self.xys, columns=['X', 'Y']).to_csv(file_path, index=False)
            messagebox.showinfo("Success", f"Route saved as: {file_path}")
        else:
            messagebox.showinfo("Info", "Route not saved.")

if __name__ == "__main__":
    root = tk.Tk()
    app = TextRoutePlanner(root)
    root.mainloop()
