#!/usr/bin/env python3
"""
GUI converter: Tkinter ablakkal kér be az útvonal pontjait a térképről származó szöveges listaként,
valamint a térképen mért centit, valós métert és DPI-t,
majd kiszámolja és megjeleníti a valós X-Y méter koordinátákat,
valamint a teljes útvonal hosszát méterben.
"""
import tkinter as tk
from tkinter import messagebox
import re
import math


def parse_pixel_list(raw_text):
    # Keresünk minden '(x, y)'-t
    matches = re.findall(r"\((\d+)\s*,\s*(\d+)\)", raw_text)
    if not matches:
        raise ValueError("Nem található érvényes pixel koordináta. Használj '(x, y)' formátumot.")
    return [(int(x), int(y)) for x, y in matches]

class ConverterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pixel→Valós Koordináta Konverter")
        self.geometry("500x600")
        self._build_widgets()

    def _build_widgets(self):
        pad = 5
        tk.Label(self, text="Útvonal pontjai (szövegesen másold be):").pack(pady=(pad,0))
        self.coords_text = tk.Text(self, height=10)
        self.coords_text.pack(fill=tk.BOTH, padx=pad)

        tk.Label(self, text="Térképen mért távolság (cm):").pack(pady=(pad,0))
        self.map_cm_entry = tk.Entry(self)
        self.map_cm_entry.pack(fill=tk.X, padx=pad)

        tk.Label(self, text="Valós távolság (m):").pack(pady=(pad,0))
        self.real_m_entry = tk.Entry(self)
        self.real_m_entry.pack(fill=tk.X, padx=pad)

        tk.Label(self, text="DPI (pont/hüvelyk):").pack(pady=(pad,0))
        self.dpi_entry = tk.Entry(self)
        self.dpi_entry.insert(0, "96")
        self.dpi_entry.pack(fill=tk.X, padx=pad)

        tk.Button(self, text="Számítás", command=self.calculate).pack(pady=pad)

        tk.Label(self, text="Eredmények:").pack(pady=(pad,0))
        self.result_text = tk.Text(self, height=12)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=pad, pady=(0,pad))

    def calculate(self):
        raw = self.coords_text.get("1.0", tk.END)
        try:
            pairs = parse_pixel_list(raw)
        except Exception as e:
            messagebox.showerror("Hiba", str(e))
            return
        try:
            map_cm = float(self.map_cm_entry.get())
            real_m = float(self.real_m_entry.get())
            dpi = float(self.dpi_entry.get())
        except:
            messagebox.showerror("Hiba", "Kérlek számokat adj meg a mezőkben! (cm, m, DPI)")
            return
        if map_cm <= 0 or real_m <= 0 or dpi <= 0:
            messagebox.showerror("Hiba", "Minden érték legyen nagyobb nullánál.")
            return
        # Számítás
        cm_per_px = 2.54 / dpi
        m_per_cm = real_m / map_cm
        m_per_px = m_per_cm * cm_per_px
        # Teljes út hosszának kiszámítása
        total_px = 0.0
        for (x1, y1), (x2, y2) in zip(pairs[:-1], pairs[1:]):
            total_px += math.hypot(x2 - x1, y2 - y1)
        total_m = total_px * m_per_px
        # Eredmény megjelenítése
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, f"Teljes út hossza: {total_m:.2f} m\n\n")
        self.result_text.insert(tk.END, "Valós koordináták (m, két tizedesjegy):\n")
        for i, (x, y) in enumerate(pairs, 1):
            xr = x * m_per_px
            yr = y * m_per_px
            self.result_text.insert(tk.END, f"{i}. ({xr:.2f} m, {yr:.2f} m)\n")

if __name__ == '__main__':
    app = ConverterGUI()
    app.mainloop()
