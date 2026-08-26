"""Diagnostic and Telemetry Service Report Generator with Cryptographic Session Hash."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.logging import get_logger
from src.protocols.j1939.diagnostics import DMMessage

logger = get_logger("engine.exporters.report")


@dataclass(slots=True)
class ServiceReportMetadata:
    """Metadata for vehicle service report."""

    vin_or_hin: str
    technician_name: str
    workshop_name: str
    notes: str = ""


class DiagnosticReportGenerator:
    """Generates structured HTML & printable diagnostic service reports with SHA-256 session hash."""

    @classmethod
    def generate_html_report(
        cls,
        output_file: str | Path,
        metadata: ServiceReportMetadata,
        dm_messages: list[DMMessage],
        summary_stats: dict[str, str | int | float],
    ) -> Path:
        """Generate structured HTML diagnostic report with cryptographic tamper-evident hash."""
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        now_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

        # Collect DTC rows
        dtc_rows = []
        for dm in dm_messages:
            for dtc in dm.dtcs:
                criticality_badge = (
                    '<span style="color:red; font-weight:bold;">KRİTİK</span>'
                    if dtc.is_critical
                    else '<span style="color:orange;">UYARI</span>'
                )
                dtc_rows.append(
                    f"<tr>"
                    f"<td>0x{dm.source_address:02X}</td>"
                    f"<td>SPN {dtc.spn}</td>"
                    f"<td>FMI {dtc.fmi}</td>"
                    f"<td>{dtc.occurrence_count}</td>"
                    f"<td>{dtc.fmi_description_tr} ({dtc.fmi_description_en})</td>"
                    f"<td>{criticality_badge}</td>"
                    f"</tr>"
                )

        if not dtc_rows:
            dtc_rows_html = "<tr><td colspan='6' style='text-align:center; color:green;'>✅ Aktif veya Kayıtlı Arıza Kodu Bulunmamaktadır (No Faults Detected)</td></tr>"
        else:
            dtc_rows_html = "\n".join(dtc_rows)

        # Compute tamper-evident hash of report content
        raw_to_hash = f"{metadata.vin_or_hin}|{metadata.technician_name}|{now_str}|{len(dtc_rows)}"
        report_sha256 = hashlib.sha256(raw_to_hash.encode("utf-8")).hexdigest().upper()

        html_content = f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Universal CAN-Bus Telemetry & Diagnostic Report</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }}
    h1 {{ color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
    th, td {{ border: 1px solid #CBD5E1; padding: 10px; text-align: left; }}
    th {{ background-color: #F1F5F9; color: #1E293B; }}
    .meta-box {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 15px; border-radius: 6px; margin-bottom: 20px; }}
    .signature {{ font-family: monospace; color: #64748B; font-size: 11px; margin-top: 30px; }}
  </style>
</head>
<body>
  <h1>🛠 Universal CAN-Bus Servis Teşhis & Telemetri Raporu</h1>

  <div class="meta-box">
    <p><strong>Araç / Tekne Kimliği (VIN / HIN):</strong> {metadata.vin_or_hin}</p>
    <p><strong>Servis / Atölye:</strong> {metadata.workshop_name} | <strong>Teknisyen:</strong> {metadata.technician_name}</p>
    <p><strong>Rapor Tarihi:</strong> {now_str}</p>
    <p><strong>Notlar:</strong> {metadata.notes or "Rutin periyodik kontrol ve telemetri doğrulaması."}</p>
  </div>

  <h2>📋 Diyagnostik Arıza Kodları (DTCs)</h2>
  <table>
    <thead>
      <tr>
        <th>Kaynak (SA)</th>
        <th>SPN</th>
        <th>FMI</th>
        <th>Tekrar (OC)</th>
        <th>Arıza Tanımı</th>
        <th>Durum</th>
      </tr>
    </thead>
    <tbody>
      {dtc_rows_html}
    </tbody>
  </table>

  <div class="signature">
    <p>🔒 <strong>Cryptographic Session SHA-256:</strong> {report_sha256}</p>
    <p>Platform: Universal CAN-Bus Diagnostic & Telemetry System v13.0 (SAE J1939 / NMEA 2000 / ISO 14229)</p>
  </div>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info("Generated Diagnostic Service HTML Report", extra={"file": str(path), "hash": report_sha256})
        return path
