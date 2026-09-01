import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { SubNav } from './components/SubNav';
import { CanSnifferTable } from './components/dashboard/CanSnifferTable';
import { SignalOscilloscope } from './components/dashboard/SignalOscilloscope';
import { AiCopilotPanel } from './components/dashboard/AiCopilotPanel';
import { EcuFlashingView } from './components/ecu/EcuFlashingView';
import { PinoutGuideView } from './components/pinout/PinoutGuideView';
import { ReportsExportView } from './components/reports/ReportsExportView';
import { SignalDiscoveryView } from './components/discovery/SignalDiscoveryView';
import { SettingsModal } from './components/modals/SettingsModal';

import { 
  CANFrame, 
  TelemetryPoint, 
  ScenarioType, 
  ActiveTab, 
  ChatMessage, 
  DiagnosticState 
} from './types/can';
import { CANSimulatorEngine } from './services/canSimulator';
import { DiagnosticEngine } from './services/diagnosticEngine';
import { DesktopBridge } from './services/bridge';

export const App: React.FC = () => {
  // Global Application State
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const [channel, setChannel] = useState('vcan0');
  const [baudRate, setBaudRate] = useState('250 kbps');
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('gemini_api_key') || '');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  // Vertical Resizer State for Dashboard (Sniffer vs Oscilloscope)
  const [snifferHeightPercent, setSnifferHeightPercent] = useState(55);
  const [isDraggingVertical, setIsDraggingVertical] = useState(false);
  const leftPanelRef = useRef<HTMLDivElement>(null);

  // Simulation & Telemetry State
  const [isSimulating, setIsSimulating] = useState(false);
  const [isEstopActive, setIsEstopActive] = useState(false);
  const [activeScenario, setActiveScenario] = useState<ScenarioType>('nominal');
  const [simulationSpeed, setSimulationSpeed] = useState<number>(1.0);
  const [busLoad, setBusLoad] = useState(0);
  const [totalPackets, setTotalPackets] = useState(0);
  const [errorCount, setErrorCount] = useState(0);
  const [frameRate, setFrameRate] = useState(0);

  // Buffer and Graph Data (Clean Live Start)
  const [frames, setFrames] = useState<CANFrame[]>([]);
  const [currentTelemetry, setCurrentTelemetry] = useState<TelemetryPoint | null>(null);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetryPoint[]>([]);

  // Engines
  const [simulator] = useState(() => new CANSimulatorEngine());
  const [diagnosticEngine] = useState(() => {
    const engine = new DiagnosticEngine();
    const savedGemini = localStorage.getItem('gemini_api_key');
    const savedOpenai = localStorage.getItem('openai_api_key');
    const savedProvider = (localStorage.getItem('ai_provider') as 'gemini' | 'openai') || 'gemini';
    if (savedGemini) engine.setApiKey(savedGemini);
    if (savedOpenai) engine.setOpenAiApiKey(savedOpenai);
    engine.setAiProvider(savedProvider);
    return engine;
  });

  // Diagnostic State & Chat (Clean Live Start)
  const [diagnosticState, setDiagnosticState] = useState<DiagnosticState>(() => 
    diagnosticEngine.evaluateSystemState('nominal', {
      timeSec: 0,
      timeFormatted: '0s',
      rpm: 0,
      turboBoostBar: 0,
      coolantTempC: 0,
      oilPressureBar: 0,
      busLoadPercent: 0,
      errorCount: 0
    })
  );

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'copilot',
      timestamp: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }),
      isDtcCard: false,
      text: `**Universal CAN-Bus Teşhis & AI Copilot Hazır**

• **Durum:** CAN veri yolu dinleniyor (\`vcan0\`).
• **Rehberlik:** Canlı veri akışı başladığında veya sistemde bir DTC hata kodu tespit edildiğinde kök neden analizi ve adım adım onarım yönergeleri burada görüntülenecektir.
• *Aşağıdaki hızlı soru butonlarını kullanarak veya mesaj yazarak teknik sorular sorabilirsiniz.*`
    }
  ]);
  const [isAiLoading, setIsAiLoading] = useState(false);

  // Vertical Resizer Drag Effect
  useEffect(() => {
    if (!isDraggingVertical) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!leftPanelRef.current) return;
      const rect = leftPanelRef.current.getBoundingClientRect();
      const relativeY = e.clientY - rect.top;
      const newPercent = (relativeY / rect.height) * 100;
      // Clamp between 20% and 80%
      setSnifferHeightPercent(Math.max(20, Math.min(80, newPercent)));
    };

    const handleMouseUp = () => {
      setIsDraggingVertical(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingVertical]);

  // Mount listeners for Telemetry & Real-time Frames
  useEffect(() => {
    simulator.subscribe({
      onNewFrame: (newFrame) => {
        setFrames((prev) => [...prev.slice(-199), newFrame]);
      },
      onNewFrameBatch: (batch) => {
        // F-35: single state update for the whole 5-frame batch
        setFrames((prev) => [...prev.slice(-(200 - batch.length)), ...batch].slice(-200));
      },
      onTelemetryUpdate: (point) => {
        setCurrentTelemetry(point);
        setTelemetryHistory((prev) => [...prev.slice(-149), point]);
      },
      onStatsUpdate: (stats) => {
        setTotalPackets(stats.totalPackets);
        setBusLoad(stats.busLoad);
        setErrorCount(stats.errorCount);
        setFrameRate(stats.frameRate);
      }
    });

    // Native Python window listener hooks
    window.onNewCanFrame = (f) => {
      setFrames((prev) => [...prev.slice(-199), f]);
    };

    window.onTelemetryTick = (p) => {
      setCurrentTelemetry(p);
      setTelemetryHistory((prev) => [...prev.slice(-149), p]);
    };

    window.onStatsTick = (s) => {
      setTotalPackets(s.totalPackets);
      setBusLoad(s.busLoad);
      setErrorCount(s.errorCount);
      setFrameRate(s.frameRate);
    };

    return () => {
      simulator.destroy();
    };
  }, [simulator]);

  // UI-alive heartbeat for the TX Watchdog (F-16 / E-11):
  // driven by the render/rAF loop, NOT a blind setInterval — if the UI
  // genuinely freezes (main-thread block), the pulse stops and the Python
  // watchdog expires (800ms timeout, 250ms pulse => 550ms tolerance).
  useEffect(() => {
    let alive = true;
    let lastSent = 0;
    const tick = () => {
      const now = performance.now();
      if (alive && now - lastSent >= 250 && window.pywebview?.api?.heartbeat) {
        lastSent = now;
        window.pywebview.api.heartbeat().catch(() => {
          // Bridge hiccup: next frame retries; watchdog tolerates misses.
        });
      }
      requestAnimationFrame(tick);
    };
    const raf = requestAnimationFrame(tick);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
    };
  }, []);

  // Update diagnostic state upon scenario change
  useEffect(() => {
    if (currentTelemetry) {
      const evalState = diagnosticEngine.evaluateSystemState(activeScenario, currentTelemetry);
      setDiagnosticState(evalState);
    }
  }, [activeScenario, currentTelemetry, diagnosticEngine]);

  // Handlers
  const handleToggleSimulator = async () => {
    const isNativeResult = await DesktopBridge.toggleSimulator();
    const nextState = isNativeResult !== null ? isNativeResult : simulator.toggleRunning();
    setIsSimulating(nextState);
    if (nextState) {
      simulator.resume();
    } else {
      simulator.pause();
      setBusLoad(0);
      setFrameRate(0);
    }
    if (isEstopActive) setIsEstopActive(false);
  };

  const handleEstop = async () => {
    await DesktopBridge.triggerEstop();
    simulator.emergencyStop();
    setIsEstopActive(true);
    setIsSimulating(false);
    setBusLoad(0);
    setFrameRate(0);
  };

  const handleSelectScenario = async (scenario: ScenarioType) => {
    await DesktopBridge.selectScenario(scenario);
    simulator.setScenario(scenario);
    setActiveScenario(scenario);
    setIsEstopActive(false);
    setIsSimulating(true);
    simulator.resume();
  };

  const handleChangeSpeed = (speed: number) => {
    setSimulationSpeed(speed);
    simulator.setSpeedMultiplier(speed);
  };

  const handleInjectFault = (type: any) => {
    simulator.injectFault(type);
  };

  const handleClearBuffer = () => {
    setFrames([]);
  };

  const handleRescan = () => {
    const point = currentTelemetry || {
      timeSec: 0,
      timeFormatted: '0s',
      rpm: 0,
      turboBoostBar: 0,
      coolantTempC: 0,
      oilPressureBar: 0,
      busLoadPercent: 0,
      errorCount: 0
    };
    const updated = diagnosticEngine.evaluateSystemState(activeScenario, point);
    setDiagnosticState({
      ...updated,
      lastScanTimestamp: new Date().toLocaleTimeString('tr-TR', { hour12: false })
    });
  };

  const handleSendMessage = async (query: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }),
      text: query
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setIsAiLoading(true);

    try {
      const response = await diagnosticEngine.generateCopilotResponse(query, diagnosticState);
      setChatMessages((prev) => [...prev, response]);
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleAskCopilotAboutFrame = (frame: CANFrame) => {
    const prompt = `Lütfen şu CAN karesini detaylı analiz et:\n\n` +
      `• CAN ID: ${frame.canIdHex} (${frame.frameType})\n` +
      `• Kanal: ${frame.channel} | Yön: ${frame.dir} | DLC: ${frame.dlc}\n` +
      `• Hex Payload: ${frame.dataHex.join(' ')}\n` +
      `• ASCII: ${frame.ascii}\n\n` +
      `Bu mesajın olası protokolünü, içerdiği fiziksel sinyalleri ve varsa aktif arıza kodunu (DTC / SPN / FMI) açıkla.`;
    handleSendMessage(prompt);
  };

  const handleSaveSettings = async (settings: any) => {
    setChannel(settings.channel);
    setBaudRate(settings.baudRate);
    setApiKey(settings.apiKey || settings.geminiApiKey || settings.openaiApiKey || '');
    
    if (settings.provider) {
      diagnosticEngine.setAiProvider(settings.provider);
      localStorage.setItem('ai_provider', settings.provider);
    }
    if (settings.geminiApiKey !== undefined) {
      diagnosticEngine.setApiKey(settings.geminiApiKey);
      localStorage.setItem('gemini_api_key', settings.geminiApiKey);
    }
    if (settings.openaiApiKey !== undefined) {
      diagnosticEngine.setOpenAiApiKey(settings.openaiApiKey);
      localStorage.setItem('openai_api_key', settings.openaiApiKey);
    }
    await DesktopBridge.updateSettings(settings);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#F8FAFC] text-slate-800 overflow-hidden select-none">
      {/* 1. Sticky Header Bar */}
      <Header
        channel={channel}
        baudRate={baudRate}
        busLoad={busLoad}
        totalPackets={totalPackets}
        isSimulating={isSimulating}
        isEstopActive={isEstopActive}
        activeScenario={activeScenario}
        simulationSpeed={simulationSpeed}
        onToggleSimulator={handleToggleSimulator}
        onSelectScenario={handleSelectScenario}
        onEstop={handleEstop}
        onChangeSpeed={handleChangeSpeed}
        onInjectFault={handleInjectFault}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* 2. Sub-Navigation Bar */}
      <SubNav
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* 3. Main Views Container */}
      <main className="flex-1 overflow-hidden p-3">
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 h-full">
            {/* Left 60% Panel: Sniffer (Top) + Resizer + Oscilloscope (Bottom) */}
            <div 
              ref={leftPanelRef}
              className="lg:col-span-7 flex flex-col h-full overflow-hidden"
            >
              {/* Top: Sniffer Table */}
              <div 
                style={{ height: `${snifferHeightPercent}%` }}
                className="min-h-[160px] overflow-hidden"
              >
                <CanSnifferTable
                  frames={frames}
                  isStreaming={isSimulating}
                  frameRate={frameRate}
                  totalDisplayedCount={frames.length}
                  errorFrameCount={errorCount}
                  onToggleStreaming={handleToggleSimulator}
                  onClearBuffer={handleClearBuffer}
                  onAskCopilot={handleAskCopilotAboutFrame}
                />
              </div>

              {/* Draggable Vertical Splitter Handle */}
              <div
                onMouseDown={() => setIsDraggingVertical(true)}
                className={`h-2.5 my-1 rounded cursor-row-resize flex items-center justify-center transition-all ${
                  isDraggingVertical 
                    ? 'bg-blue-200 ring-2 ring-blue-400/40' 
                    : 'bg-slate-200/80 hover:bg-blue-100'
                }`}
                title="Yukarı / Aşağı sürükleyerek Sniffer ve Osiloskop boyutunu ayarlayın"
              >
                <div className={`w-12 h-1 rounded-full transition-colors ${
                  isDraggingVertical ? 'bg-blue-600' : 'bg-slate-400'
                }`}></div>
              </div>

              {/* Bottom: Signal Oscilloscope */}
              <div 
                style={{ height: `calc(${100 - snifferHeightPercent}% - 14px)` }}
                className="min-h-[160px] overflow-hidden"
              >
                <SignalOscilloscope
                  currentPoint={currentTelemetry}
                  history={telemetryHistory}
                  onAskCopilot={handleSendMessage}
                />
              </div>
            </div>

            {/* Right 40% Panel: AI Diagnostic Copilot */}
            <div className="lg:col-span-5 h-full overflow-hidden">
              <AiCopilotPanel
                diagnosticState={diagnosticState}
                chatMessages={chatMessages}
                isAiLoading={isAiLoading}
                onRescan={handleRescan}
                onSendMessage={handleSendMessage}
              />
            </div>
          </div>
        )}

        {activeTab === 'signal_discovery' && (
          <SignalDiscoveryView 
            latestFrame={frames[frames.length - 1] || null}
            frames={frames}
            onStimulusChange={(lvl) => simulator.setStimulusLevel(lvl)}
            onAskCopilot={handleSendMessage}
          />
        )}

        {activeTab === 'ecu_flashing' && <EcuFlashingView />}
        {activeTab === 'pinout_guide' && <PinoutGuideView />}
        {activeTab === 'reports' && <ReportsExportView frames={frames} />}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        channel={channel}
        baudRate={baudRate}
        apiKey={apiKey}
        onClose={() => setIsSettingsOpen(false)}
        onSave={handleSaveSettings}
      />
    </div>
  );
};
