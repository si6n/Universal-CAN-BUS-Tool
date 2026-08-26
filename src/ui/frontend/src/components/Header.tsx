import React from 'react';
import { 
  Cpu, 
  Activity, 
  Layers, 
  AlertOctagon, 
  Play, 
  Pause, 
  Settings, 
  Power,
  ChevronDown,
  Wand2
} from 'lucide-react';
import { ScenarioType } from '../types/can';

interface HeaderProps {
  channel: string;
  baudRate: string;
  busLoad: number;
  totalPackets: number;
  isSimulating: boolean;
  isEstopActive: boolean;
  activeScenario: ScenarioType;
  onToggleSimulator: () => void;
  onEstop: () => void;
  onSelectScenario: (scenario: ScenarioType) => void;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  channel,
  baudRate,
  busLoad,
  totalPackets,
  isSimulating,
  isEstopActive,
  activeScenario,
  onToggleSimulator,
  onEstop,
  onSelectScenario,
  onOpenSettings
}) => {
  const [showScenarioMenu, setShowScenarioMenu] = React.useState(false);

  const scenarioLabels: Record<ScenarioType, { title: string; desc: string }> = {
    nominal: { title: 'Nominal Çalışma (0 DTC)', desc: 'Standart telemetri akışı' },
    misfire_p0300: { title: 'DTC P0300 Ateşleme Hatası', desc: 'Silindir tekleme ve tork düşüşü' },
    overboost: { title: 'DTC P0234 Turbo Aşırı Basınç', desc: 'Takviye basıncı > 2.4 Bar' },
    overheat: { title: 'DTC P0115 Hararet Uyarısı', desc: 'Soğutma suyu > 105°C' },
    bus_surge: { title: 'CAN Bus Yüksek Yükü & Hata', desc: 'Bus yükü > %75 & CRC hataları' },
  };

  return (
    <header className="sticky top-0 z-40 bg-white border-b border-slate-200 px-4 py-2 flex items-center justify-between shadow-xs">
      {/* Left Brand & Title */}
      <div className="flex items-center space-x-3 min-w-[280px]">
        <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm ring-2 ring-blue-500/20">
          <Cpu className="w-5 h-5 stroke-[2.2]" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-sm font-bold text-slate-900 tracking-tight leading-tight">
              Universal CAN-Bus Diagnostic
            </h1>
            <span className="bg-slate-100 text-slate-600 text-[10.5px] font-mono font-medium px-1.5 py-0.5 rounded border border-slate-200">
              v13.0
            </span>
          </div>
          <p className="text-[11px] text-slate-500 font-medium">
            Telemetry & Real-Time Signal Sniffer
          </p>
        </div>
      </div>

      {/* Center Status Bar (Pill Shaped Container) */}
      <div className="flex items-center bg-slate-50 border border-slate-200 rounded-full px-4 py-1.5 space-x-5 text-xs text-slate-600 shadow-inner">
        {/* Connection Badge */}
        <div className="flex items-center space-x-2">
          <span className="relative flex h-2.5 w-2.5">
            {!isEstopActive && isSimulating && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isEstopActive ? 'bg-rose-500' : isSimulating ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
          </span>
          <span className="font-medium text-slate-700 font-mono text-[11px]">
            {channel} {isEstopActive ? 'Durduruldu' : `Bağlı (${baudRate})`}
          </span>
        </div>

        <div className="w-px h-3.5 bg-slate-200" />

        {/* Bus Load Meter */}
        <div className="flex items-center space-x-1.5 text-[11px]">
          <Activity className="w-3.5 h-3.5 text-blue-600" />
          <span className="text-slate-500">Yük:</span>
          <span className={`font-mono font-semibold ${busLoad > 70 ? 'text-rose-600' : busLoad > 50 ? 'text-amber-600' : 'text-slate-800'}`}>
            %{busLoad}
          </span>
        </div>

        <div className="w-px h-3.5 bg-slate-200" />

        {/* Total Packets Counter */}
        <div className="flex items-center space-x-1.5 text-[11px]">
          <Layers className="w-3.5 h-3.5 text-indigo-600" />
          <span className="text-slate-500">Paket:</span>
          <span className="font-mono font-semibold text-slate-800">
            {totalPackets.toLocaleString('tr-TR')}
          </span>
        </div>
      </div>

      {/* Right Action Group */}
      <div className="flex items-center space-x-2">
        {/* E-STOP Button */}
        <button
          onClick={onEstop}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all shadow-xs ${
            isEstopActive 
              ? 'bg-rose-600 text-white border-rose-700 ring-2 ring-rose-500/30' 
              : 'border-rose-200 bg-rose-50/80 text-rose-600 hover:bg-rose-100 active:scale-[0.98]'
          }`}
          title="Tüm CAN akışını acil durdur"
        >
          <AlertOctagon className="w-3.5 h-3.5 text-rose-600 fill-rose-100" />
          <span>{isEstopActive ? 'E-STOP AKTİF (DURDU)' : 'E-STOP (ACİL DURDUR)'}</span>
        </button>

        {/* Demo Simulator Action & Scenario Menu */}
        <div className="relative">
          <div className="inline-flex rounded-lg shadow-xs">
            <button
              onClick={onToggleSimulator}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-l-lg text-xs font-medium text-white transition-all ${
                isSimulating 
                  ? 'bg-blue-600 hover:bg-blue-700' 
                  : 'bg-slate-700 hover:bg-slate-800'
              }`}
            >
              {isSimulating ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
              <span>{isSimulating ? 'Demo Simülatör Duraklat' : 'Demo Simülatör Başlat'}</span>
            </button>
            <button
              onClick={() => setShowScenarioMenu(!showScenarioMenu)}
              className="bg-blue-700 hover:bg-blue-800 text-white px-1.5 py-1.5 rounded-r-lg border-l border-blue-500 text-xs"
              title="Senaryo Seç"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Dropdown for scenarios */}
          {showScenarioMenu && (
            <div className="absolute right-0 mt-1.5 w-64 bg-white border border-slate-200 rounded-lg shadow-xl py-1 z-50 animate-in fade-in slide-in-from-top-1">
              <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                Arıza & Telemetri Senaryoları
              </div>
              {(Object.keys(scenarioLabels) as ScenarioType[]).map((key) => {
                const item = scenarioLabels[key];
                const isSelected = activeScenario === key;
                return (
                  <button
                    key={key}
                    onClick={() => {
                      onSelectScenario(key);
                      setShowScenarioMenu(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-xs flex flex-col transition-colors ${
                      isSelected ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    <span className="font-semibold">{item.title}</span>
                    <span className="text-[10.5px] text-slate-400 font-normal">{item.desc}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Settings Button */}
        <button
          onClick={onOpenSettings}
          className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors shadow-xs"
          title="Ayarlar"
        >
          <Settings className="w-4 h-4" />
        </button>
        <button
          onClick={onEstop}
          className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors shadow-xs"
          title="Güvenli Kapat"
        >
          <Power className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
