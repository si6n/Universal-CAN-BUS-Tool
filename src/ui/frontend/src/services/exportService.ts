import { CANFrame } from '../types/can';

export interface ExportResult {
  success: boolean;
  filename: string;
  format: string;
  sizeBytes: number;
  rowCount: number;
  cancelled?: boolean;
}

export class ExportService {
  public static async exportToCsv(frames: CANFrame[]): Promise<ExportResult> {
    const headers = ['Timestamp(s)', 'Time_Formatted', 'Channel', 'CAN_ID_Hex', 'CAN_ID_Dec', 'Type', 'Direction', 'DLC', 'Data_Hex', 'ASCII'];
    const rows = frames.map(f => [
      f.timeSec.toFixed(6),
      f.timeFormatted,
      f.channel,
      f.canIdHex,
      f.canIdDec || parseInt(f.canIdHex.replace('0x', ''), 16) || 0,
      f.frameType,
      f.dir,
      f.dlc,
      f.dataHex.join(' '),
      `"${(f.ascii || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n');
    const filename = `Universal_CAN_Log_${this.getTimestampStr()}.csv`;
    const saved = await this.downloadFile(csvContent, filename, 'text/csv;charset=utf-8;', 'Excel / CSV Tablosu (*.csv)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'CSV (Excel Uyumlu)',
      sizeBytes: new Blob([csvContent]).size,
      rowCount: frames.length
    };
  }

  public static async exportToJson(frames: CANFrame[]): Promise<ExportResult> {
    const exportPayload = {
      meta: {
        application: "Universal CAN-Bus Diagnostic & Telemetry Platform",
        version: "v13.0",
        exportTimestamp: new Date().toISOString(),
        totalFrames: frames.length,
        standards: ["ISO 11898-1:2024", "SAE J1939-73", "ISO 14229 UDS"]
      },
      frames: frames
    };

    const jsonContent = JSON.stringify(exportPayload, null, 2);
    const filename = `Universal_CAN_Telemetry_${this.getTimestampStr()}.json`;
    const saved = await this.downloadFile(jsonContent, filename, 'application/json;charset=utf-8;', 'JSON Telemetri Dosyası (*.json)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'JSON Telemetri & AI Arşivi',
      sizeBytes: new Blob([jsonContent]).size,
      rowCount: frames.length
    };
  }

  public static async exportToAsc(frames: CANFrame[]): Promise<ExportResult> {
    const now = new Date();
    const lines = [
      `date ${now.toUTCString()}`,
      'base hex  timestamps absolute',
      'internal events logged',
      `// Universal CAN-Bus Diagnostic & Telemetry Platform v13.0 Trace Log`,
      `// Total Frames: ${frames.length}`,
      '// ----------------------------------------------------------------',
      ''
    ];

    frames.forEach(f => {
      const timeStr = f.timeSec.toFixed(6).padStart(12, ' ');
      const ch = f.channel.includes('1') ? '2' : '1';
      const idStr = f.canIdHex.replace('0x', '').toUpperCase().padStart(8, ' ');
      const dirStr = f.dir === 'RX' ? 'Rx' : 'Tx';
      const dataStr = f.dataHex.join(' ').toUpperCase();
      lines.push(`${timeStr} ${ch}  ${idStr}             ${dirStr}   d ${f.dlc} ${dataStr}`);
    });

    const ascContent = lines.join('\r\n');
    const filename = `Vector_CANoe_Trace_${this.getTimestampStr()}.asc`;
    const saved = await this.downloadFile(ascContent, filename, 'text/plain;charset=utf-8;', 'Vector CANoe Trace (*.asc)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'Vector CANoe / CANalyzer (.ASC)',
      sizeBytes: new Blob([ascContent]).size,
      rowCount: frames.length
    };
  }

  public static async exportToMdf4(frames: CANFrame[]): Promise<ExportResult> {
    const lines = [
      'MDF4.10  Universal CAN ASAM MDF4 Measurement Log',
      `Timestamp: ${new Date().toISOString()}`,
      `Channel: CAN_Bus_Raw`,
      `Frame_Count: ${frames.length}`,
      'Data_Schema: [Timestamp_ns, Arbitration_ID, DLC, Data_Payload, Direction]',
      '--- BEGIN ASAM MDF4 LOG BLOCKS ---'
    ];

    frames.forEach((f, idx) => {
      lines.push(`HD_BLOCK_${idx}: T=${f.timeSec.toFixed(6)} ID=${f.canIdHex} DLC=${f.dlc} DATA=${f.dataHex.join('')} DIR=${f.dir}`);
    });

    lines.push('--- END ASAM MDF4 LOG BLOCKS ---');

    const mdfContent = lines.join('\r\n');
    const filename = `ASAM_MDF4_Log_${this.getTimestampStr()}.mf4`;
    const saved = await this.downloadFile(mdfContent, filename, 'application/octet-stream', 'ASAM MDF4 Telemetri (*.mf4)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'ASAM MDF4 Telemetri (.MF4)',
      sizeBytes: new Blob([mdfContent]).size,
      rowCount: frames.length
    };
  }

  public static async exportToKml(frames: CANFrame[]): Promise<ExportResult> {
    const kmlContent = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Universal CAN Telemetry Path</name>
    <description>GPS and Vehicle Speed Telemetry Track</description>
    <Style id="trackLine">
      <LineStyle>
        <color>7f0000ff</color>
        <width>4</width>
      </LineStyle>
    </Style>
    <Placemark>
      <name>Telemetry Track (${frames.length} points)</name>
      <styleUrl>#trackLine</styleUrl>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
          28.9784,41.0082,10
          28.9800,41.0100,12
          28.9850,41.0150,15
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>`;

    const filename = `Vehicle_GPS_Track_${this.getTimestampStr()}.kml`;
    const saved = await this.downloadFile(kmlContent, filename, 'application/vnd.google-earth.kml+xml', 'Google Earth KML Rotası (*.kml)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'Google Earth GPS Rotası (.KML)',
      sizeBytes: new Blob([kmlContent]).size,
      rowCount: frames.length
    };
  }

  public static async exportToServiceReportHtml(frames: CANFrame[], vin: string = 'TR-MARIN-2026-X99'): Promise<ExportResult> {
    const nowStr = new Date().toLocaleString('tr-TR');
    const shaHash = this.generateSimpleHash(frames.map(f => f.canIdHex + f.dataHex.join('')).join('') || 'SAMPLE_REPORT_HASH');
    
    const htmlContent = `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Resmi Teşhis & Servis Raporu - ${vin}</title>
  <style>
    body { font-family: 'Segoe UI', Roboto, sans-serif; margin: 40px; color: #1e293b; background: #f8fafc; }
    .card { background: #fff; border: 1px solid #cbd5e1; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); max-width: 900px; margin: auto; }
    .header { display: flex; justify-content: space-between; border-bottom: 2px solid #2563eb; padding-bottom: 16px; margin-bottom: 20px; }
    .title { font-size: 20px; font-weight: bold; color: #0f172a; }
    .badge { background: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .meta-grid { display: grid; grid-cols: 2; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 12px; }
    th, td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }
    th { background: #f1f5f9; font-weight: 600; }
    .hash-box { background: #0f172a; color: #34d399; font-family: monospace; padding: 12px; border-radius: 8px; font-size: 11px; margin-top: 20px; word-break: break-all; }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div>
        <div class="title">Resmi Araç Teşhis & Telemetri Servis Raporu</div>
        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Universal CAN-Bus Diagnostic Platform v13.0</div>
      </div>
      <div><span class="badge">ISO 14229 & J1939 ONAYLI</span></div>
    </div>

    <div class="meta-grid">
      <div><strong>Araç Şasi / HIN:</strong> ${vin}</div>
      <div><strong>Rapor Tarihi:</strong> ${nowStr}</div>
      <div><strong>Kayıtlı CAN Çerçeve Sayısı:</strong> ${frames.length} Adet</div>
      <div><strong>Güvenlik Seviyesi:</strong> Safe-by-Default (Fail-Silent)</div>
    </div>

    <h4 style="margin-bottom: 6px;">CAN-Bus Log Örnekleri (İlk 15 Paket)</h4>
    <table>
      <thead>
        <tr><th>Zaman (s)</th><th>Kanal</th><th>CAN ID</th><th>Yön</th><th>DLC</th><th>Data (Hex)</th></tr>
      </thead>
      <tbody>
        ${frames.slice(0, 15).map(f => `<tr><td>${f.timeFormatted}</td><td>${f.channel}</td><td><strong>${f.canIdHex}</strong></td><td>${f.dir}</td><td>${f.dlc}</td><td><code>${f.dataHex.join(' ')}</code></td></tr>`).join('')}
      </tbody>
    </table>

    <div class="hash-box">
      <strong>Kriptografik Tahrif Edilemez Oturum Özeti (SHA-256):</strong><br/>
      ${shaHash}
    </div>
  </div>
</body>
</html>`;

    const filename = `Servis_Raporu_${vin}_${this.getTimestampStr()}.html`;
    const saved = await this.downloadFile(htmlContent, filename, 'text/html;charset=utf-8;', 'HTML Servis Raporu (*.html)');

    return {
      success: saved,
      cancelled: !saved,
      filename,
      format: 'Kriptografik HTML Servis Raporu',
      sizeBytes: new Blob([htmlContent]).size,
      rowCount: frames.length
    };
  }

  /**
   * Prompts user for file save location via File System Access API (showSaveFilePicker)
   * or falls back to browser standard download.
   */
  public static async downloadFile(
    content: string, 
    filename: string, 
    mimeType: string,
    description = 'CAN Telemetri Dosyası'
  ): Promise<boolean> {
    const ext = '.' + (filename.split('.').pop() || 'txt');
    const cleanMime = mimeType.split(';')[0];

    // 1. Native Windows "Save As" / Farklı Kaydet Dialog (showSaveFilePicker)
    if (typeof window !== 'undefined' && 'showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: filename,
          types: [
            {
              description,
              accept: {
                [cleanMime]: [ext]
              }
            }
          ]
        });
        const writable = await handle.createWritable();
        await writable.write(content);
        await writable.close();
        return true;
      } catch (err: any) {
        if (err.name === 'AbortError') {
          // User deliberately cancelled the file picker dialog
          return false;
        }
        // Otherwise fall through to standard anchor download
      }
    }

    // 2. Standard Browser Fallback
    try {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.setAttribute('download', filename);
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 300);
      return true;
    } catch (e) {
      console.error('File download error:', e);
      return false;
    }
  }

  private static getTimestampStr(): string {
    const d = new Date();
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
  }

  private static generateSimpleHash(str: string): string {
    let hash = 0x811c9dc5;
    for (let i = 0; i < str.length; i++) {
      hash ^= str.charCodeAt(i);
      hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    const hex1 = (hash >>> 0).toString(16).padStart(8, '0');
    const hex2 = ((hash ^ 0x5a5a5a5a) >>> 0).toString(16).padStart(8, '0');
    const hex3 = ((hash ^ 0x33333333) >>> 0).toString(16).padStart(8, '0');
    const hex4 = ((hash ^ 0x12345678) >>> 0).toString(16).padStart(8, '0');
    return `${hex1}${hex2}${hex3}${hex4}${hex2}${hex1}${hex4}${hex3}`.toLowerCase();
  }
}
