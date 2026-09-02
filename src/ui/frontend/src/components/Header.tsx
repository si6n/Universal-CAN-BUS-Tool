import React, { useState, useRef, useEffect } from 'react';
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
  Zap,
  Gauge,
  Check
} from 'lucide-react';
import { ScenarioType, FaultInjectionType } from '../types/can';

interface HeaderProps {
  channel: string;
  baudRate: string;
  busLoad: number;
  totalPackets: number;
  isSimulating: boolean;
  isEstopActive: boolean;
  activeScenario: ScenarioType;
  simulationSpeed?: number;
  onToggleSimulator: () => void;
  onSelectScenario: (scenario: ScenarioType) => void;
  onEstop: () => void;
  onChangeSpeed?: (speed: number) => void;
  onInjectFault?: (type: FaultInjectionType) => void;
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
  simulationSpeed = 1.0,
  onToggleSimulator,
  onSelectScenario,
  onEstop,
  onChangeSpeed,
  onInjectFault,
  onOpenSettings
}) => {
  const [showScenarioMenu, setShowScenarioMenu] = useState(false);
  const [showFaultMenu, setShowFaultMenu] = useState(false);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  const scenarioMenuRef = useRef<HTMLDivElement>(null);

  const scenarioCategories = [
    {
      category: '🚗 Otomotiv & Ağır Vasıta J1939',
      items: [
        { key: 'nominal' as ScenarioType, title: 'Nominal Çalışma (0 DTC)', desc: 'Periyodik devir, turbo ve soğutma telemetrisi' },
        { key: 'misfire_p0300' as ScenarioType, title: 'DTC P0300 Silindir Tekleme', desc: 'Ateşleme arızası ve anlık tork kaybı' },
        { key: 'overboost' as ScenarioType, title: 'DTC P0234 Turbo Aşırı Basınç', desc: 'Wastegate sıkışması, >2.4 Bar takviye' },
        { key: 'overheat' as ScenarioType, title: 'DTC P0115 Motor Harareti', desc: 'Soğutma suyu >108°C kritik sıcaklık uyarısı' },
        { key: 'j1939_multi_ecu_fleet' as ScenarioType, title: 'J1939 Filo Ağı (5 ECU Eşzamanlı)', desc: 'ECM, TCM, Retarder, EBS ve Gösterge' },
      ]
    },
    {
      category: '⚡ Elektrikli Araç (EV & BMS)',
      items: [
        { key: 'ev_bms_telemetry' as ScenarioType, title: 'EV Yüksek Voltaj BMS Telemetrisi', desc: '398V DC, -45A/+140A akım döngüsü, %78 SOC' },
      ]
    },
    {
      category: '🌊 Marin & Denizcilik NMEA 2000',
      items: [
        { key: 'marine_vessel_n2k' as ScenarioType, title: 'NMEA 2000 Marin Seyir & Çift Motor', desc: 'Sancak/İskele RPM, GPS SOG hızı ve derinlik' },
      ]
    },
    {
      category: '📡 Yeni Nesil CAN-FD & ADAS',
      items: [
        { key: 'can_fd_adas_vision' as ScenarioType, title: 'CAN-FD 64B ADAS Ön Radar & Kamera', desc: '64 Bayt yük, 2.0 Mbps BRS, 8 hedef nesne kümesi' },
      ]
    },
    {
      category: '⚠️ Ağ Stres & Hat Hataları',
      items: [
        { key: 'bus_surge' as ScenarioType, title: 'CAN Bus Ağ Taşması & Yüksek Yük (%85+)', desc: 'Babbling Node patlaması ve CRC hataları' },
        { key: 'intermittent_wiring_fault' as ScenarioType, title: 'Kesintili Tesisat & Bus-Off Kurtarma', desc: 'Mikro temas temassızlığı ve otomatik kurtarma' },
      ]
    }
  ];

  // Close menus on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (scenarioMenuRef.current && !scenarioMenuRef.current.contains(event.target as Node)) {
        setShowScenarioMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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
            Multi-Domain Telemetry & Real-Time Signal Sniffer
          </p>
        </div>
      </div>

      {/* Center Status Bar (Pill Shaped Container) */}
      <div className="flex items-center bg-slate-50 border border-slate-200 rounded-full px-4 py-1.5 space-x-4 text-xs text-slate-600 shadow-inner">
        {/* Connection Badge */}
        <div className="flex items-center space-x-2">
          <span className="relative flex h-2.5 w-2.5">
            {!isEstopActive && isSimulating && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${isEstopActive ? 'bg-rose-500' : isSimulating ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
          </span>
          <span className="font-medium text-slate-700 font-mono text-[11px]">
            {channel} {isEstopActive ? 'Durduruldu' : isSimulating ? `Canlı Akış (${baudRate})` : `Bağlı (${baudRate})`}
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
          <span>{isEstopActive ? 'E-STOP (DURDU)' : 'E-STOP'}</span>
        </button>

        {/* Fault Injection Button & Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setShowFaultMenu(!showFaultMenu);
              setShowScenarioMenu(false);
              setShowSpeedMenu(false);
            }}
            className="flex items-center space-x-1 px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg text-xs font-semibold transition-colors"
            title="Manuel Hata Enjeksiyonu"
          >
            <Zap className="w-3.5 h-3.5 text-amber-600 fill-amber-500" />
            <span>Hata Enjekte Et</span>
            <ChevronDown className="w-3 h-3 ml-0.5 text-amber-600" />
          </button>

          {showFaultMenu && (
            <div className="absolute right-0 mt-1.5 w-60 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50 animate-in fade-in slide-in-from-top-1 text-xs">
              <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                Canlı Hat Hata Enjeksiyonu
              </div>
              <button
                onClick={() => {
                  if (onInjectFault) onInjectFault('error_frame');
                  setShowFaultMenu(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-rose-50 text-rose-700 font-medium flex items-center justify-between transition-colors"
              >
                <span>🔴 Fiziksel Hata Karesi Bas (Error Frame)</span>
              </button>
              <button
                onClick={() => {
                  if (onInjectFault) onInjectFault('dtc_fault');
                  setShowFaultMenu(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-amber-50 text-amber-800 font-medium flex items-center justify-between transition-colors"
              >
                <span>🟡 Aktif DTC Arıza Kodu Tetikle (DM1)</span>
              </button>
              <button
                onClick={() => {
                  if (onInjectFault) onInjectFault('sensor_freeze');
                  setShowFaultMenu(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-blue-50 text-blue-700 font-medium flex items-center justify-between transition-colors"
              >
                <span>❄️ Sensör Sinyal Donması (Frozen ADC)</span>
              </button>
              <button
                onClick={() => {
                  if (onInjectFault) onInjectFault('babbling_surge');
                  setShowFaultMenu(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-purple-50 text-purple-700 font-medium flex items-center justify-between transition-colors"
              >
                <span>💥 Ağ Taşması Patlaması (Babbling Node)</span>
              </button>
              <button
                onClick={() => {
                  if (onInjectFault) onInjectFault('wiring_dropout');
                  setShowFaultMenu(false);
                }}
                className="w-full text-left px-3 py-2 hover:bg-slate-50 text-slate-700 font-medium flex items-center justify-between transition-colors border-t border-slate-100"
              >
                <span>⚡ Kesintili Kablo & Bus-Off</span>
              </button>
            </div>
          )}
        </div>

        {/* Simulator Start / Pause & Categorized Scenario Dropdown (Sleek Segmented Design) */}
        <div className="relative" ref={scenarioMenuRef}>
          <div className="inline-flex rounded-lg shadow-xs border border-slate-200/80">
            {/* Start / Pause Button */}
            <button
              onClick={onToggleSimulator}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-l-lg text-xs font-semibold transition-all active:scale-[0.98] ${
                isSimulating 
                  ? 'bg-slate-800 hover:bg-slate-900 text-white' 
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
              title={isSimulating ? 'Simülasyonu Duraklat' : 'Simülatörü Başlat'}
            >
              {isSimulating ? (
                <>
                  <Pause className="w-3.5 h-3.5 fill-current text-amber-400" />
                  <span>Duraklat</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Simülatör Başlat</span>
                </>
              )}
            </button>

            {/* Scenario Dropdown Trigger */}
            <button
              onClick={() => {
                setShowScenarioMenu(!showScenarioMenu);
                setShowFaultMenu(false);
                setShowSpeedMenu(false);
              }}
              className={`px-2 py-1.5 rounded-r-lg border-l text-xs flex items-center transition-colors ${
                isSimulating 
                  ? 'bg-slate-850 hover:bg-slate-900 text-slate-200 border-slate-700' 
                  : 'bg-blue-700 hover:bg-blue-800 text-white border-blue-500'
              }`}
              title="Senaryo Galerisi"
            >
              <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showScenarioMenu ? 'rotate-180' : ''}`} />
            </button>
          </div>

          {/* Categorized Dropdown for 10 Scenarios (Spacious & Clean) */}
          {showScenarioMenu && (
            <div className="absolute right-0 mt-1.5 w-84 bg-white border border-slate-200 rounded-xl shadow-2xl py-1.5 z-50 animate-in fade-in slide-in-from-top-1 max-h-[480px] overflow-y-auto">
              <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 flex items-center justify-between">
                <span>CAN-Bus Senaryo Galerisi</span>
                <span className="font-mono text-slate-400">10 Senaryo</span>
              </div>
              
              {scenarioCategories.map((cat, catIdx) => (
                <div key={catIdx} className="py-1">
                  <div className="px-3 py-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider bg-slate-50 border-y border-slate-100">
                    {cat.category}
                  </div>
                  {cat.items.map((item) => {
                    const isSelected = activeScenario === item.key;
                    return (
                      <button
                        key={item.key}
                        onClick={() => {
                          onSelectScenario(item.key);
                          setShowScenarioMenu(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs flex flex-col transition-colors ${
                          isSelected 
                            ? 'bg-blue-50/90 text-blue-900 font-semibold border-l-2 border-blue-600' 
                            : 'text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-800">{item.title}</span>
                          {isSelected && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0 ml-1" />}
                        </div>
                        <span className="text-[10.5px] text-slate-400 font-normal mt-0.5">{item.desc}</span>
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Speed Multiplier Button */}
        <div className="relative">
          <button
            onClick={() => {
              setShowSpeedMenu(!showSpeedMenu);
              setShowScenarioMenu(false);
              setShowFaultMenu(false);
            }}
            className="flex items-center space-x-1 px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-lg text-xs font-mono font-semibold transition-colors shadow-2xs"
            title="Simülasyon Hızı"
          >
            <Gauge className="w-3.5 h-3.5 text-slate-600" />
            <span>{simulationSpeed}x</span>
          </button>

          {showSpeedMenu && (
            <div className="absolute right-0 mt-1.5 w-28 bg-white border border-slate-200 rounded-xl shadow-xl py-1 z-50 animate-in fade-in slide-in-from-top-1 text-xs">
              {[0.5, 1.0, 2.0, 5.0].map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    if (onChangeSpeed) onChangeSpeed(s);
                    setShowSpeedMenu(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 font-mono font-semibold transition-colors ${
                    simulationSpeed === s ? 'bg-blue-50 text-blue-700' : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {s}x Hız
                </button>
              ))}
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
