"""Google Earth KML GPS Track Exporter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from src.core.logging import get_logger

logger = get_logger("engine.exporters.kml")


@dataclass(slots=True)
class GpsPoint:
    """GPS coordinate waypoint."""

    latitude: float
    longitude: float
    altitude_m: float = 0.0
    speed_knots: float = 0.0
    timestamp_iso: str = ""


class KmlExporter:
    """Exports GPS coordinates into standard Google Earth .kml paths."""

    @classmethod
    def export_track(
        cls,
        output_file: str | Path,
        track_name: str,
        points: list[GpsPoint],
    ) -> Path:
        """Export GPS waypoints list into KML file."""
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        # XML-escape user-supplied track name (F-02, CWE-91)
        safe_track_name = xml_escape(track_name)

        coords_str = " ".join(f"{p.longitude},{p.latitude},{p.altitude_m}" for p in points)

        kml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{safe_track_name}</name>
    <Style id="trackLine">
      <LineStyle>
        <color>ff0000ff</color>
        <width>4</width>
      </LineStyle>
    </Style>
    <Placemark>
      <name>{safe_track_name} Path</name>
      <styleUrl>#trackLine</styleUrl>
      <LineString>
        <extrude>1</extrude>
        <tessellate>1</tessellate>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
          {coords_str}
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(kml_content)

        logger.info("Saved Google Earth KML track", extra={"file": str(path), "points": len(points)})
        return path
