import { CANFrame, TelemetryPoint, ScenarioType, DtcInfo } from '../types/can';

export const KNOWN_DTCS: Record<string, DtcInfo> = {
  P0300: {
    code: 'DTC P0300',
    title: 'Rastgele/Çoklu Silindir Ateşleme Hızı Hatası (Random Misfire)',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'critical',
    rootCauses: [
      'Buji aşınması, elektrot aralığı bozulması veya ateşleme bobini izolasyon kaçağı',
      'Enjektör püskürtme deseni bozukluğu veya yakıt rayı basınç düşüklüğü',
      '0x0CF00400 ID tork dalgalanması ve krank mili sensör sinyal gürültüsü'
    ],
    recommendedActions: [
      'Osilatör ekranında silindir ateşleme dalga boyunu kontrol ediniz.',
      'Enjektör dengeleme oranlarını ve yakıt rayı basınç sensörünü doğrulayınız.',
      'Buji ve ateşleme bobinlerinin primer/sekonder dirençlerini ölçünüz.'
    ],
    oscilloscopeNote: 'Osilatör ekranında motor devri eğrisinde ani 150-300 RPM mikro-dalgalanmalar ve tork kaybı tespit edildi.'
  },
  P0234: {
    code: 'DTC P0234',
    title: 'Turboşarj / Süperşarj Aşırı Basınç Durumu (Engine Overboost)',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'warning',
    rootCauses: [
      'Wastegate aktüatör mekanik sıkışması veya vakum kaçağı',
      'Boost kontrol selenoid valf arızası (N75 valfi tepkisiz)',
      'MAP / Takviye basınç sensörü kalibrasyon sapması'
    ],
    recommendedActions: [
      'Turbo basıncı 2.4 Bar üzerine çıktığında acil tahliye valfini test ediniz.',
      'Vakum hortumlarında kırılma veya tıkanıklık kontrolü yapınız.',
      'Wastegate kol hareket mesafesini manuel aktüatör ile doğrulayınız.'
    ],
    oscilloscopeNote: 'Turbo basınç eğrisi hedef 1.4 Bar değerini aşarak 2.45 Bar tepe noktasına ulaştı.'
  },
  P0299: {
    code: 'DTC P0299',
    title: 'Turboşarj Düşük Takviye Basıncı (Engine Underboost)',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'warning',
    rootCauses: [
      'Intercooler hava hortumlarında yırtık, kelepçe gevşekliği veya çatlak',
      'Wastegate kapağının tam kapanmaması veya egzoz türbin kanat aşınması',
      'EGR valfinin açık konumda takılı kalması'
    ],
    recommendedActions: [
      'Intercooler ve emiş borularına duman testi (smoke test) uygulayınız.',
      'EGR valfi pozisyonunu ve karbon kurum birikintisini inceleyiniz.'
    ],
    oscilloscopeNote: 'Takviye basıncı hedef değerin altında kalıyor.'
  },
  P0115: {
    code: 'DTC P0115',
    title: 'Motor Soğutma Suyu Sıcaklık Devresi Arızası (ECT Sensor)',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'warning',
    rootCauses: [
      'ECT sensör kablo demetinde şasiye kısa devre veya açık devre',
      'Termostat açık kalması veya soğutma sıvısı seviye düşüklüğü',
      'Sensör NTC direnç karakteristiğinin bozulması'
    ],
    recommendedActions: [
      '0x18FEE100 J1939 ET1 frame sıcaklık baytını kontrol ediniz.',
      'Sensör soketindeki 5V referans ve sinyal voltajını ölçünüz.',
      'Radyatör fan kontrol modülünün tetikleme durumunu izleyiniz.'
    ],
    oscilloscopeNote: 'Soğutma suyu telemetrisi 105°C eşiğini aşarak uyarı bölgesine girdi.'
  },
  P0101: {
    code: 'DTC P0101',
    title: 'Kütle Hava Akış (MAF) Sensörü Devre / Performans Sorunu',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'warning',
    rootCauses: [
      'MAF sensörü ölçüm elemanı üzerinde yağ veya toz kirliliği',
      'Hava filtresi sonrası emiş borularında kaçak (kaçak hava girişi)'
    ],
    recommendedActions: [
      'MAF sensörünü özel sensör temizleme spreyi ile temizleyiniz.',
      'Hava filtresi kutusu ve kelepçelerin sızdırmazlığını kontrol ediniz.'
    ],
    oscilloscopeNote: 'Hava akış debisi motor devrine orantısız kalıyor.'
  },
  P0171: {
    code: 'DTC P0171',
    title: 'Sistem Çok Fakir (Bank 1 - System Too Lean)',
    ecu: 'ECM (Motor Kontrol Modülü - 0x00)',
    severity: 'warning',
    rootCauses: [
      'Vakum hortumu sızıntısı veya emme manifoldu conta kaçağı',
      'Tıkalı yakıt enjektörleri veya düşük yakıt pompa basıncı',
      'Ön Lambda sensörü kirlenmesi'
    ],
    recommendedActions: [
      'Kısa ve uzun vadeli yakıt trim (STFT/LTFT) canlı verilerini izleyiniz.',
      'Yakıt rayı basıncını manometre ile doğrulayınız.'
    ],
    oscilloscopeNote: 'Lambda sensörü sürekli fakir karışım voltajı üretiyor.'
  },
  U0100: {
    code: 'DTC U0100',
    title: 'Motor Kontrol Modülü (ECM/PCM) İletişim Kaybı (CAN Bus-Off)',
    ecu: 'Ağ İletişim Ağ Geçidi (Gateway - 0x00)',
    severity: 'critical',
    rootCauses: [
      'CAN-H veya CAN-L hattında kopukluk, kısa devre veya 120Ω direnç kaybı',
      'ECM ana rölesi veya şasi hattında voltaj düşüşü',
      'Aşırı elektriksel parazit ve bus yükü taşması'
    ],
    recommendedActions: [
      'OBD-II Pin 6 ve Pin 14 arası 60Ω sonlandırma direncini ölçünüz.',
      'ECM ana besleme voltajını ve şasi sürekliliğini kontrol ediniz.'
    ],
    oscilloscopeNote: 'CAN veri yolunda ACK alınamıyor ve hata bayrakları yükseliyor.'
  }
};

