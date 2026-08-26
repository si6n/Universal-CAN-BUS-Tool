import React, { useState, useEffect } from 'react';
import { 
  X, 
  Settings, 
  Key, 
  Cpu, 
  Check, 
  Zap, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  Sparkles,
  Bot
} from 'lucide-react';
import { GeminiClient } from '../../services/geminiClient';
import { OpenAiClient } from '../../services/openAiClient';

export type AiProvider = 'gemini' | 'openai';

export interface AppSettings {
  channel: string;
  baudRate: string;
  provider: AiProvider;
  geminiApiKey: string;
  openaiApiKey: string;
  apiKey: string; // for backward-compatibility
}

interface SettingsModalProps {
  isOpen: boolean;
  channel: string;
  baudRate: string;
  apiKey?: string;
  onClose: () => void;
  onSave: (settings: AppSettings) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  channel: initChannel,
  baudRate: initBaud,
  apiKey: initKey,
  onClose,
  onSave
}) => {
  const [channel, setChannel] = useState(initChannel);
  const [baudRate, setBaudRate] = useState(initBaud);
  const [provider, setProvider] = useState<AiProvider>(() => {
    return (localStorage.getItem('ai_provider') as AiProvider) || 'gemini';
  });
  const [geminiKey, setGeminiKey] = useState(() => {
    return localStorage.getItem('gemini_api_key') || initKey || '';
  });
  const [openaiKey, setOpenaiKey] = useState(() => {
    return localStorage.getItem('openai_api_key') || '';
  });

  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [testMessage, setTestMessage] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setChannel(initChannel);
      setBaudRate(initBaud);
      const savedProvider = (localStorage.getItem('ai_provider') as AiProvider) || 'gemini';
      const savedGemini = localStorage.getItem('gemini_api_key') || initKey || '';
      const savedOpenai = localStorage.getItem('openai_api_key') || '';
      setProvider(savedProvider);
      setGeminiKey(savedGemini);
      setOpenaiKey(savedOpenai);
      setTestStatus('idle');
      setTestMessage('');
    }
  }, [isOpen, initChannel, initBaud, initKey]);

  if (!isOpen) return null;

  const handleTestApiKey = async () => {
    setTestStatus('testing');

    if (provider === 'gemini') {
      const keyToTest = geminiKey.trim();
      if (!keyToTest) {
        setTestStatus('error');
        setTestMessage('Lütfen önce bir Google Gemini API anahtarı girin.');
        return;
      }

      setTestMessage('Google Gemini API modelleri (3.6/3.5/2.0 Flash) taranıyor...');
      try {
        const result = await GeminiClient.discoverAndTestModel(keyToTest);
        if (result.success) {
          setTestStatus('success');
          setTestMessage(`✅ Google Gemini Bağlantısı Başarılı! Aktif Model: ${result.modelName}`);
        } else {
          setTestStatus('error');
          setTestMessage(`❌ Hata: ${result.error}`);
        }
      } catch (err: any) {
        setTestStatus('error');
        setTestMessage(`❌ Bağlantı Hatası: ${err.message || 'Ağ engeli'}`);
      }
    } else {
      const keyToTest = openaiKey.trim();
      if (!keyToTest) {
        setTestStatus('error');
        setTestMessage('Lütfen önce bir OpenAI API anahtarı (sk-...) girin.');
        return;
      }

      setTestMessage('OpenAI ChatGPT modelleri (GPT-4o, GPT-4o-mini) taranıyor...');
      try {
        const result = await OpenAiClient.discoverAndTestModel(keyToTest);
        if (result.success) {
          setTestStatus('success');
          setTestMessage(`✅ OpenAI ChatGPT Bağlantısı Başarılı! Aktif Model: ${result.modelName}`);
        } else {
          setTestStatus('error');
          setTestMessage(`❌ Hata: ${result.error}`);
        }
      } catch (err: any) {
        setTestStatus('error');
        setTestMessage(`❌ Bağlantı Hatası: ${err.message || 'Ağ engeli'}`);
      }
    }
  };

  const handleSave = () => {
    localStorage.setItem('ai_provider', provider);
    localStorage.setItem('gemini_api_key', geminiKey.trim());
    localStorage.setItem('openai_api_key', openaiKey.trim());

    onSave({
      channel,
      baudRate,
      provider,
      geminiApiKey: geminiKey.trim(),
      openaiApiKey: openaiKey.trim(),
      apiKey: provider === 'openai' ? openaiKey.trim() : geminiKey.trim()
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white border border-slate-200 rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-900">
            <Settings className="w-4 h-4 text-blue-600" />
            <span>CAN Donanım & Bulut AI Yapılandırması</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-4 space-y-4 text-xs">
          {/* Channel Selection */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-700 flex items-center space-x-1.5">
              <Cpu className="w-3.5 h-3.5 text-slate-500" />
              <span>CAN Arayüz Kanalı:</span>
            </label>
            <div className="grid grid-cols-3 gap-2">
              {['vcan0', 'can0', 'can1'].map((ch) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => setChannel(ch)}
                  className={`py-1.5 px-3 rounded-lg border font-mono font-bold text-center transition-all ${
                    channel === ch
                      ? 'bg-blue-50 border-blue-500 text-blue-700 ring-1 ring-blue-500'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>

          {/* Baud Rate Selection */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-700">
              Baud Hızı (Bitrate):
            </label>
            <div className="grid grid-cols-4 gap-2">
              {['125 kbps', '250 kbps', '500 kbps', '1000 kbps'].map((br) => (
                <button
                  key={br}
                  type="button"
                  onClick={() => setBaudRate(br)}
                  className={`py-1.5 px-2 rounded-lg border font-mono font-bold text-center transition-all ${
                    baudRate === br
                      ? 'bg-blue-50 border-blue-500 text-blue-700 ring-1 ring-blue-500'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {br.split(' ')[0]}
                </button>
              ))}
            </div>
          </div>

          {/* AI Provider Switcher */}
          <div className="space-y-2 pt-1 border-t border-slate-100">
            <label className="font-semibold text-slate-700 flex items-center justify-between">
              <span className="flex items-center space-x-1.5">
                <Bot className="w-3.5 h-3.5 text-indigo-600" />
                <span>Bulut AI Sağlayıcısı (Cloud LLM):</span>
              </span>
              <span className="text-[10px] text-slate-400 font-normal">Çoklu Model Desteği</span>
            </label>

            <div className="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-lg border border-slate-200">
              <button
                type="button"
                onClick={() => {
                  setProvider('gemini');
                  setTestStatus('idle');
                  setTestMessage('');
                }}
                className={`flex items-center justify-center space-x-1.5 py-1.5 rounded-md font-semibold text-xs transition-all ${
                  provider === 'gemini'
                    ? 'bg-white text-blue-700 shadow-xs border border-slate-200'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                <span>Google Gemini</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setProvider('openai');
                  setTestStatus('idle');
                  setTestMessage('');
                }}
                className={`flex items-center justify-center space-x-1.5 py-1.5 rounded-md font-semibold text-xs transition-all ${
                  provider === 'openai'
                    ? 'bg-white text-emerald-700 shadow-xs border border-slate-200'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Zap className="w-3.5 h-3.5 text-emerald-600" />
                <span>OpenAI ChatGPT</span>
              </button>
            </div>
          </div>

          {/* Dynamic API Key Input for Google Gemini */}
          {provider === 'gemini' && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="font-semibold text-slate-700 flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-500" />
                  <span>Google Gemini API Key:</span>
                </label>
                <button
                  type="button"
                  onClick={handleTestApiKey}
                  disabled={testStatus === 'testing' || !geminiKey.trim()}
                  className="flex items-center space-x-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 disabled:opacity-50 transition-colors"
                >
                  {testStatus === 'testing' ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Zap className="w-3 h-3" />
                  )}
                  <span>Bağlantıyı Test Et</span>
                </button>
              </div>

              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <p className="text-[10.5px] text-slate-400">
                Gemini 3.6 / 3.5 / 2.0 Flash modellerini otomatik keşfeder ve en hızlı yanıtı seçer.
              </p>
            </div>
          )}

          {/* Dynamic API Key Input for OpenAI ChatGPT */}
          {provider === 'openai' && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="font-semibold text-slate-700 flex items-center space-x-1.5">
                  <Key className="w-3.5 h-3.5 text-slate-500" />
                  <span>OpenAI API Key:</span>
                </label>
                <button
                  type="button"
                  onClick={handleTestApiKey}
                  disabled={testStatus === 'testing' || !openaiKey.trim()}
                  className="flex items-center space-x-1 text-[11px] font-semibold text-emerald-600 hover:text-emerald-800 disabled:opacity-50 transition-colors"
                >
                  {testStatus === 'testing' ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <Zap className="w-3 h-3" />
                  )}
                  <span>Bağlantıyı Test Et</span>
                </button>
              </div>

              <input
                type="password"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-proj-..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
              <p className="text-[10.5px] text-slate-400">
                GPT-4o, GPT-4o-mini ve o3-mini modelleri üzerinden derin otomotiv arıza analizi sağlar.
              </p>
            </div>
          )}

          {/* Test Status Alert */}
          {testStatus !== 'idle' && (
            <div className={`p-2.5 rounded-lg border text-[11px] flex items-start space-x-1.5 ${
              testStatus === 'testing'
                ? 'bg-blue-50 border-blue-200 text-blue-800'
                : testStatus === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800 font-medium'
                  : 'bg-rose-50 border-rose-200 text-rose-800 font-medium'
            }`}>
              {testStatus === 'testing' && <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0 mt-0.5" />}
              {testStatus === 'success' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />}
              {testStatus === 'error' && <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0 mt-0.5" />}
              <span className="leading-snug">{testMessage}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 font-semibold text-xs transition-colors"
          >
            İptal
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs flex items-center space-x-1.5 shadow-xs transition-colors"
          >
            <Check className="w-3.5 h-3.5" />
            <span>Kaydet</span>
          </button>
        </div>
      </div>
    </div>
  );
};
