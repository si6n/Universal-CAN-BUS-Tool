export type FrameDirection = 'RX' | 'TX';
export type FrameType = 'Std' | 'Ext' | 'FD' | 'ERR';

export interface CANFrame {
  id: string;
  timeSec: number;
  timeFormatted: string;
  channel: 'vcan0' | 'can0' | 'can1' | string;
  canIdHex: string;
  canIdDec: number;
  pgn?: number;
  frameType: FrameType;
  dir: FrameDirection;
  dlc: number;
  dataHex: string[];
  ascii: string;
  isErrorFrame?: boolean;
  colorPalette?: ('blue' | 'indigo' | 'emerald' | 'slate' | 'amber' | 'rose')[];
  signalName?: string;
}

export interface TelemetryPoint {
  timeSec: number;
  timeFormatted: string;
  rpm: number;
  turboBoostBar: number;
  coolantTempC: number;
  oilPressureBar: number;
  busLoadPercent: number;
  errorCount: number;
}

export type ScenarioType = 
  | 'nominal' 
  | 'misfire_p0300' 
  | 'overboost' 
  | 'overheat' 
  | 'bus_surge';

export interface DtcInfo {
  code: string;
  title: string;
  ecu: string;
  severity: 'warning' | 'critical';
  rootCauses: string[];
  recommendedActions: string[];
  oscilloscopeNote: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'copilot';
  timestamp: string;
  text: string;
  isDtcCard?: boolean;
  dtcInfo?: DtcInfo;
}

export type ActiveTab = 'dashboard' | 'signal_discovery' | 'ecu_flashing' | 'pinout_guide' | 'reports';

export interface DiagnosticState {
  healthStatus: 'nominal' | 'warning' | 'critical';
  dtcCount: number;
  activeDtcs: DtcInfo[];
  lastScanTimestamp: string;
  liveAnalysisTitle: string;
  liveAnalysisSummary: string;
  currentTelemetry: {
    rpm: number;
    coolantTemp: number;
    turboPressure: number;
    responseLatencyMs: number;
  };
  recommendedActions: {
    id: string;
    text: string;
    completed: boolean;
  }[];
}