const CAN_ID_LIBRARY = [
  { idHex: '0x19F20000', pgn: 61952, name: 'Proprietary Telemetry', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x0C000003', pgn: 0, name: 'Transmission Control', dlc: 8, channel: 'can0' as const, dir: 'TX' as const },
  { idHex: '0x18FEF200', pgn: 65266, name: 'J1939 LFE (Fuel Economy)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x0CF00400', pgn: 61444, name: 'J1939 EEC1 (Engine Speed/Torque)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x18FEE100', pgn: 65249, name: 'J1939 ET1 (Engine Temperature)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x18FEF600', pgn: 65270, name: 'J1939 IC1 (Turbo Boost / Inlet)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x18FEE000', pgn: 65248, name: 'J1939 TCO1 (Vehicle Speed/Distance)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x0CF00300', pgn: 61443, name: 'J1939 EEC2 (Electronic Controller 2)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x18FF0501', pgn: 65281, name: 'Vendor Proprietary Telemetry', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
  { idHex: '0x18FECA00', pgn: 65226, name: 'J1939 DM1 (Active DTCs)', dlc: 8, channel: 'vcan0' as const, dir: 'RX' as const },
];

const COLOR_PALETTES: ('blue' | 'indigo' | 'emerald' | 'slate' | 'amber' | 'rose')[][] = [
  ['blue', 'indigo', 'blue', 'indigo', 'emerald', 'slate', 'slate', 'slate'],
  ['blue', 'blue', 'emerald', 'emerald', 'indigo', 'slate', 'slate', 'slate'],
  ['indigo', 'slate', 'emerald', 'blue', 'slate', 'emerald', 'indigo', 'blue'],
  ['slate', 'emerald', 'indigo', 'emerald', 'blue', 'blue', 'slate', 'slate'],
  ['amber', 'amber', 'emerald', 'indigo', 'blue', 'slate', 'slate', 'slate'],
];

export class CANSimulatorEngine {
  private isRunning: boolean = false;
  private scenario: ScenarioType = 'nominal';
  private frameRateTarget: number = 9;
  private totalPackets: number = 15523;
  private totalDisplayed: number = 444;
  private errorFramesCount: number = 0;
  private baseStartTime: number = Date.now() - 74000;
  private currentRpm: number = 2381;
  private currentTurboBoost: number = 1.66;
  private currentCoolantTemp: number = 85;
  private busLoad: number = 0;
  private stimulusLevelPercent: number = 0;
  private rollingCounter: number = 0;
  private listeners: {
    onNewFrame?: (frame: CANFrame) => void;
    onTelemetryUpdate?: (telemetry: TelemetryPoint) => void;
    onStatsUpdate?: (stats: { totalPackets: number; busLoad: number; errorCount: number; frameRate: number }) => void;
  } = {};

  private timerId: number | null = null;
  private telemetryTimerId: number | null = null;
  private statsTimerId: number | null = null;
  private lastFrameSec: number = 74.0380;
  private framesThisSecond: number = 0;
  private bitsAccumulatedThisSecond: number = 0;
  private currentActualFrameRate: number = 0;
  private performanceStartOffset: number = typeof performance !== 'undefined' ? performance.now() : 0;

  constructor() {
    this.startSimulation();
  }

  public setStimulusLevel(pct: number) {
    this.stimulusLevelPercent = Math.max(0, Math.min(100, pct));
  }

  public setScenario(scenario: ScenarioType) {
    this.scenario = scenario;
    if (scenario === 'bus_surge') {
      this.busLoad = 78;
    } else if (scenario === 'overboost') {
      this.currentTurboBoost = 2.45;
    } else if (scenario === 'overheat') {
      this.currentCoolantTemp = 108;
    } else if (scenario === 'nominal') {
      this.busLoad = 38;
      this.currentTurboBoost = 1.66;
      this.currentCoolantTemp = 85;
      this.currentRpm = 2381;
    }
  }

  public getScenario(): ScenarioType {
    return this.scenario;
  }

  public pause() {
    this.isRunning = false;
  }

  public resume() {
    this.isRunning = true;
  }

  public toggleRunning(): boolean {
    this.isRunning = !this.isRunning;
    return this.isRunning;
  }

  public getIsRunning(): boolean {
    return this.isRunning;
  }

  public emergencyStop() {
    this.isRunning = false;
    this.busLoad = 0;
    this.currentRpm = 0;
    this.currentTurboBoost = 0.0;
  }

  public subscribe(callbacks: typeof this.listeners) {
    this.listeners = { ...this.listeners, ...callbacks };
  }

  private startSimulation() {
    const intervalMs = Math.max(16, Math.floor(1000 / this.frameRateTarget));

    this.timerId = window.setInterval(() => {
      if (!this.isRunning) return;
      this.generateNextFrame();
    }, intervalMs);

    this.telemetryTimerId = window.setInterval(() => {
      if (!this.isRunning) return;
      this.updateTelemetry();
    }, 100);

    this.statsTimerId = window.setInterval(() => {
      this.currentActualFrameRate = this.isRunning ? this.framesThisSecond : 0;
      this.framesThisSecond = 0;

      // Real physical CAN Bus Load estimation:
      // (Accumulated bits / Baud rate 250 kbps) * 100
      const nominalBaud = 250000;
      const physicalLoad = Math.round((this.bitsAccumulatedThisSecond / (nominalBaud * 0.45)) * 100);
      this.bitsAccumulatedThisSecond = 0;

      if (this.scenario === 'bus_surge') {
        this.busLoad = Math.min(96, Math.max(72, physicalLoad + 60 + Math.random() * 15));
      } else {
        this.busLoad = this.isRunning ? Math.min(65, Math.max(24, physicalLoad + 28)) : 0;
      }

      if (this.listeners.onStatsUpdate) {
        this.listeners.onStatsUpdate({
          totalPackets: this.totalPackets,
          busLoad: Math.round(this.busLoad),
          errorCount: this.errorFramesCount,
          frameRate: this.currentActualFrameRate
        });
      }
    }, 1000);
  }

  private updateTelemetry() {
    const t = Date.now() / 1000;
    let targetRpm = 2380 + Math.sin(t * 0.8) * 80 + Math.cos(t * 1.5) * 30;
    let targetTurbo = 1.66 + Math.sin(t * 0.5) * 0.12 + Math.cos(t * 1.1) * 0.05;

    if (this.scenario === 'misfire_p0300') {
      if (Math.random() > 0.6) {
        targetRpm -= 220 + Math.random() * 150;
      }
    } else if (this.scenario === 'overboost') {
      targetTurbo = 2.40 + Math.sin(t * 1.2) * 0.25;
      targetRpm += 300;
    } else if (this.scenario === 'overheat') {
      this.currentCoolantTemp = Math.min(115, this.currentCoolantTemp + 0.03);
    } else if (this.scenario === 'bus_surge') {
      this.busLoad = 75 + Math.random() * 15;
    }

    this.currentRpm = Math.max(0, Math.round(targetRpm));
    this.currentTurboBoost = Math.max(0, parseFloat(targetTurbo.toFixed(2)));

    const nowSec = (Date.now() - this.baseStartTime) / 1000;
    const point: TelemetryPoint = {
      timeSec: nowSec,
      timeFormatted: `${nowSec.toFixed(2)}s`,
      rpm: this.currentRpm,
      turboBoostBar: this.currentTurboBoost,
      coolantTempC: this.currentCoolantTemp,
      oilPressureBar: 4.2 + Math.sin(t) * 0.2,
      busLoadPercent: this.busLoad,
      errorCount: this.errorFramesCount
    };

    if (this.listeners.onTelemetryUpdate) {
      this.listeners.onTelemetryUpdate(point);
    }
  }

  private generateNextFrame(): CANFrame {
    this.totalPackets++;
    this.totalDisplayed++;
    this.framesThisSecond++;

    this.lastFrameSec += 0.0350 + Math.random() * 0.0800;
    const timeFormatted = `${this.lastFrameSec.toFixed(4)}s`;

    // Determine active CAN ID based on scenario
    let activeLibrary = CAN_ID_LIBRARY;
    if (this.scenario === 'nominal' || this.scenario === 'bus_surge') {
      // In nominal and bus_surge mode, filter out engine DTC (DM1) broadcasting
      activeLibrary = CAN_ID_LIBRARY.filter(d => d.idHex !== '0x18FECA00');
    }

    const defIndex = Math.floor(Math.random() * activeLibrary.length);
    const def = activeLibrary[defIndex];

    // Standard vs Extended Frame physical bit length estimation (with 15% bit stuffing factor)
    const isExtended = def.idHex.length > 5;
    const baseBits = isExtended ? 67 : 47;
    const frameBits = Math.round((baseBits + (def.dlc * 8)) * 1.15);
    this.bitsAccumulatedThisSecond += frameBits;

    const dataHex: string[] = [];
    const rawData: number[] = [];
    let ascii = '';

    for (let i = 0; i < def.dlc; i++) {
      let b = Math.floor(Math.random() * 256);
      if (def.idHex === '0x18FF0501') {
        if (i === 0) {
          b = Math.floor(Math.random() * 256); // Noise
        } else if (i === 1) {
          b = Math.round(this.stimulusLevelPercent * 2.5) & 0xFF; // Accelerator (0..250)
        } else if (i === 2) {
          b = (this.rollingCounter++) & 0x0F; // 4-bit Rolling counter
        } else if (i === 7) {
          b = (rawData.reduce((acc, val) => acc ^ val, 0) ^ 0xAA) & 0xFF; // Checksum
        } else {
          b = 0xFF;
        }
      } else if (def.idHex === '0x0CF00400' && i === 1) {
        b = Math.min(250, 125 + Math.round(this.stimulusLevelPercent * 1.25));
      } else if (def.idHex === '0x0CF00400' && i === 3) {
        b = Math.floor(this.currentRpm / 256);
      } else if (def.idHex === '0x0CF00400' && i === 4) {
        b = this.currentRpm % 256;
      } else if (def.idHex === '0x18FEF600' && i === 1) {
        b = Math.min(255, Math.floor(this.currentTurboBoost * 50));
      } else if (def.idHex === '0x18FECA00') {
        if (this.scenario === 'nominal') {
          // No Active DTCs: 00 FF FF FF FF FF FF FF
          b = (i === 0) ? 0x00 : 0xFF;
        } else if (this.scenario === 'misfire_p0300') {
          // Amber Lamp, SPN 651 (0x028B) / FMI 18, OC 14: 04 FF 8B 02 32 0E FF FF
          const dtcBytes = [0x04, 0xFF, 0x8B, 0x02, 0x32, 0x0E, 0xFF, 0xFF];
          b = dtcBytes[i] ?? 0xFF;
        } else if (this.scenario === 'overboost') {
          // Amber Lamp, SPN 102 (0x0066) / FMI 0, OC 7: 04 FF 66 00 20 07 FF FF
          const dtcBytes = [0x04, 0xFF, 0x66, 0x00, 0x20, 0x07, 0xFF, 0xFF];
          b = dtcBytes[i] ?? 0xFF;
        } else if (this.scenario === 'overheat') {
          // Red+Amber Lamp, SPN 110 (0x006E) / FMI 0, OC 5: 14 FF 6E 00 20 05 FF FF
          const dtcBytes = [0x14, 0xFF, 0x6E, 0x00, 0x20, 0x05, 0xFF, 0xFF];
          b = dtcBytes[i] ?? 0xFF;
        }
      }

      rawData.push(b);
      dataHex.push(b.toString(16).toUpperCase().padStart(2, '0'));
      if (b >= 32 && b <= 126) {
        ascii += String.fromCharCode(b);
      } else {
        ascii += '.';
      }
    }

    const isError = this.scenario === 'bus_surge' && Math.random() > 0.75;
    if (isError) {
      this.errorFramesCount++;
    }

    const palette = COLOR_PALETTES[Math.floor(Math.random() * COLOR_PALETTES.length)];

    const frame: CANFrame = {
      id: `frame-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      timeSec: this.lastFrameSec,
      timeFormatted,
      channel: def.channel,
      canIdHex: def.idHex,
      canIdDec: parseInt(def.idHex, 16),
      pgn: def.pgn,
      frameType: isError ? 'ERR' : 'Ext',
      dir: def.dir,
      dlc: def.dlc,
      dataHex,
      ascii,
      isErrorFrame: isError,
      colorPalette: palette,
      signalName: def.name
    };

    if (this.listeners.onNewFrame) {
      this.listeners.onNewFrame(frame);
    }

    return frame;
  }

  public destroy() {
    if (this.timerId) clearInterval(this.timerId);
    if (this.telemetryTimerId) clearInterval(this.telemetryTimerId);
    if (this.statsTimerId) clearInterval(this.statsTimerId);
  }

  public static getInitialFrames(): CANFrame[] {
    const rawSeeds = [
      { time: '74.0380s', ch: 'vcan0', id: '0x19F20000', type: 'Ext', dir: 'RX', dlc: 8, hex: ['1E', '11', '0D', '4B', '54', 'A4', '0F', 'D6'], ascii: '...KT...' },
      { time: '74.1500s', ch: 'can0',  id: '0x0C000003', type: 'Ext', dir: 'TX', dlc: 8, hex: ['0F', 'A2', '5F', '1C', '31', 'FD', 'E3', 'CD'], ascii: '.._.1...' },
      { time: '74.2350s', ch: 'vcan0', id: '0x18FEF200', type: 'Ext', dir: 'RX', dlc: 8, hex: ['8A', 'BA', '90', '6D', 'DE', 'B5', '1F', '00'], ascii: '...m....' },
      { time: '74.3160s', ch: 'vcan0', id: '0x18FEF200', type: 'Ext', dir: 'RX', dlc: 8, hex: ['E5', '2A', 'D5', '4E', 'A6', '9E', 'CB', 'DB'], ascii: '.*.N....' },
      { time: '74.4060s', ch: 'vcan0', id: '0x18FEF200', type: 'Ext', dir: 'RX', dlc: 8, hex: ['CA', 'C3', '03', 'C4', '2C', 'BE', 'C7', 'A9'], ascii: '....,...' },
      { time: '74.5230s', ch: 'can0',  id: '0x0C000003', type: 'Ext', dir: 'TX', dlc: 8, hex: ['82', '53', '6E', '86', '5E', 'E1', 'B6', 'EC'], ascii: '.Sn.^...' },
      { time: '74.6500s', ch: 'vcan0', id: '0x19F20000', type: 'Ext', dir: 'RX', dlc: 8, hex: ['C5', 'B8', '32', '8C', '60', '2A', '68', '2D'], ascii: '..2.`*h-' },
      { time: '74.7850s', ch: 'can0',  id: '0x0C000003', type: 'Ext', dir: 'TX', dlc: 8, hex: ['73', 'AA', 'C6', '7D', 'A3', 'D6', '73', '72'], ascii: 's..}..sr' },
      { time: '74.9030s', ch: 'vcan0', id: '0x0CF00300', type: 'Ext', dir: 'RX', dlc: 8, hex: ['E7', 'B9', 'B2', '0F', '19', 'C5', '4B', '36'], ascii: '.....K6' },
      { time: '75.0120s', ch: 'vcan0', id: '0x0CF00300', type: 'Ext', dir: 'RX', dlc: 8, hex: ['35', 'E0', 'C4', '13', '77', '8C', 'FE', '34'], ascii: '5...w..4' },
      { time: '75.0870s', ch: 'vcan0', id: '0x19F20000', type: 'Ext', dir: 'RX', dlc: 8, hex: ['31', '88', '6C', '2F', '6B', 'D2', '6E', 'F3'], ascii: '1.l/k.n.' },
      { time: '75.2360s', ch: 'vcan0', id: '0x18FEE100', type: 'Ext', dir: 'RX', dlc: 8, hex: ['B4', 'DD', '67', 'EC', 'F9', 'A5', '18', 'BB'], ascii: '..g.....' },
      { time: '75.3350s', ch: 'vcan0', id: '0x0CF00400', type: 'Ext', dir: 'RX', dlc: 8, hex: ['35', 'C3', '45', '3E', '03', '84', 'AB', '94'], ascii: '5.E>....' },
      { time: '75.4810s', ch: 'vcan0', id: '0x18FEF200', type: 'Ext', dir: 'RX', dlc: 8, hex: ['7C', '48', 'B6', '3D', 'DC', '58', 'F4', 'ED'], ascii: '|H.=.X..' },
      { time: '75.6000s', ch: 'vcan0', id: '0x19F20000', type: 'Ext', dir: 'RX', dlc: 8, hex: ['90', 'EF', 'BB', 'BD', 'C7', 'AB', '97', '0D'], ascii: '........' },
      { time: '75.6920s', ch: 'vcan0', id: '0x18FEF200', type: 'Ext', dir: 'RX', dlc: 8, hex: ['FF', 'C6', '45', '7D', 'DD', '25', 'F6', '51'], ascii: '..E}.%.Q' },
      { time: '75.8370s', ch: 'vcan0', id: '0x18FEE100', type: 'Ext', dir: 'RX', dlc: 8, hex: ['EA', 'C8', '8B', '44', '3C', 'AA', '2D', 'B5'], ascii: '...D<.-.' },
      { time: '75.9530s', ch: 'vcan0', id: '0x0CF00300', type: 'Ext', dir: 'RX', dlc: 8, hex: ['68', '79', '44', '0C', 'C7', '82', '41', '24'], ascii: 'hyD...A$' },
      { time: '76.0780s', ch: 'can0',  id: '0x0C000003', type: 'Ext', dir: 'TX', dlc: 8, hex: ['92', '61', '1A', '9F', 'EA', '33', '3D', '75'], ascii: '.a...3=u' },
      { time: '76.2040s', ch: 'vcan0', id: '0x0CF00400', type: 'Ext', dir: 'RX', dlc: 8, hex: ['73', 'B3', '85', 'D5', '21', '66', '4D', 'EF'], ascii: 's...!fM.' },
      { time: '76.2890s', ch: 'vcan0', id: '0x19F20000', type: 'Ext', dir: 'RX', dlc: 8, hex: ['4D', 'B0', 'CB', 'DF', '9D', 'F8', '45', '8B'], ascii: 'M.....E.' },
    ];

    return rawSeeds.map((s, idx) => ({
      id: `seed-${idx}`,
      timeSec: parseFloat(s.time.replace('s', '')),
      timeFormatted: s.time,
      channel: s.ch,
      canIdHex: s.id,
      canIdDec: parseInt(s.id, 16),
      frameType: 'Ext',
      dir: s.dir as any,
      dlc: 8,
      dataHex: s.hex,
      ascii: s.ascii,
      colorPalette: COLOR_PALETTES[idx % COLOR_PALETTES.length]
    }));
  }
}
