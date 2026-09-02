import React, { useState, useRef, useEffect } from 'react';
import { 
  LayoutDashboard, 
  Wand2,
  Cpu, 
  Share2, 
  FileText, 
  Wrench, 
  ChevronDown, 
  Check 
} from 'lucide-react';
import { ActiveTab } from '../types/can';

interface SubNavProps {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  protocolText?: string;
}

export const SubNav: React.FC<SubNavProps> = ({
  activeTab,
  onSelectTab,
  protocolText = 'ISO 11898-2 (CAN 2.0B / J1939)'
}) => {
  const [isToolsOpen, setIsToolsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const toolItems = [
    { 
      id: 'ecu_flashing' as ActiveTab, 
      label: 'ECU Flashing & Bootloader', 
      desc: 'ISO 14229 UDS Firmware Yükleyici',
      icon: Cpu,
      badge: 'UDS 0x10/0x34'
    },
    { 
      id: 'pinout_guide' as ActiveTab, 
      label: 'Konnektör Pinout Rehberi', 
      desc: 'OBD-II, Deutsch 9-Pin, Micro-C Pin Şemaları',
      icon: Share2,
      badge: 'Şemalar'
    },
    { 
      id: 'reports' as ActiveTab, 
      label: 'Rapor & Dışa Aktarma', 
      desc: 'MDF4, Vector ASC, CSV, JSON, HTML İndirme',
      icon: FileText,
      badge: 'MDF4/ASC'
    }
  ];

  const isToolActive = activeTab === 'ecu_flashing' || activeTab === 'pinout_guide' || activeTab === 'reports';
  const currentActiveTool = toolItems.find(t => t.id === activeTab);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsToolsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="bg-white border-b border-slate-200 px-4 flex items-center justify-between shadow-[0_1px_2px_rgba(0,0,0,0.02)] relative z-30">
      <nav className="flex items-center space-x-1 -mb-px">
        {/* 1. Dashboard Tab */}
        <button
          onClick={() => {
            onSelectTab('dashboard');
            setIsToolsOpen(false);
          }}
          className={`group flex items-center space-x-2 py-2 px-3.5 border-b-2 text-xs font-semibold transition-all ${
            activeTab === 'dashboard'
              ? 'border-blue-600 text-blue-600 bg-blue-50/40 shadow-xs'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
          }`}
        >
          <LayoutDashboard className={`w-3.5 h-3.5 ${activeTab === 'dashboard' ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
          <span>Dashboard</span>
        </button>

        {/* 2. Reverse Engineer Tab */}
        <button
          onClick={() => {
            onSelectTab('signal_discovery');
            setIsToolsOpen(false);
          }}
          className={`group flex items-center space-x-2 py-2 px-3.5 border-b-2 text-xs font-semibold transition-all ${
            activeTab === 'signal_discovery'
              ? 'border-indigo-600 text-indigo-600 bg-indigo-50/40 shadow-xs'
              : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
          }`}
        >
          <Wand2 className={`w-3.5 h-3.5 ${activeTab === 'signal_discovery' ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
          <span>Reverse Engineer</span>
        </button>

        {/* 3. Araçlar (Tools) Dropdown Menu */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsToolsOpen(!isToolsOpen)}
            className={`group flex items-center space-x-1.5 py-2 px-3.5 border-b-2 text-xs font-semibold transition-all ${
              isToolActive
                ? 'border-blue-600 text-blue-700 bg-blue-50/40 shadow-xs'
                : isToolsOpen
                ? 'border-slate-300 text-slate-900 bg-slate-50'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Wrench className={`w-3.5 h-3.5 ${isToolActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
            <span>Araçlar</span>
            {isToolActive && currentActiveTool && (
              <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.2 rounded font-normal ml-0.5">
                ({currentActiveTool.label.split(' ')[0]})
              </span>
            )}
            <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isToolsOpen ? 'rotate-180 text-blue-600' : ''}`} />
          </button>

          {/* Dropdown Popup */}
          {isToolsOpen && (
            <div className="absolute top-full left-0 mt-1 w-80 bg-white border border-slate-200 rounded-xl shadow-xl p-1.5 space-y-1 animate-in fade-in slide-in-from-top-2 duration-150 z-50">
              <div className="px-2.5 py-1.5 text-[10.5px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                Sistem & Teşhis Araçları
              </div>

              {toolItems.map((tool) => {
                const Icon = tool.icon;
                const isCurrent = activeTab === tool.id;
                return (
                  <button
                    key={tool.id}
                    onClick={() => {
                      onSelectTab(tool.id);
                      setIsToolsOpen(false);
                    }}
                    className={`w-full text-left p-2.5 rounded-lg flex items-start space-x-2.5 transition-colors ${
                      isCurrent
                        ? 'bg-blue-50 text-blue-900 font-semibold'
                        : 'hover:bg-slate-50 text-slate-700'
                    }`}
                  >
                    <div className={`p-1.5 rounded-md mt-0.5 shrink-0 ${isCurrent ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      <Icon className="w-3.5 h-3.5" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold leading-tight truncate">{tool.label}</span>
                        {isCurrent && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0 ml-1" />}
                      </div>
                      <p className="text-[10.5px] text-slate-400 truncate mt-0.5">{tool.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </nav>

      {/* Right Side: Protocol Badge */}
      <div className="flex items-center space-x-2 text-[11px] text-slate-500 font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
        <span>Protokol: <strong className="text-slate-700 font-semibold">{protocolText}</strong></span>
      </div>
    </div>
  );
};
