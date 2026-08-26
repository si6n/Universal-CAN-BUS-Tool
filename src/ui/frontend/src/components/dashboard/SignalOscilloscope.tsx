import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  Flame, 
  LineChart, 
  Cpu, 
  Maximize2, 
  ShieldAlert, 
  Pause, 
  Play, 
  Bot, 
  AlertTriangle, 
  CheckCircle2, 
  Clock,
  Copy,
  Check,
  Search,
  Sliders,
  Sparkles
} from 'lucide-react';
import { TelemetryPoint } from '../../types/can';
import { AnomalyDetector, SignalAnomalyEvent, CanIdTimingState } from '../../services/anomalyDetector';
import { CopilotContextBuilder } from '../../services/copilotContextBuilder';

interface SignalOscilloscopeProps {
  currentPoint: TelemetryPoint | null;
  history: TelemetryPoint[];
  onAskCopilot?: (prompt: string) => void;
}

interface CanIdDefinition {
  idHex: string;
  name: string;
  protocol: string;
  expectedFreqHz: number;
  color: string;
  bgGradient: string;
}

interface HeatmapContextMenu {
  visible: boolean;
  x: number;
  y: number;
  timingState: CanIdTimingState;
}

const HEATMAP_CAN_IDS: CanIdDefinition[] = [
  { idHex: '0x0CF00400', name: 'J1939 EEC1 Devir / Tork', protocol: 'J1939 PGN 61444', expectedFreqHz: 50, color: '#2563EB', bgGradient: 'from-blue-500 to-indigo-600' },
  { idHex: '0x18FEF600', name: 'J1939 IC1 Turbo Basınç', protocol: 'J1939 PGN 65270', expectedFreqHz: 20, color: '#10B981', bgGradient: 'from-emerald-500 to-teal-600' },
  { idHex: '0x18FEE100', name: 'J1939 ET1 Motor Hararet', protocol: 'J1939 PGN 65249', expectedFreqHz: 10, color: '#F59E0B', bgGradient: 'from-amber-500 to-orange-600' },
  { idHex: '0x19F20000', name: 'NMEA2000 Hızlı Telemetri', protocol: 'N2K PGN 127488', expectedFreqHz: 40, color: '#6366F1', bgGradient: 'from-indigo-500 to-purple-600' },
  { idHex: '0x18FEF200', name: 'J1939 LFE Yakıt Tüketimi', protocol: 'J1939 PGN 65266', expectedFreqHz: 10, color: '#06B6D4', bgGradient: 'from-cyan-500 to-blue-600' },
  { idHex: '0x18FEE000', name: 'J1939 TCO1 Araç Hızı', protocol: 'J1939 PGN 65248', expectedFreqHz: 20, color: '#8B5CF6', bgGradient: 'from-purple-500 to-indigo-600' },
  { idHex: '0x0CF00300', name: 'J1939 EEC2 Elektronik #2', protocol: 'J1939 PGN 61443', expectedFreqHz: 25, color: '#3B82F6', bgGradient: 'from-blue-600 to-sky-600' },
  { idHex: '0x0C000003', name: 'Şanzıman Kontrol (TCU)', protocol: 'Proprietary TX', expectedFreqHz: 30, color: '#64748B', bgGradient: 'from-slate-600 to-slate-700' },
];

