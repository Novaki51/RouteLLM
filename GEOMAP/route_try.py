import subprocess
import json
import sys
from typing import List, Tuple

# Ensure required packages are installed: pip install geopy folium
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError
    import folium
except ImportError as e:
    print(f"Missing dependency: {e.name}. Please install via pip (e.g., pip install geopy folium)", file=sys.stderr)
    sys.exit(1)

class OllamaRouteGenerator:
    """
    Generates driving routes between two points (lon, lat) using an Ollama model via CLI.
    """
    def __init__(self, model_name: str = "route-model", temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature

    def generate_route(self, start: Tuple[float, float], end: Tuple[float, float]) -> List[Tuple[float, float]]:
        """
        Generates a road-based route between `start` and `end` coordinates.

        Args:
            start: (lon, lat) of the start point.
            end: (lon, lat) of the end point.

        Returns:
            List of (lon, lat) tuples representing the route.
        """
        prompt = (
            f"Generate a driving route along roads from start at X={start[0]}, Y={start[1]} "
            f"to end at X={end[0]}, Y={end[1]}. Return the path as a JSON list of [x, y] points."
        )
        try:
            result = subprocess.run(
                [
                    "ollama", "run", self.model_name,
                    "prompt", prompt,
                    "temperature", str(self.temperature),
                    "json"
                ],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error calling Ollama CLI: {e.stderr}", file=sys.stderr)
            raise

        data = json.loads(result.stdout)
        coords = data.get("coordinates", data)
        return [tuple(point) for point in coords]


def geocode_address(address: str) -> Tuple[float, float]:
    """
    Geocodes an address to (lon, lat) coordinates using Nominatim.
    """
    geolocator = Nominatim(user_agent="route_generator")
    try:
        location = geolocator.geocode(address)
    except GeocoderServiceError as e:
        print(f"Geocoding error: {e}", file=sys.stderr)
        sys.exit(1)
    if not location:
        print(f"Could not geocode address: {address}", file=sys.stderr)
        sys.exit(1)
    return (location.longitude, location.latitude)


def plot_route(coords: List[Tuple[float, float]], output_file: str = 'route_map.html') -> None:
    """
    Plots the route on an interactive map and saves to HTML.
    """
    lons, lats = zip(*coords)
    center = (sum(lats) / len(lats), sum(lons) / len(lons))
    m = folium.Map(location=center, zoom_start=13)
    # Draw polyline (swap to lat, lon)
    line = [(lat, lon) for lon, lat in coords]
    folium.PolyLine(locations=line, weight=5).add_to(m)
    # Start & End markers
    folium.Marker(location=line[0], popup='Start').add_to(m)
    folium.Marker(location=line[-1], popup='End').add_to(m)
    m.save(output_file)
    print(f"Map saved to {output_file}")


def main():
    print("Enter locations one per line (start, optional waypoints, end).\n"  
          "Press Enter on empty line to finish:")
    addresses: List[str] = []
    while True:
        addr = input("Location: ").strip()
        if not addr:
            break
        addresses.append(addr)

    if len(addresses) < 2:
        print("Please enter at least a start and an end location.", file=sys.stderr)
        sys.exit(1)

    coords: List[Tuple[float, float]] = [geocode_address(addr) for addr in addresses]
    generator = OllamaRouteGenerator()
    full_route: List[Tuple[float, float]] = []

    for i in range(len(coords) - 1):
        segment = generator.generate_route(coords[i], coords[i+1])
        if i == 0:
            full_route.extend(segment)
        else:
            full_route.extend(segment[1:])

    print(json.dumps({"route": full_route}, indent=2))
    plot_route(full_route)

if __name__ == "__main__":
    main()
