import React, { useState } from 'react';
import { 
  FileText, 
  Download, 
  FileSpreadsheet, 
  Code, 
  CheckCircle2,
  Database,
  MapPin,
  Shield,
  Layers,
  Sparkles,
  Check
} from 'lucide-react';
import { CANFrame } from '../../types/can';
import { ExportService, ExportResult } from '../../services/exportService';

interface ReportsExportViewProps {
  frames: CANFrame[];
}

export const ReportsExportView: React.FC<ReportsExportViewProps> = ({ frames }) => {
  const [lastExport, setLastExport] = useState<ExportResult | null>(null);
  const [vinInput, setVinInput] = useState('TR-MARIN-2026-X99');

  const handleExport = async (exportFn: () => Promise<ExportResult>) => {
    const res = await exportFn();
    if (res && res.success) {
      setLastExport(res);
      setTimeout(() => {
        setLastExport(null);
      }, 6000);
    }
  };

  return (
    <div className="p-4 space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-card flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Rapor & Telemetri Dışa Aktarma Merkezi</h2>
            <p className="text-xs text-slate-500">MDF4, Vector ASC, CSV, JSON, KML ve Kriptografik Servis Raporu İndirme</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="text-xs text-slate-500">
            Araç VIN/HIN:
            <input
              type="text"
              value={vinInput}
              onChange={(e) => setVinInput(e.target.value)}
              className="ml-1.5 px-2 py-1 border border-slate-200 rounded font-mono text-xs font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="text-xs font-mono font-semibold text-slate-600 bg-slate-100 px-3 py-1.5 rounded-lg border border-slate-200">
            Kayıtlı Çerçeve: <strong>{frames.length} adet</strong>
          </div>
        </div>
      </div>

      {/* Success Notification Banner */}
      {lastExport && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 flex items-center justify-between shadow-xs animate-in fade-in slide-in-from-top-1">
          <div className="flex items-center space-x-2.5 text-xs text-emerald-800 font-medium">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <div>
              <strong>{lastExport.format}</strong> başarıyla üretildi ve bilgisayarınıza indirildi! (Dosya: <code className="font-mono bg-emerald-100/70 px-1.5 py-0.5 rounded text-emerald-900">{lastExport.filename}</code> • {(lastExport.sizeBytes / 1024).toFixed(1)} KB)
            </div>
          </div>
          <span className="text-[11px] text-emerald-700 font-semibold bg-emerald-100 px-2 py-0.5 rounded-full">
            İndirildi
          </span>
        </div>
      )}

      {/* Export Cards Grid (6 Formats) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* 1. CSV / Excel Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">Excel & CSV Telemetri Tablosu</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Zaman damgası, CAN ID (Hex & Dec), DLC, baytlar ve ASCII içeriğini tablo formatında dışa aktarır.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToCsv(frames))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>CSV Dosyasını İndir</span>
          </button>
        </div>

        {/* 2. Vector ASC Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">Vector CANoe / CANalyzer (.ASC)</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Otomotiv standardı Vector ASC formatında tam trace logu üretir. CANoe veya PCAN ile tekrar oynatılabilir.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToAsc(frames))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>Vector ASC İndir</span>
          </button>
        </div>

        {/* 3. ASAM MDF4 (.MF4) Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-cyan-50 border border-cyan-200 flex items-center justify-center text-cyan-700">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">ASAM MDF4 Telemetri (.MF4)</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              ASAM e.V. standardı MDF4 ikili telemetri blokları. INCA, CANape ve MATLAB ile tam uyumludur.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToMdf4(frames))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>ASAM MDF4 İndir</span>
          </button>
        </div>

        {/* 4. JSON Dump Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Code className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">Ham JSON / AI Model Çıktısı</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Tüm telemetri çerçevelerini ve zaman serisi metaverilerini JSON formatında arşivler.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToJson(frames))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>JSON İndir</span>
          </button>
        </div>

        {/* 5. Google Earth KML Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
              <MapPin className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">Google Earth GPS Rotası (.KML)</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Marin veya araç güzergah telemetrisini Google Earth 3D haritalarında görselleştirmek için KML dosyası.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToKml(frames))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>KML Rotası İndir</span>
          </button>
        </div>

        {/* 6. Cryptographic Service Report (HTML/Printable) */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-card flex flex-col justify-between space-y-4 hover:border-slate-300 transition-colors">
          <div className="space-y-2">
            <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-600">
              <Shield className="w-5 h-5" />
            </div>
            <h3 className="text-xs font-bold text-slate-900">Resmi Teşhis Servis Raporu</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Kriptografik SHA-256 oturum özetli, tahrif edilemez HTML ve PDF yazdırılabilir servis formu.
            </p>
          </div>

          <button
            onClick={() => handleExport(() => ExportService.exportToServiceReportHtml(frames, vinInput))}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-bold shadow-xs transition-colors active:scale-[0.99]"
          >
            <Download className="w-4 h-4" />
            <span>Resmi Servis Raporu İndir</span>
          </button>
        </div>
      </div>

      {/* Summary Box */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-card space-y-2">
        <div className="text-xs font-bold text-slate-800">Standart & Güvenlik Doğrulamaları:</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600">
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>ISO 14229 (UDS) & ISO 15765-2 Uyumlu</span>
          </div>
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>SAE J1939 Ağır Vasıta & NMEA 2000 Destekli</span>
          </div>
          <div className="flex items-center space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>SHA-256 Kriptografik Oturum Bütünlüğü</span>
          </div>
        </div>
      </div>
    </div>
  );
};