export const SignalOscilloscope: React.FC<SignalOscilloscopeProps> = ({
  currentPoint,
  history,
  onAskCopilot
}) => {
  const [viewMode, setViewMode] = useState<'oscilloscope' | 'heatmap'>('oscilloscope');
  const [isAutoRange, setIsAutoRange] = useState(true);
  const [isGlitchGuardActive, setIsGlitchGuardActive] = useState(true);
  const [isFrozen, setIsFrozen] = useState(false);
  const [frozenHistory, setFrozenHistory] = useState<TelemetryPoint[]>([]);
  const [activeAnomaly, setActiveAnomaly] = useState<SignalAnomalyEvent | null>(null);

  // Context Menu State for Heatmap
  const [contextMenu, setContextMenu] = useState<HeatmapContextMenu | null>(null);
  const [copiedToast, setCopiedToast] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const displayHistory = isFrozen ? frozenHistory : history;
  const rpm = currentPoint?.rpm ?? 0;
  const turboBar = currentPoint?.turboBoostBar ?? 0.0;
  const busLoad = currentPoint?.busLoadPercent ?? 0;

  // Close context menu on outside click
  useEffect(() => {
    const handleOutsideClick = () => {
      if (contextMenu) setContextMenu(null);
    };
    window.addEventListener('click', handleOutsideClick);
    return () => window.removeEventListener('click', handleOutsideClick);
  }, [contextMenu]);

  const handleToggleFreeze = () => {
    if (!isFrozen) {
      setFrozenHistory([...history]);
      setIsFrozen(true);
    } else {
      setIsFrozen(false);
    }
  };

  // 1. Oscilloscope Rendering Engine with Adaptive Auto-Range & Glitch Markers
  useEffect(() => {
    if (viewMode !== 'oscilloscope') return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.parentElement?.clientWidth || 700;
    const height = canvas.parentElement?.clientHeight || 200;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const paddingLeft = 48;
    const paddingRight = 44;
    const paddingTop = 26;
    const paddingBottom = 20;
    const plotWidth = width - paddingLeft - paddingRight;
    const plotHeight = height - paddingTop - paddingBottom;

    // Calculate Adaptive Range
    const range = AnomalyDetector.calculateAdaptiveRange(displayHistory, isAutoRange);

    const yGridSteps = 5;
    ctx.strokeStyle = '#F1F5F9';
    ctx.lineWidth = 1;
    ctx.font = '10px "JetBrains Mono", monospace';
    ctx.textBaseline = 'middle';

    for (let i = 0; i <= yGridSteps; i++) {
      const y = paddingTop + plotHeight - (i / yGridSteps) * plotHeight;
      ctx.beginPath();
      ctx.moveTo(paddingLeft, y);
      ctx.lineTo(width - paddingRight, y);
      ctx.stroke();

      // Left Y-Axis (RPM)
      ctx.fillStyle = '#64748B';
      ctx.textAlign = 'right';
      const rpmVal = Math.round(range.minRpm + (i / yGridSteps) * (range.maxRpm - range.minRpm));
      ctx.fillText(rpmVal.toLocaleString('tr-TR'), paddingLeft - 6, y);

      // Right Y-Axis (Turbo Bar)
      ctx.fillStyle = '#10B981';
      ctx.textAlign = 'left';
      const barVal = (range.minTurbo + (i / yGridSteps) * (range.maxTurbo - range.minTurbo)).toFixed(1);
      ctx.fillText(barVal, width - paddingRight + 6, y);
    }

    if (displayHistory.length < 2) {
      ctx.fillStyle = '#94A3B8';
      ctx.textAlign = 'center';
      ctx.font = '12px Inter, sans-serif';
      ctx.fillText('Canlı telemetri sinyali bekleniyor... [RPM & Turbo Boost]', paddingLeft + plotWidth / 2, paddingTop + plotHeight / 2);
      return;
    }

    const points = displayHistory.slice(-45);
    const stepX = plotWidth / (points.length - 1);

    // 1. Draw RPM Smooth Line (Royal Blue with gradient fill)
    ctx.beginPath();
    points.forEach((p, idx) => {
      const x = paddingLeft + idx * stepX;
      const normalizedRpm = (p.rpm - range.minRpm) / Math.max(1, range.maxRpm - range.minRpm);
      const y = paddingTop + plotHeight - Math.max(0, Math.min(1, normalizedRpm)) * plotHeight;
      
      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        const prevP = points[idx - 1];
        const prevNorm = (prevP.rpm - range.minRpm) / Math.max(1, range.maxRpm - range.minRpm);
        const prevX = paddingLeft + (idx - 1) * stepX;
        const prevY = paddingTop + plotHeight - Math.max(0, Math.min(1, prevNorm)) * plotHeight;
        const cpX = (prevX + x) / 2;
        ctx.bezierCurveTo(cpX, prevY, cpX, y, x, y);
      }
    });

    ctx.strokeStyle = '#2563EB';
    ctx.lineWidth = 2.2;
    ctx.stroke();

    const lastX = paddingLeft + (points.length - 1) * stepX;
    ctx.lineTo(lastX, paddingTop + plotHeight);
    ctx.lineTo(paddingLeft, paddingTop + plotHeight);
    ctx.closePath();

    const rpmGradient = ctx.createLinearGradient(0, paddingTop, 0, paddingTop + plotHeight);
    rpmGradient.addColorStop(0, 'rgba(37, 99, 235, 0.12)');
    rpmGradient.addColorStop(1, 'rgba(37, 99, 235, 0.0)');
    ctx.fillStyle = rpmGradient;
    ctx.fill();

    // 2. Draw Turbo Boost Line (Emerald Dashed Line)
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    points.forEach((p, idx) => {
      const x = paddingLeft + idx * stepX;
      const normalizedTurbo = (p.turboBoostBar - range.minTurbo) / Math.max(0.1, range.maxTurbo - range.minTurbo);
      const y = paddingTop + plotHeight - Math.max(0, Math.min(1, normalizedTurbo)) * plotHeight;
      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.strokeStyle = '#10B981';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.setLineDash([]);

    // 3. Glitch Anomaly Detection & Visual Markers
    if (isGlitchGuardActive) {
      const anomalies = AnomalyDetector.scanSignalAnomalies(displayHistory);
      if (anomalies.length > 0) {
        const latestAnomaly = anomalies[anomalies.length - 1];
        setActiveAnomaly(latestAnomaly);

        // Find index of anomaly in points
        const anomIdx = points.findIndex(p => Math.abs(p.timeSec - latestAnomaly.timestampSec) < 0.1);
        if (anomIdx >= 0) {
          const anomX = paddingLeft + anomIdx * stepX;

          // Draw vertical warning flag line
          ctx.beginPath();
          ctx.strokeStyle = latestAnomaly.severity === 'CRITICAL' ? '#EF4444' : '#F59E0B';
          ctx.lineWidth = 1.5;
          ctx.setLineDash([2, 2]);
          ctx.moveTo(anomX, paddingTop);
          ctx.lineTo(anomX, paddingTop + plotHeight);
          ctx.stroke();
          ctx.setLineDash([]);

          // Draw Anomaly Pulsing Dot
          ctx.beginPath();
          ctx.arc(anomX, paddingTop + 10, 4, 0, Math.PI * 2);
          ctx.fillStyle = latestAnomaly.severity === 'CRITICAL' ? '#EF4444' : '#F59E0B';
          ctx.fill();
        }
      } else {
        setActiveAnomaly(null);
      }
    }

    // Pulse dots on latest values
    const latestP = points[points.length - 1];
    const latestRpmNorm = (latestP.rpm - range.minRpm) / Math.max(1, range.maxRpm - range.minRpm);
    const latestRpmY = paddingTop + plotHeight - Math.max(0, Math.min(1, latestRpmNorm)) * plotHeight;

    const latestTurboNorm = (latestP.turboBoostBar - range.minTurbo) / Math.max(0.1, range.maxTurbo - range.minTurbo);
    const latestTurboY = paddingTop + plotHeight - Math.max(0, Math.min(1, latestTurboNorm)) * plotHeight;

    ctx.beginPath();
    ctx.arc(lastX, latestRpmY, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#2563EB';
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#FFFFFF';
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(lastX, latestTurboY, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#10B981';
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#FFFFFF';
    ctx.stroke();

  }, [displayHistory, viewMode, isAutoRange, isGlitchGuardActive, isFrozen]);

  const handleInspectAnomaly = (anomaly: SignalAnomalyEvent) => {
    if (!onAskCopilot) return;
    const prompt = CopilotContextBuilder.buildSignalAnomalyPrompt(anomaly, currentPoint);
    onAskCopilot(prompt);
  };

  const handleInspectCanTiming = (timingState: CanIdTimingState) => {
    if (!onAskCopilot) return;
    const prompt = CopilotContextBuilder.buildCanTimingPrompt(timingState, busLoad);
    onAskCopilot(prompt);
    setContextMenu(null);
  };

  const handleCardContextMenu = (e: React.MouseEvent, timingState: CanIdTimingState) => {
    e.preventDefault();
    e.stopPropagation();

    const rect = containerRef.current?.getBoundingClientRect();
    const offsetX = rect ? rect.left : 0;
    const offsetY = rect ? rect.top : 0;

    setContextMenu({
      visible: true,
      x: e.clientX - offsetX,
      y: e.clientY - offsetY,
      timingState
    });
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedToast(`${label} kopyalandı!`);
    setTimeout(() => setCopiedToast(null), 2000);
    setContextMenu(null);
  };

  return (
    <div ref={containerRef} className="bg-white border border-slate-200 rounded-xl shadow-card flex flex-col h-full overflow-hidden relative">
      {/* ───────────────────────────────────────────────────────────── */}
      {/* TOP HEADER: Ultra Clean & Uncluttered (Guaranteed No Overflow) */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="px-3 py-1.5 bg-white border-b border-slate-200 flex items-center justify-between shrink-0">
        {/* Left: Brand Title */}
        <div className="flex items-center space-x-2">
          <div className="w-5 h-5 rounded-md bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
            <LineChart className="w-3 h-3 stroke-[2.2]" />
          </div>
          <span className="text-xs font-bold text-slate-900 tracking-tight">Grafik & Sinyal Analizi</span>
        </div>

        {/* Right: Mode Switcher Tabs (Permanently Fixed & Never Clipped) */}
        <div className="inline-flex bg-slate-100 p-0.5 rounded-lg border border-slate-200/80 text-[11px] font-medium shrink-0">
          <button
            onClick={() => setViewMode('oscilloscope')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md transition-all ${
              viewMode === 'oscilloscope'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Activity className="w-3 h-3 text-blue-600" />
            <span>Osiloskop</span>
          </button>

          <button
            onClick={() => setViewMode('heatmap')}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-md transition-all ${
              viewMode === 'heatmap'
                ? 'bg-white text-slate-900 shadow-xs font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Flame className="w-3 h-3 text-amber-500" />
            <span>Isı Haritası</span>
          </button>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MAIN VIEW CONTENT AREA */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="relative flex-1 bg-white p-2 flex flex-col overflow-hidden">
        {/* VIEW 1: OSCILLOSCOPE */}
        {viewMode === 'oscilloscope' && (
          <div className="w-full h-full relative flex flex-col">
            {/* Oscilloscope Floating In-Canvas Toolbar */}
            <div className="absolute left-2.5 top-1 z-10 flex items-center space-x-2">
              {/* Telemetry Live Value Indicators */}
              <div className="flex items-center space-x-2 px-2 py-0.5 bg-white/95 backdrop-blur-xs border border-slate-200 rounded-md text-[10.5px] font-mono shadow-2xs">
                <div className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block animate-pulse"></span>
                  <span className="text-slate-500 font-sans">Devir:</span>
                  <span className="font-bold text-slate-900">{rpm} RPM</span>
                </div>
                <div className="w-px h-2.5 bg-slate-200"></div>
                <div className="flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block"></span>
                  <span className="text-slate-500 font-sans">Turbo:</span>
                  <span className="font-bold text-slate-900">{turboBar} Bar</span>
                </div>
              </div>
            </div>

            {/* Oscilloscope Floating Controls (Top Right of Canvas) */}
            <div className="absolute right-2.5 top-1 z-10 flex items-center space-x-1">
              <button
                onClick={() => setIsAutoRange(!isAutoRange)}
                className={`flex items-center space-x-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold transition-all ${
                  isAutoRange 
                    ? 'bg-blue-50 border-blue-200 text-blue-700 shadow-2xs' 
                    : 'bg-white/95 backdrop-blur-xs border-slate-200 text-slate-500 hover:bg-slate-50'
                }`}
                title="Sinyal genliğine göre Y eksenini dinamik optimize eder"
              >
                <Maximize2 className="w-2.5 h-2.5" />
                <span>Oto-Ölçek</span>
              </button>

              <button
                onClick={() => setIsGlitchGuardActive(!isGlitchGuardActive)}
                className={`flex items-center space-x-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold transition-all ${
                  isGlitchGuardActive 
                    ? 'bg-amber-50 border-amber-200 text-amber-800 shadow-2xs' 
                    : 'bg-white/95 backdrop-blur-xs border-slate-200 text-slate-500 hover:bg-slate-50'
                }`}
                title="Misfire ve aşırı basınç dalga anomalilerini gerçek zamanlı işaretler"
              >
                <ShieldAlert className="w-2.5 h-2.5 text-amber-600" />
                <span>Glitch Guard</span>
              </button>

              <button
                onClick={handleToggleFreeze}
                className={`flex items-center space-x-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold transition-all ${
                  isFrozen 
                    ? 'bg-rose-100 border-rose-300 text-rose-800 animate-pulse' 
                    : 'bg-white/95 backdrop-blur-xs border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
                title="Grafik akışını inceleme için dondur"
              >
                {isFrozen ? <Play className="w-2.5 h-2.5 fill-rose-700" /> : <Pause className="w-2.5 h-2.5" />}
                <span>{isFrozen ? 'Sürdür' : 'Dondur'}</span>
              </button>
            </div>

            {/* Active Anomaly Glitch Action Banner */}
            {activeAnomaly && (
              <div className="absolute right-2.5 top-8 z-10 bg-rose-50/95 border border-rose-200 text-rose-900 rounded-md px-2 py-0.5 flex items-center space-x-1.5 shadow-xs text-[10.5px]">
                <AlertTriangle className="w-3 h-3 text-rose-600 animate-pulse shrink-0" />
                <span className="font-semibold">{activeAnomaly.description}</span>
                <button
                  onClick={() => handleInspectAnomaly(activeAnomaly)}
                  className="flex items-center space-x-1 px-2 py-0.5 bg-rose-600 hover:bg-rose-700 text-white rounded text-[10px] font-bold shadow-2xs transition-colors ml-1"
                >
                  <Bot className="w-2.5 h-2.5" />
                  <span>AI Analiz</span>
                </button>
              </div>
            )}

            <canvas ref={canvasRef} className="w-full h-full block" />
          </div>
        )}

        {/* VIEW 2: CAN FREQUENCY HEATMAP SPECTRUM */}
        {viewMode === 'heatmap' && (
          <div className="w-full h-full flex flex-col space-y-1.5 overflow-y-auto">
            {/* Heatmap Top Spectrum Info Sub-bar */}
            <div className="flex items-center justify-between px-2.5 py-1 bg-slate-50 border border-slate-200/80 rounded-lg text-xs shrink-0">
              <div className="flex items-center space-x-2">
                <span className="bg-indigo-100 text-indigo-700 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold">
                  8 Aktif Düğüm
                </span>
                <div className="flex items-center space-x-1 text-[11px] font-mono text-slate-600">
                  <span className="text-slate-400">Bus Yükü:</span>
                  <span className={`font-bold ${busLoad > 70 ? 'text-rose-600' : 'text-slate-800'}`}>%{busLoad}</span>
                </div>
              </div>

              <div className="text-[10px] text-slate-400 font-sans">
                🖱️ <span className="font-medium text-slate-600">Kartlara sağ tıklayarak</span> AI Analizi yapabilirsiniz
              </div>
            </div>

            {/* 8-Card Responsive Grid with Right-Click Context Menu Support */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 flex-1">
              {HEATMAP_CAN_IDS.map((item, idx) => {
                // Calculate realistic frequency and jitter
                const jitter = parseFloat((1.1 + (idx * 0.35) + Math.sin(displayHistory.length * 0.05 + idx) * 0.4).toFixed(1));
                const currentFreq = parseFloat((item.expectedFreqHz + Math.sin((displayHistory.length || 1) * 0.1 + idx) * 1.8).toFixed(1));
                
                const timingState = AnomalyDetector.evaluateCanIdTiming(
                  item.idHex,
                  item.name,
                  item.protocol,
                  item.expectedFreqHz,
                  currentFreq,
                  busLoad,
                  jitter
                );

                const isCritical = timingState.severity === 'CRITICAL';
                const isWarning = timingState.severity === 'WARNING';

                return (
                  <div
                    key={item.idHex}
                    onContextMenu={(e) => handleCardContextMenu(e, timingState)}
                    className={`group bg-white border rounded-xl p-2.5 flex flex-col justify-between transition-all select-none cursor-context-menu hover:shadow-md hover:scale-[1.01] ${
                      isCritical
                        ? 'border-rose-300 bg-rose-50/40 ring-1 ring-rose-300'
                        : isWarning
                          ? 'border-amber-300 bg-amber-50/40'
                          : 'border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/10'
                    }`}
                    title="Sağ tıkla: AI Analiz, Kopyala"
                  >
                    <div>
                      {/* Top: CAN ID + Frequency Badge */}
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-mono text-xs font-bold text-slate-900 tracking-tight">
                          {item.idHex}
                        </span>
                        <span 
                          className="px-2 py-0.5 rounded-md text-[10.5px] font-mono font-bold text-white shadow-2xs"
                          style={{ backgroundColor: isCritical ? '#EF4444' : isWarning ? '#F59E0B' : item.color }}
                        >
                          {currentFreq} Hz
                        </span>
                      </div>

                      {/* Name & Protocol */}
                      <div className="text-[11px] font-semibold text-slate-700 truncate" title={item.name}>
                        {item.name}
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate">
                        {item.protocol}
                      </div>

                      {/* Jitter & Bus Load Share Metrics */}
                      <div className="grid grid-cols-2 gap-1.5 my-2 bg-slate-50 group-hover:bg-white border border-slate-100 rounded-lg p-1.5 text-[10.5px] font-mono transition-colors">
                        <div>
                          <span className="text-slate-400 block text-[9.5px]">Jitter</span>
                          <span className="font-semibold text-slate-700">{jitter} ms</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block text-[9.5px]">Yük Payı</span>
                          <span className="font-semibold text-slate-700">%{timingState.busLoadContribution}</span>
                        </div>
                      </div>
                    </div>

                    {/* Bottom Status Indicator */}
                    <div className="pt-1.5 flex items-center justify-between border-t border-slate-100 text-[10.5px]">
                      <div className="flex items-center space-x-1 font-semibold">
                        {isCritical ? (
                          <span className="text-rose-700 flex items-center space-x-1">
                            <AlertTriangle className="w-3.5 h-3.5 text-rose-600 animate-pulse" />
                            <span>Kritik Sapma</span>
                          </span>
                        ) : isWarning ? (
                          <span className="text-amber-700 flex items-center space-x-1">
                            <Clock className="w-3.5 h-3.5 text-amber-600" />
                            <span>Zamanlama Sapması</span>
                          </span>
                        ) : (
                          <span className="text-emerald-700 flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Normal</span>
                          </span>
                        )}
                      </div>

                      <span className="text-[9.5px] text-slate-400 font-sans opacity-60 group-hover:opacity-100 transition-opacity">
                        Sağ tıkla ➔
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* HEATMAP RIGHT-CLICK CONTEXT MENU */}
      {/* ───────────────────────────────────────────────────────────── */}
      {contextMenu && contextMenu.visible && (
        <div
          style={{
            position: 'absolute',
            top: `${Math.min(contextMenu.y, 220)}px`,
            left: `${Math.min(contextMenu.x, 520)}px`,
            zIndex: 60
          }}
          className="w-56 bg-white border border-slate-200 rounded-xl shadow-xl py-1 text-xs text-slate-700 animate-in fade-in duration-100 select-none"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-100 text-[10.5px] font-mono text-slate-500 flex items-center justify-between font-bold">
            <span>{contextMenu.timingState.idHex}</span>
            <span className="text-indigo-600 font-sans text-[10px]">{contextMenu.timingState.observedFreqHz} Hz</span>
          </div>

          <div className="py-1">
            {/* 1. Ask Copilot */}
            <button
              onClick={() => handleInspectCanTiming(contextMenu.timingState)}
              className="w-full px-3 py-2 flex items-center space-x-2.5 hover:bg-indigo-50 text-indigo-700 font-semibold transition-colors text-left"
            >
              <Bot className="w-4 h-4 text-indigo-600 shrink-0" />
              <span>AI Copilot'a Analiz Ettir</span>
            </button>

            <div className="my-1 border-t border-slate-100"></div>

            {/* 2. Copy CAN ID */}
            <button
              onClick={() => copyToClipboard(contextMenu.timingState.idHex, 'CAN ID')}
              className="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-slate-50 text-slate-700 transition-colors text-left"
            >
              <Copy className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>CAN ID Kopyala</span>
            </button>

            {/* 3. Copy Signal Name & PGN */}
            <button
              onClick={() => copyToClipboard(`${contextMenu.timingState.name} (${contextMenu.timingState.protocol})`, 'Sinyal Bilgisi')}
              className="w-full px-3 py-1.5 flex items-center space-x-2.5 hover:bg-slate-50 text-slate-700 transition-colors text-left"
            >
              <Copy className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>Protokol & Sinyali Kopyala</span>
            </button>
          </div>
        </div>
      )}

      {/* Copied Toast Alert */}
      {copiedToast && (
        <div className="absolute bottom-4 right-4 z-50 bg-slate-900/95 backdrop-blur-md text-white text-xs font-sans px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-2 duration-150">
          <Check className="w-3.5 h-3.5 text-emerald-400" />
          <span>{copiedToast}</span>
        </div>
      )}
    </div>
  );
};
