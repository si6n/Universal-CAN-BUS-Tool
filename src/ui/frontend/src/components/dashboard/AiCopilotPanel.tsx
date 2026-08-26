import React, { useState } from 'react';
import { 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle, 
  RotateCw, 
  Search, 
  Send, 
  Bot,
  Check
} from 'lucide-react';
import { DiagnosticState, ChatMessage } from '../../types/can';

interface AiCopilotPanelProps {
  diagnosticState: DiagnosticState;
  chatMessages: ChatMessage[];
  isAiLoading: boolean;
  onRescan: () => void;
  onSendMessage: (query: string) => void;
}

export const AiCopilotPanel: React.FC<AiCopilotPanelProps> = ({
  diagnosticState,
  chatMessages,
  isAiLoading,
  onRescan,
  onSendMessage
}) => {
  const [inputText, setInputText] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanToast, setScanToast] = useState<string | null>(null);
  const [checkboxState, setCheckboxState] = useState<Record<string, boolean>>({});

  const handleSend = () => {
    if (!inputText.trim()) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  const toggleCheck = (id: string) => {
    setCheckboxState(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleRescanClick = () => {
    setIsScanning(true);
    onRescan();
    setScanToast('CAN veri yolu düğümleri tarandı ve doğrulandı.');
    setTimeout(() => {
      setIsScanning(false);
    }, 800);
    setTimeout(() => {
      setScanToast(null);
    }, 3000);
  };

  const isNominal = diagnosticState.healthStatus === 'nominal';

  const renderFormattedText = (rawText: string, isCopilot: boolean) => {
    if (!isCopilot) {
      return <div className="whitespace-pre-line font-sans">{rawText}</div>;
    }

    const lines = rawText.split('\n');
    return (
      <div className="space-y-1.5 font-sans leading-relaxed">
        {lines.map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-0.5" />;

          // Parse bold **text** and code `code`
          const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
          const renderedLine = parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={pIdx} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
            }
            if (part.startsWith('`') && part.endsWith('`')) {
              return <code key={pIdx} className="font-mono bg-slate-200/70 text-indigo-700 px-1 py-0.5 rounded text-[10.5px] font-semibold">{part.slice(1, -1)}</code>;
            }
            return part;
          });

          if (trimmed.startsWith('•') || trimmed.startsWith('- ') || /^[0-9]+\./.test(trimmed)) {
            return (
              <div key={idx} className="flex items-start space-x-1.5 pl-0.5">
                <span className="text-indigo-600 font-bold shrink-0 mt-0.5">•</span>
                <span className="flex-1">{renderedLine}</span>
              </div>
            );
          }

          return <div key={idx}>{renderedLine}</div>;
        })}
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-card flex flex-col h-full overflow-hidden relative">
      {/* 1. Header (Indigo Gradient Brand) */}
      <div className="px-4 py-3 bg-gradient-to-r from-slate-50 via-white to-indigo-50/40 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
            <Sparkles className="w-4 h-4 fill-white/20" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-slate-900 tracking-normal">
              AI Diagnostic Copilot
            </h2>
            <p className="text-[10.5px] text-slate-500 font-medium">
              Derin Öğrenme CAN Teşhis Asistanı
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-200/80 text-[10.5px] font-semibold text-indigo-700">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-600 animate-pulse"></span>
          <span>Canlı Teşhis Aktif</span>
        </div>
      </div>

      {/* 2. Scrollable Body Content */}
      <div className="flex-1 p-3.5 space-y-3 overflow-y-auto">
        {/* System Health Status Card */}
        <div className={`p-3 rounded-lg border transition-all ${
          isNominal 
            ? 'bg-emerald-50/70 border-emerald-200/80' 
            : 'bg-rose-50/70 border-rose-200/80'
        }`}>
          <div className="flex items-start justify-between">
            <div className="flex items-start space-x-2.5">
              {isNominal ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              )}
              <div>
                <h3 className={`text-xs font-bold ${isNominal ? 'text-emerald-900' : 'text-rose-900'}`}>
                  {isNominal ? 'Sistem Nominal (0 DTC Hata Kodu)' : `Kritik Arıza (${diagnosticState.dtcCount} DTC Hata Kodu)`}
                </h3>
                <p className={`text-[11px] mt-0.5 ${isNominal ? 'text-emerald-700' : 'text-rose-700'}`}>
                  {isNominal 
                    ? 'Tüm CAN bus düğümleri (ECU, TCU, ABS) normal aralıkta çalışıyor.' 
                    : 'Anomali eşiği aşıldı! E-Stop veya acil kontrol önerilir.'}
                </p>
              </div>
            </div>

            <button
              onClick={handleRescanClick}
              disabled={isScanning}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-[11px] font-semibold transition-all shadow-2xs shrink-0 ml-2 ${
                isScanning
                  ? 'bg-slate-200 text-slate-500 cursor-wait'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white active:scale-95'
              }`}
              title="CAN veri yolundaki tüm düğümleri ve hata kayıtlarını yeniden tara"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
              <span>{isScanning ? 'Taranıyor...' : 'Yeniden Tara'}</span>
            </button>
          </div>
        </div>

        {/* Live Diagnosis & Root Cause Box */}
        <div className="bg-slate-50/80 border border-slate-200 rounded-lg p-3 space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-700 font-semibold">
            <div className="flex items-center space-x-1.5">
              <Search className="w-3.5 h-3.5 text-slate-500" />
              <span>Canlı Teşhis & Kök Neden Analizi</span>
            </div>
            <span className="text-[10.5px] font-mono text-slate-400 font-normal">
              Son Tarama: {diagnosticState.lastScanTimestamp}
            </span>
          </div>

          <div className="text-[11px] text-slate-600 leading-relaxed font-sans whitespace-pre-line bg-white border border-slate-200/60 rounded-md p-2.5">
            {diagnosticState.liveAnalysisSummary}
          </div>
        </div>

        {/* Recommended Actions (Checklist) */}
        <div className="bg-white border border-slate-200 rounded-lg p-3 space-y-2">
          <div className="text-xs font-bold text-slate-800">
            🛠️ Önerilen Aksiyonlar & Kontroller
          </div>
          <div className="space-y-1.5">
            {diagnosticState.recommendedActions.map((action) => (
              <label 
                key={action.id}
                className="flex items-start space-x-2 text-[11px] text-slate-700 cursor-pointer hover:text-slate-900 select-none"
              >
                <input
                  type="checkbox"
                  checked={!!checkboxState[action.id]}
                  onChange={() => toggleCheck(action.id)}
                  className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 w-3.5 h-3.5"
                />
                <span className={checkboxState[action.id] ? 'line-through text-slate-400' : 'text-slate-700'}>
                  {action.text}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Quick Query Chips */}
        <div className="flex flex-wrap gap-1.5 pt-0.5">
          <button
            onClick={() => onSendMessage('DTC P0300 ne anlama geliyor?')}
            className="text-[11px] bg-indigo-50 border border-indigo-200 text-indigo-700 font-medium px-2.5 py-1 rounded-md hover:bg-indigo-100 transition-colors shadow-2xs"
          >
            P0300 Ateşleme Arızası
          </button>
          <button
            onClick={() => onSendMessage('J1939 EEC1 frame yapısını açıkla')}
            className="text-[11px] bg-slate-100 border border-slate-200 text-slate-700 font-medium px-2.5 py-1 rounded-md hover:bg-slate-200 transition-colors"
          >
            J1939 EEC1 Tork & Devir
          </button>
          <button
            onClick={() => onSendMessage('120 Ohm sonlandırma direnci testi nasıl yapılır?')}
            className="text-[11px] bg-slate-100 border border-slate-200 text-slate-700 font-medium px-2.5 py-1 rounded-md hover:bg-slate-200 transition-colors"
          >
            120Ω Direnç Testi
          </button>
        </div>

        {/* Diagnostic Copilot Interactive Chat Stream */}
        <div className="space-y-2 pt-1">
          {chatMessages.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg border text-xs leading-relaxed ${
                msg.sender === 'copilot'
                  ? 'bg-slate-50/90 border-slate-200 text-slate-800'
                  : 'bg-indigo-600 text-white ml-auto max-w-[85%]'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5 opacity-70 text-[10px] font-mono">
                <span className="font-semibold">{msg.sender === 'copilot' ? 'AI Diagnostic Copilot' : 'Kullanıcı'}</span>
                <span>{msg.timestamp}</span>
              </div>
              <div>{renderFormattedText(msg.text, msg.sender === 'copilot')}</div>
            </div>
          ))}

          {isAiLoading && (
            <div className="p-3 bg-indigo-50/60 border border-indigo-200 rounded-lg flex items-center space-x-2 text-xs text-indigo-700">
              <Bot className="w-4 h-4 animate-bounce" />
              <span>AI Copilot canlı CAN akışını analiz ediyor...</span>
            </div>
          )}
        </div>
      </div>

      {/* 3. Message Input Box */}
      <div className="p-2.5 bg-slate-50 border-t border-slate-200 flex items-center space-x-2">
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="CAN telemetrisi veya arıza sorusu yazın..."
          className="flex-1 px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all font-sans"
        />
        <button
          onClick={handleSend}
          disabled={!inputText.trim() || isAiLoading}
          className="p-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg transition-colors shadow-2xs"
          title="Mesaj Gönder"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Scan Feedback Toast */}
      {scanToast && (
        <div className="absolute top-16 right-4 z-50 bg-slate-900/90 backdrop-blur-md text-white text-xs font-sans px-3 py-1.5 rounded-lg shadow-lg flex items-center space-x-2 animate-in fade-in slide-in-from-top-2 duration-150">
          <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span>{scanToast}</span>
        </div>
      )}
    </div>
  );
};
