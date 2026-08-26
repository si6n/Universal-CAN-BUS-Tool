import { TelemetryPoint } from '../types/can';

export type SignalAnomalyType = 
  | 'RPM_TRANSIENT' 
  | 'RPM_DROP' 
  | 'RPM_SPIKE' 
  | 'BOOST_SPIKE' 
  | 'BOOST_UNDERPRESSURE' 
  | 'SENSOR_STUCK';

export type TimingAnomalyType = 
  | 'NOMINAL' 
  | 'TIMING_ANOMALY' 
  | 'MESSAGE_TIMEOUT' 
  | 'BABBLING_CANDIDATE' 
  | 'LOCAL_DRIFT';

export type AnomalySeverity = 'INFO' | 'WARNING' | 'CRITICAL';

export interface SignalAnomalyEvent {
  id: string;
  type: SignalAnomalyType;
  signalName: 'rpm' | 'turboBoost';
  timestampSec: number;
  value: number;
  delta: number;
  threshold: number;
  severity: AnomalySeverity;
  description: string;
}

export interface CanIdTimingState {
  idHex: string;
  name: string;
  protocol: string;
  expectedFreqHz: number;
  observedFreqHz: number;
  jitterMs: number;
  deviationPercent: number;
  busLoadContribution: number;
  status: TimingAnomalyType;
  severity: AnomalySeverity;
  persistenceCount: number;
}

export interface AdaptiveRange {
  minRpm: number;
  maxRpm: number;
  minTurbo: number;
  maxTurbo: number;
}

export class AnomalyDetector {
  private static rpmPersistence = 0;
  private static boostPersistence = 0;

  /**
   * Deterministic Adaptive Auto-Range calculator using rolling window min/max, guard margins and hysteresis.
   */
  public static calculateAdaptiveRange(history: TelemetryPoint[], isAutoRange: boolean): AdaptiveRange {
    if (!isAutoRange || history.length < 5) {
      return {
        minRpm: 0,
        maxRpm: 3000,
        minTurbo: 0.0,
        maxTurbo: 3.0
      };
    }

    const windowPoints = history.slice(-45);
    const rpmValues = windowPoints.map(p => p.rpm);
    const turboValues = windowPoints.map(p => p.turboBoostBar);

    const minObservedRpm = Math.min(...rpmValues);
    const maxObservedRpm = Math.max(...rpmValues);

    const minObservedTurbo = Math.min(...turboValues);
    const maxObservedTurbo = Math.max(...turboValues);

    // Calculate RPM Range with 20% guard band
    const rpmSpan = Math.max(500, maxObservedRpm - minObservedRpm);
    const targetMinRpm = Math.max(0, Math.floor((minObservedRpm - rpmSpan * 0.15) / 250) * 250);
    const targetMaxRpm = Math.ceil((maxObservedRpm + rpmSpan * 0.20) / 250) * 250;

    // Calculate Turbo Range with 0.4 Bar guard band
    const turboSpan = Math.max(0.6, maxObservedTurbo - minObservedTurbo);
    const targetMinTurbo = Math.max(0.0, parseFloat((minObservedTurbo - turboSpan * 0.15).toFixed(1)));
    const targetMaxTurbo = parseFloat((maxObservedTurbo + turboSpan * 0.25).toFixed(1));

    return {
      minRpm: targetMinRpm,
      maxRpm: Math.max(1500, targetMaxRpm),
      minTurbo: targetMinTurbo,
      maxTurbo: Math.max(1.8, targetMaxTurbo)
    };
  }

  /**
   * Scan signal history for transient glitches (Misfires, Spikes, Drops) using rate-of-change and persistence.
   */
  public static scanSignalAnomalies(history: TelemetryPoint[]): SignalAnomalyEvent[] {
    if (history.length < 3) return [];

    const events: SignalAnomalyEvent[] = [];
    const points = history.slice(-45);

    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];

