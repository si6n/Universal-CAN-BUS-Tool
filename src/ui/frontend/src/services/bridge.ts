import { CANFrame, TelemetryPoint } from '../types/can';

// Interface for pywebview Python backend bridge
declare global {
  interface Window {
    pywebview?: {
      api: {
        trigger_estop: () => Promise<void>;
        toggle_simulator: () => Promise<boolean>;
        select_scenario: (name: string) => Promise<void>;
        ask_copilot: (query: string) => Promise<string>;
        export_logs: (format: string) => Promise<boolean>;
        save_settings: (settings: { channel: string; baudRate: string; apiKey: string }) => Promise<void>;
      };
    };
    onNewCanFrame?: (frame: CANFrame) => void;
    onTelemetryTick?: (point: TelemetryPoint) => void;
    onStatsTick?: (stats: { totalPackets: number; busLoad: number; errorCount: number; frameRate: number }) => void;
  }
}

export class DesktopBridge {
  public static isNative(): boolean {
    return typeof window !== 'undefined' && !!window.pywebview;
  }

  public static async triggerEstop(): Promise<void> {
    if (this.isNative() && window.pywebview?.api?.trigger_estop) {
      await window.pywebview.api.trigger_estop();
    }
  }

  public static async toggleSimulator(): Promise<boolean | null> {
    if (this.isNative() && window.pywebview?.api?.toggle_simulator) {
      return await window.pywebview.api.toggle_simulator();
    }
    return null;
  }

  public static async selectScenario(scenario: string): Promise<void> {
    if (this.isNative() && window.pywebview?.api?.select_scenario) {
      await window.pywebview.api.select_scenario(scenario);
    }
  }

  public static async askCopilot(query: string): Promise<string | null> {
    if (this.isNative() && window.pywebview?.api?.ask_copilot) {
      return await window.pywebview.api.ask_copilot(query);
    }
    return null;
  }

  public static async updateSettings(settings: { channel: string; baudRate: string; apiKey: string }): Promise<void> {
    if (this.isNative() && (window.pywebview?.api as any)?.update_settings) {
      await (window.pywebview.api as any).update_settings(settings);
    }
  }
}