      const dt = Math.max(0.01, curr.timeSec - prev.timeSec);
      const rpmRate = (curr.rpm - prev.rpm) / dt; // RPM / sec
      const rpmDelta = Math.abs(curr.rpm - prev.rpm);

      // 1. RPM Transient / Drop Detection (e.g. Misfire V-Notch > 140 RPM drop in short sample)
      if (curr.rpm < prev.rpm && (rpmDelta > 130 || Math.abs(rpmRate) > 2500)) {
        this.rpmPersistence++;
        if (this.rpmPersistence >= 1) {
          events.push({
            id: `evt-rpm-${curr.timeSec.toFixed(2)}`,
            type: 'RPM_DROP',
            signalName: 'rpm',
            timestampSec: curr.timeSec,
            value: curr.rpm,
            delta: -rpmDelta,
            threshold: 130,
            severity: rpmDelta > 220 ? 'CRITICAL' : 'WARNING',
            description: `RPM Ani Düşüşü: -${rpmDelta.toFixed(0)} RPM (Tekleme Çentiği)`
          });
        }
      } else {
        this.rpmPersistence = Math.max(0, this.rpmPersistence - 1);
      }

      // 2. Turbo Overboost Spike Detection (Pressure > 2.15 Bar)
      if (curr.turboBoostBar > 2.15) {
        this.boostPersistence++;
        if (this.boostPersistence >= 1) {
          events.push({
            id: `evt-boost-${curr.timeSec.toFixed(2)}`,
            type: 'BOOST_SPIKE',
            signalName: 'turboBoost',
            timestampSec: curr.timeSec,
            value: curr.turboBoostBar,
            delta: curr.turboBoostBar - 1.66,
            threshold: 2.15,
            severity: curr.turboBoostBar > 2.35 ? 'CRITICAL' : 'WARNING',
            description: `Aşırı Takviye Basıncı: ${curr.turboBoostBar.toFixed(2)} Bar (Hedef: 1.66 Bar)`
          });
        }
      } else {
        this.boostPersistence = Math.max(0, this.boostPersistence - 1);
      }
    }

    return events;
  }

  /**
   * Analyze CAN ID timing, jitter, frequency deviation and bus load correlation.
   */
  public static evaluateCanIdTiming(
    idHex: string,
    name: string,
    protocol: string,
    expectedFreqHz: number,
    observedFreqHz: number,
    totalBusLoadPercent: number,
    jitterMs: number
  ): CanIdTimingState {
    const deviationPercent = expectedFreqHz > 0 
      ? Math.round(((observedFreqHz - expectedFreqHz) / expectedFreqHz) * 100)
      : 0;

    let status: TimingAnomalyType = 'NOMINAL';
    let severity: AnomalySeverity = 'INFO';

    // 1. Message Timeout (0 Hz when frequency was expected)
    if (observedFreqHz <= 0.5 && expectedFreqHz > 0) {
      status = 'MESSAGE_TIMEOUT';
      severity = 'CRITICAL';
    } 
    // 2. Babbling Node / Flooding (Frequency surge + High total bus load)
    else if (deviationPercent > 80 && totalBusLoadPercent > 65) {
      status = 'BABBLING_CANDIDATE';
      severity = 'CRITICAL';
    } 
    // 3. Local Timing Anomaly / Drift
    else if (Math.abs(deviationPercent) > 30) {
      status = deviationPercent > 0 ? 'TIMING_ANOMALY' : 'LOCAL_DRIFT';
      severity = Math.abs(deviationPercent) > 60 ? 'WARNING' : 'INFO';
    }

    // Bus load contribution approximation
    const busLoadContribution = parseFloat(((observedFreqHz * 0.13)).toFixed(1));

    return {
      idHex,
      name,
      protocol,
      expectedFreqHz,
      observedFreqHz,
      jitterMs,
      deviationPercent,
      busLoadContribution,
      status,
      severity,
      persistenceCount: 3
    };
  }
}
