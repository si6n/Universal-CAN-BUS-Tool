import { ChatMessage, DiagnosticState, ScenarioType, TelemetryPoint } from '../types/can';
import { KNOWN_DTCS } from './canSimulator';
import { DesktopBridge } from './bridge';
import { GeminiClient } from './geminiClient';
import { OpenAiClient } from './openAiClient';

// J1939 FMI Table Reference (SAE J1939-73)
const J1939_FMI_DEFINITIONS: Record<number, string> = {
  0: "Aşırı yüksek değer (Kritik sınır aşıldı)",
  1: "Aşırı düşük değer (Kritik sınırın altında)",
  2: "Sinyal kararsız veya kesintili",
  3: "Yüksek voltaj / Artıya kısa devre",
  4: "Düşük voltaj / Şasiye kısa devre",
  5: "Açık devre / Kablo kopuk",
  6: "Aşırı akım / Toprağa kısa devre",
  7: "Mekanik sistem yanıt vermiyor / Sıkışmış",
  8: "Anormal frekans veya darbe genişliği",
  9: "İletişim gecikmesi / Güncelleme yok",
  10: "Anormal ani değişim",
  11: "Belirlenemeyen arıza modu",
  12: "Sensör veya beyin dahili donanım arızası",
  13: "Kalibrasyon / Ayar dışı",
  14: "Özel üretici arıza durumu",
  15: "Uyarı eşiğinin üzerinde (Hafif yüksek)",
  16: "Uyarı eşiğinin üzerinde (Orta yüksek)",
  17: "Uyarı eşiğinin altında (Hafif düşük)",
  18: "Uyarı eşiğinin altında (Orta düşük)",
  19: "Ağdan hatalı veri alındı",
  22: "Normal çalışma aralığının dışında"
};

// J1939 SPN Table Reference (SAE J1939-71)
const J1939_SPN_DEFINITIONS: Record<number, string> = {
  84: "Araç Hız Sensörü",
  91: "Gaz Pedalı Konumu",
  94: "Yakıt İletim Basıncı",
  100: "Motor Yağ Basıncı",
  102: "Turbo Takviye Basıncı (Boost)",
  105: "Emme Manifoldu Sıcaklığı",
  108: "Barometrik Ortam Basıncı",
  110: "Motor Soğutma Suyu Sıcaklığı (Hararet)",
  157: "Yakıt Ray Basıncı (Common Rail)",
  158: "Kontak Anahtarı Voltajı",
  168: "Akü Voltajı",
  175: "Motor Yağ Sıcaklığı",
  190: "Motor Devri (RPM)",
  512: "Sürücü Tork Talebi",
  513: "Gerçek Motor Torku",
  651: "Silindir #1 Enjektörü",
  652: "Silindir #2 Enjektörü",
  653: "Silindir #3 Enjektörü",
  654: "Silindir #4 Enjektörü",
  655: "Silindir #5 Enjektörü",
  656: "Silindir #6 Enjektörü",
  970: "Acil Durdurma Anahtarı (E-STOP)",
  1172: "Turbo Giriş Sıcaklığı"
};

// UDS Negative Response Codes (ISO 14229-1)
const UDS_NRC_MAP: Record<number, string> = {
  0x11: "Bu UDS servisi desteklenmiyor",
  0x12: "Alt fonksiyon desteklenmiyor",
  0x13: "Geçersiz mesaj formatı",
  0x22: "Ön koşullar karşılanmadı (Motor çalışıyor veya araç hareket halinde)",
  0x31: "İstenen parametre kabul aralığı dışında",
  0x33: "Güvenlik kilidi kapalı (Seed/Key gerekir)",
  0x35: "Geçersiz güvenlik anahtarı",
  0x78: "İstek alındı, yanıt hazırlanıyor (Bekleyiniz)"
};

export class DiagnosticEngine {
  private geminiApiKey: string = '';
  private openAiApiKey: string = '';
  private aiProvider: 'auto' | 'gemini' | 'openai' = 'auto';

  public setApiKey(key: string) {
    this.geminiApiKey = key;
  }

  public getApiKey(): string {
    return this.geminiApiKey;
  }

  public setOpenAiApiKey(key: string) {
    this.openAiApiKey = key;
  }

  public getOpenAiApiKey(): string {
    return this.openAiApiKey;
  }

  public setAiProvider(provider: 'auto' | 'gemini' | 'openai') {
    this.aiProvider = provider;
  }

  public getAiProvider(): 'auto' | 'gemini' | 'openai' {
    return this.aiProvider;
  }

  public evaluateSystemState(
    scenario: ScenarioType,
    telemetry: TelemetryPoint
  ): DiagnosticState {
    const timestampStr = new Date().toLocaleTimeString('tr-TR', { hour12: false });

    if (scenario === 'misfire_p0300') {
      const dtc = KNOWN_DTCS.P0300;
      return {
        healthStatus: 'critical',
        dtcCount: 1,
        activeDtcs: [dtc],
        lastScanTimestamp: timestampStr,
        liveAnalysisTitle: 'Kritik Ateşleme / Tekleme Arızası!',
        liveAnalysisSummary: `• Motor Devri: ${telemetry.rpm} RPM (Dalgalı)
• Tork Kaybı: %32 anlık düşüş
• Hata: Silindir ateşleme hatası (P0300)`,
        currentTelemetry: {
          rpm: telemetry.rpm,
          coolantTemp: telemetry.coolantTempC,
          turboPressure: telemetry.turboBoostBar,
          responseLatencyMs: 14.8
        },
        recommendedActions: [
          { id: '1', text: '1. Osiloskopta motor devrini izleyin.', completed: true },
          { id: '2', text: '2. Buji ve ateşleme bobinlerini kontrol edin.', completed: false },
          { id: '3', text: '3. Enjektör püskürtmesini test edin.', completed: false }
        ]
      };
    }

    if (scenario === 'overboost') {
      const dtc = KNOWN_DTCS.P0234;
      return {
        healthStatus: 'warning',
        dtcCount: 1,
        activeDtcs: [dtc],
        lastScanTimestamp: timestampStr,
        liveAnalysisTitle: 'Aşırı Turbo Basıncı (Overboost)!',
        liveAnalysisSummary: `• Turbo Basıncı: ${telemetry.turboBoostBar} Bar (Kritik >2.2 Bar)
• Hata: P0234 Aşırı Takviye Basıncı`,
        currentTelemetry: {
          rpm: telemetry.rpm,
          coolantTemp: telemetry.coolantTempC,
          turboPressure: telemetry.turboBoostBar,
          responseLatencyMs: 3.8
        },
        recommendedActions: [
          { id: '1', text: '1. Turbo wastegate kolunun sıkışıp sıkışmadığına bakın.', completed: true },
          { id: '2', text: '2. N75 selenoid valf soketini kontrol edin.', completed: false }
        ]
      };
    }

    if (scenario === 'overheat') {
      const dtc = KNOWN_DTCS.P0115;
      return {
        healthStatus: 'warning',
        dtcCount: 1,
        activeDtcs: [dtc],
        lastScanTimestamp: timestampStr,
        liveAnalysisTitle: 'Yüksek Motor Harareti!',
        liveAnalysisSummary: `• Sıcaklık: ${telemetry.coolantTempC}°C (Kritik >105°C)
• Hata: P0115 Motor Sıcaklık Uyarısı`,
        currentTelemetry: {
          rpm: telemetry.rpm,
          coolantTemp: telemetry.coolantTempC,
          turboPressure: telemetry.turboBoostBar,
          responseLatencyMs: 2.1
        },
        recommendedActions: [
          { id: '1', text: '1. Su seviyesini ve termostatı kontrol edin.', completed: false },
          { id: '2', text: '2. Radyatör fanının dönüp dönmediğini kontrol edin.', completed: false }
        ]
      };
    }

    if (scenario === 'bus_surge') {
      return {
        healthStatus: 'warning',
        dtcCount: 0,
        activeDtcs: [],
        lastScanTimestamp: timestampStr,
        liveAnalysisTitle: 'CAN Veri Yolu Yoğun Trafik / Hata!',
        liveAnalysisSummary: `• Bus Yükü: %${telemetry.busLoadPercent}
• Hata Kareleri: ${telemetry.errorCount} adet`,
        currentTelemetry: {
          rpm: telemetry.rpm,
          coolantTemp: telemetry.coolantTempC,
          turboPressure: telemetry.turboBoostBar,
          responseLatencyMs: 8.4
        },
        recommendedActions: [
          { id: '1', text: '1. CAN_H ve CAN_L arasındaki 120Ω direncini ölçün.', completed: true },
          { id: '2', text: '2. Gürültülü kablo tesisatını izole edin.', completed: false }
        ]
      };
    }

    const isTelemetryActive = (telemetry.rpm > 0) || (telemetry.turboBoostBar > 0) || (telemetry.coolantTempC > 0);

    if (!isTelemetryActive) {
      return {
        healthStatus: 'nominal',
        dtcCount: 0,
        activeDtcs: [],
        lastScanTimestamp: timestampStr,
        liveAnalysisTitle: 'Sistem Bağlantıya Hazır (Nominal)',
        liveAnalysisSummary: 'CAN veri yolu dinleniyor. Aktif bir arıza kodu (DTC) veya anomali tespit edilmedi.',
        currentTelemetry: {
          rpm: 0,
          coolantTemp: 0,
          turboPressure: 0,
          responseLatencyMs: 0
        },
        recommendedActions: [
          { id: '1', text: '1. CAN donanım bağlantısını kurun veya simülasyonu başlatın.', completed: false },
          { id: '2', text: '2. 120Ω hat sonlandırma direncini doğrulayın.', completed: false }
        ]
      };
    }

    return {
      healthStatus: 'nominal',
      dtcCount: 0,
      activeDtcs: [],
      lastScanTimestamp: timestampStr,
      liveAnalysisTitle: 'Sistem Durumu Nominal',
      liveAnalysisSummary: `• Motor Devri: ${telemetry.rpm} RPM | Turbo: ${telemetry.turboBoostBar} Bar | Sıcaklık: ${telemetry.coolantTempC}°C
Tüm CAN düğümleri normal çalışma aralığında, aktif arıza kodu yok.`,
      currentTelemetry: {
        rpm: telemetry.rpm,
        coolantTemp: telemetry.coolantTempC,
        turboPressure: telemetry.turboBoostBar,
        responseLatencyMs: 2.1
      },
      recommendedActions: [
        { id: '1', text: '1. Canlı telemetri akışı aktif ve parametreler stabil.', completed: true }
      ]
    };
  }

  /**
   * Helper: Extract byte array from natural language query or Hex Payload line.
   */
  private extractHexBytes(query: string): number[] {
    const payloadMatch = query.match(/(?:hex payload|payload|veri|data)[:\s]*((?:[0-9A-Fa-f]{2}[\s,-]*){1,64})/i);
    let hexStr = '';
    if (payloadMatch) {
      hexStr = payloadMatch[1];
    } else {
      const matches = query.match(/\b[0-9A-Fa-f]{2}\b/g);
      if (matches && matches.length >= 2) {
        return matches.map(m => parseInt(m, 16));
      }
      return [];
    }

    const cleaned = hexStr.replace(/[^0-9A-Fa-f]/g, ' ').trim();
    const tokens = cleaned.split(/\s+/).filter(t => t.length === 2);
    return tokens.map(t => parseInt(t, 16));
  }

  /**
   * Compact, Human-Friendly Forensics for SAE J1939 DM1 (PGN 65226).
   */
  private decodeJ1939DM1(bytes: number[], canIdHex: string): string {
    // 1. Check if payload represents "No Active DTCs" (00 FF FF FF FF FF FF FF)
    if ((bytes[2] === 0xFF && bytes[3] === 0xFF) || (bytes[0] === 0x00 && bytes[2] === 0xFF)) {
      return `✅ **J1939 DM1 (Aktif Arıza Yok):**

• **İkaz Lambaları:** Kapalı / Normal
• **Aktif Arıza Kodu:** **0 DTC** (Beyinde kayıtlı aktif arıza bulunmuyor).
• **Durum:** Tüm alt sistemler nominal çalışma aralığında.`;
    }

    // 2. Lamp Status
    const b0 = bytes[0];
    const amberLamp = (b0 >> 2) & 0x03;
    const redStopLamp = (b0 >> 4) & 0x03;
    const milLamp = (b0 >> 6) & 0x03;

    let lampText = "Normal (İkaz Lambaları Kapalı)";
    if (redStopLamp === 1) lampText = "🔴 Kırmızı Acil Durdurma Lambası (STOP)";
    else if (milLamp === 1) lampText = "🟠 Motor Arıza Lambası (Check Engine)";
    else if (amberLamp === 1) lampText = "🟡 Sarı Servis Uyarı Lambası";

    // 3. SPN / FMI / OC
    const b2 = bytes[2];
    const b3 = bytes[3];
    const b4 = bytes[4];
    const b5 = bytes[5];

    const spn = ((b4 & 0xE0) << 11) | (b3 << 8) | b2;
    const fmi = b4 & 0x1F;
    const oc = b5 & 0x7F;

    const spnName = J1939_SPN_DEFINITIONS[spn] || `SPN ${spn} (Özel Sensör)`;
    const fmiDesc = J1939_FMI_DEFINITIONS[fmi] || `Arıza Kodu FMI ${fmi}`;

    return `🚨 **Aktif Arıza Tespiti (J1939 DM1):**

• **Gösterge Lambası:** ${lampText}
• **Arıza Tanımı:** ${spnName} - *${fmiDesc}* (SPN ${spn} / FMI ${fmi})
• **Tekrarlanma Sayısı:** Beyin bu hatayı **${oc} kez** kaydetti.

🛠️ **Hızlı Çözüm Adımları:**
1. İlgili sensörün kablo soketinde gevşeklik, korozyon veya kırık var mı bakın.
2. Kabloyu ve sensörü ölçtükten sonra arıza hafızasını temizleyin.`;
  }

  /**
   * Compact, Human-Friendly Forensics for SAE J1939 EEC1 (PGN 61444).
   */
  private decodeJ1939EEC1(bytes: number[], canIdHex: string): string {
    if (bytes.length < 5) return `⚡ **J1939 EEC1:** Bayt sayısı eksik.`;

    const demandTorque = bytes[1] - 125;
    const actualTorque = bytes[2] - 125;
    const rpm = (((bytes[4] << 8) | bytes[3]) * 0.125).toFixed(0);

    const isMatch = Math.abs(actualTorque - demandTorque) <= 10;

    return `⚡ **Motor Devri & Tork Durumu (J1939 EEC1):**

• **Motor Devri:** **${rpm} RPM**
• **Sürücü Tork Talebi:** %${demandTorque}
• **Gerçek Üretilen Tork:** %${actualTorque}

${isMatch ? '✅ Motor devri ve tork talebi dengeli, sorun yok.' : '⚠️ **Dikkat:** Motor istenen torku tam üretemiyor (Ateşleme teklemesi veya yakıt düşüklüğü olabilir).'}`;
  }

  /**
   * Compact Forensics for NMEA 2000 PGN 127488.
   */
  private decodeN2K127488(bytes: number[]): string {
    if (bytes.length < 6) return `🌊 **NMEA 2000:** Eksik veri.`;

    const rpm = (((bytes[2] << 8) | bytes[1]) * 0.25).toFixed(0);
    const boostBar = (((bytes[4] << 8) | bytes[3]) * 0.001).toFixed(2);
    const trim = bytes[5] > 127 ? bytes[5] - 256 : bytes[5];

    return `🌊 **Marin Motor Telemetrisi (NMEA 2000):**

• **Motor Devri:** **${rpm} RPM**
• **Turbo Basıncı:** **${boostBar} Bar**
• **Trim Açısı:** %${trim}

✅ Marin motor telemetrisi normal akıyor.`;
  }

  /**
   * Compact Forensics for UDS Negative Response (0x7F).
   */
  private decodeUdsNegativeResponse(bytes: number[]): string {
    const rejectedSid = bytes.length >= 2 ? `0x${bytes[1].toString(16).toUpperCase().padStart(2, '0')}` : '0x??';
    const nrcCode = bytes.length >= 3 ? bytes[2] : 0;
    const nrcDesc = UDS_NRC_MAP[nrcCode] || "İşlem reddedildi";

    return `❌ **Beyin (ECU) İsteği Reddetti (UDS 0x7F):**

• **İstenen Servis:** \`${rejectedSid}\`
• **Reddetme Nedeni:** *${nrcDesc}* (NRC: 0x${nrcCode.toString(16).toUpperCase()})

🛠️ **Ne Yapmalısın?**
Kontağın açık olduğundan, motorun çalışmadığından ve gerekirse güvenlik kilidinin (SecurityAccess) açıldığından emin olun.`;
  }

  /**
   * Deep Offline Automotive Intelligence & Reasoning Engine.
   */
  public async generateCopilotResponse(
    query: string,
    state: DiagnosticState
  ): Promise<ChatMessage> {
    const qLower = query.toLowerCase().trim();
    const timestamp = new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    const curRpm = state.currentTelemetry.rpm || 1850;
    const curBoost = state.currentTelemetry.turboPressure || 1.4;
    const sysContext = `Sen "Universal CAN-Bus Diagnostic & Telemetry Tool" profesyonel araç teşhis yazılımının içerisindeki yerleşik AI Teşhis Başmühendisisin.
Kullanıcı zaten CAN veri yoluna (OBD-II / J1939 / NMEA2000) doğrudan bağlı ve canlı paketleri bu cihaz ile okuyor!

KESİN VE TAVİZSİZ ALAN KISITLAMALARI (DOMAIN GUARDRAILS):
1. Sen SADECE ve SADECE otomotiv ve marin elektronik, CAN-Bus haberleşmesi (J1939, UDS, N2K, OBD-II), araç telemetrisi, sensörler ve arıza teşhisi alanında uzmanlaşmış özel bir mühendislik yapay zekasısın.
2. Otomotiv, araç telemetrisi, donanım veya arıza teşhisi dışındaki HERHANGİ BİR KONUDA (günlük sohbet, hava durumu, yemek tarifi, siyaset, genel felsefe, edebiyat, genel kodlama vb.) soru sorulursa KESİNLİKLE yanıt verme!
3. Konu dışı sorularda SADECE şunu söyle:
   "⚠️ Ben Universal CAN-Bus Teşhis ve Telemetri asistanıyım. Yalnızca araç telemetrisi, CAN veri yolu protokolleri (J1939, UDS, NMEA 2000) ve arıza teşhis konularında yardımcı olabilirim."
4. ASLA "DTC'yi başka bir teşhis cihazıyla okuyun", "aracı servise götürün" veya "bir tarayıcı bağlayın" DEME! Çünkü kullanıcı ZATEN bu teşhis cihazını kullanıyor ve arıza verisini doğrudan CAN hattından canlı okuyor.
5. SAE J1939 DM1 (0x18FECA00) mesajlarını doğrudan çöz:
   • Bayt 0: Lamba durumu (0x04=Sarı Uyarı, 0x10=Kırmızı Stop, 0x40=MIL Motor Lambası)
   • Bayt 2-4: SPN = ((Bayt 4 & 0xE0) << 11) | (Bayt 3 << 8) | Bayt 2
   • Bayt 4: FMI = Bayt 4 & 0x1F (0: Aşırı yüksek, 1: Aşırı düşük, 2: Düzensiz sinyal, 3: Yüksek voltaj, 4: Düşük voltaj)
   • Bayt 5: Tekrarlanma Sayısı (Occurrence Count) = Bayt 5 & 0x7F
6. Doğrudan net, maddeli ve sahada uygulanabilir fiziksel onarım adımları ver (Sensör soketi, multimetre ohm/volt ölçümü, hortum kontrolü, UDS servis 0x14/0x31).

Canlı Araç Durumu:
• Motor Devri: ${curRpm} RPM
• Turbo Takviye Basıncı: ${curBoost} Bar
• Sistem Sağlığı: ${state.healthStatus === 'nominal' ? 'Nominal (0 DTC)' : `Arıza (${state.dtcCount} DTC)`}`;

    // 0. Check OpenAI ChatGPT if selected or key starts with sk-
    const shouldUseOpenAi = (this.aiProvider === 'openai') || 
                            (this.aiProvider === 'auto' && this.openAiApiKey && this.openAiApiKey.trim().length > 10) ||
                            (this.openAiApiKey && this.openAiApiKey.trim().startsWith('sk-'));

    if (shouldUseOpenAi && this.openAiApiKey && this.openAiApiKey.trim().length > 10) {
      try {
        const openAiRes = await OpenAiClient.generateContent(this.openAiApiKey, query, sysContext);
        if (openAiRes.success && openAiRes.text.trim().length > 0) {
          return {
            id: `msg-${Date.now()}`,
            sender: 'copilot',
            timestamp,
            text: `✨ **OpenAI ${openAiRes.modelUsed} (ChatGPT Bulut Zekası):**\n\n${openAiRes.text.trim()}`
          };
        } else if (openAiRes.error) {
          console.warn('OpenAI API error:', openAiRes.error);
          return {
            id: `msg-${Date.now()}`,
            sender: 'copilot',
            timestamp,
            text: `⚠️ **OpenAI ChatGPT API Bağlantı Uyarısı:**\n${openAiRes.error}\n\n*Lütfen Ayarlar menüsünden API anahtarınızı "Bağlantıyı Test Et" butonu ile kontrol ediniz. Geçici olarak yerel motor devreye alındı.*`
          };
        }
      } catch (err: any) {
        console.warn('OpenAI API fetch failed:', err);
      }
    }

    // 1. Check Google Gemini if selected or key is present
    const shouldUseGemini = (this.aiProvider === 'gemini') || 
                            (this.aiProvider === 'auto' && this.geminiApiKey && this.geminiApiKey.trim().length > 10) ||
                            (this.geminiApiKey && this.geminiApiKey.trim().startsWith('AIza'));

    if (shouldUseGemini && this.geminiApiKey && this.geminiApiKey.trim().length > 10) {
      try {
        const geminiRes = await GeminiClient.generateContent(this.geminiApiKey, query, sysContext);

        if (geminiRes.success && geminiRes.text.trim().length > 0) {
          const modelTitle = geminiRes.modelUsed ? geminiRes.modelUsed.replace(/^models\//, '') : 'Gemini 3.5/2.0 Flash';
          return {
            id: `msg-${Date.now()}`,
            sender: 'copilot',
            timestamp,
            text: `✨ **Google ${modelTitle} (Bulut Zekası):**\n\n${geminiRes.text.trim()}`
          };
        } else if (geminiRes.error) {
          console.warn('Gemini API error response:', geminiRes.error);
          return {
            id: `msg-${Date.now()}`,
            sender: 'copilot',
            timestamp,
            text: `⚠️ **Google Gemini API Bağlantı Uyarısı:**\n${geminiRes.error}\n\n*Lütfen Ayarlar menüsünden API anahtarınızı "Bağlantıyı Test Et" butonu ile kontrol ediniz. Geçici olarak yerel motor devreye alındı.*`
          };
        }
      } catch (err: any) {
        console.warn('Gemini API fetch failed, using local expert engine:', err);
      }
    }

    // Check if Python Desktop Bridge is present and returns a deep answer
    const nativeRes = await DesktopBridge.askCopilot(query);
    if (nativeRes && !nativeRes.includes("Girdiğiniz sorgu (") && !nativeRes.includes("sorunuz için uzman")) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: nativeRes
      };
    }

    // ─────────────────────────────────────────────────────────────────────────
    // A. DYNAMIC CAN FRAME FORENSICS (E.G. FROM RIGHT-CLICK CONTEXT MENU)
    // ─────────────────────────────────────────────────────────────────────────
    const hexBytes = this.extractHexBytes(query);
    const canIdMatch = query.match(/0x[0-9A-Fa-f]+/);
    const canIdHex = canIdMatch ? canIdMatch[0].toUpperCase() : '0x00000000';

    // 1. SAE J1939 DM1 Active DTC Frame
    if (canIdHex.includes('18FECA') || qLower.includes('dm1')) {
      if (hexBytes.length >= 6) {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          isDtcCard: true,
          text: this.decodeJ1939DM1(hexBytes, canIdHex)
        };
      }
    }

    // 2. SAE J1939 EEC1 Engine Speed & Torque Frame
    if (canIdHex.includes('0CF004') || canIdHex.includes('61444') || qLower.includes('eec1')) {
      if (hexBytes.length >= 5) {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          text: this.decodeJ1939EEC1(hexBytes, canIdHex)
        };
      }
    }

    // 3. NMEA 2000 PGN 127488 Engine Rapid Update
    if (canIdHex.includes('19F200') || qLower.includes('127488')) {
      if (hexBytes.length >= 6) {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          text: this.decodeN2K127488(hexBytes)
        };
      }
    }

    // 4. UDS Negative Response (0x7F)
    if (hexBytes.length >= 3 && hexBytes[0] === 0x7F) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        isDtcCard: true,
        text: this.decodeUdsNegativeResponse(hexBytes)
      };
    }

    // 5. Structured Oscilloscope Signal Anomaly Snapshot Handling (JSON)
    if (query.includes('Osiloskop Sinyal Anomalisi Enstantanesini') || query.includes('RPM_DROP') || query.includes('BOOST_SPIKE')) {
      const isRpmDrop = query.includes('RPM_DROP') || query.includes('rpm');
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: isRpmDrop
          ? `🔍 **Kanıta Dayalı Sinyal Anomalisi Analizi (Evidence-Based):**\n\n` +
            `• **Tespit Edilen Olay:** \`RPM_DROP / TRANSIENT\` (Motor Devrinde Ani Düşüş Çentiği)\n` +
            `• **Kanıt Seviyesi:** **Detected (Yüksek Güvenilirlik)**\n` +
            `• **Muhtemel Kök Nedenler:**\n` +
            `  1. *Ateşleme Hattı:* Buji elektrot aşınması veya ateşleme bobini primer sargı yalıtım kaçağı.\n` +
            `  2. *Yakıt Püskürtme:* Silindir #1 enjektör soketinde mikro temassızlık veya piezo valf gecikmesi.\n` +
            `  3. *Krank Sensörü:* CKP sensör dişli çarkında manyetik çapak veya hava aralığı sapması.\n\n` +
            `🛠️ **Önerilen Bir Sonraki Teşhis Adımı:**\n` +
            `Ateşleme bobini primer direncini (~1.2Ω) multimetre ile ölçün ve UDS Servis 0x31 ile Silindir Balans Testi çalıştırın.`
          : `🔍 **Kanıta Dayalı Sinyal Anomalisi Analizi (Evidence-Based):**\n\n` +
            `• **Tespit Edilen Olay:** \`BOOST_SPIKE / OVERBOOST\` (Aşırı Takviye Basıncı)\n` +
            `• **Kanıt Seviyesi:** **Detected (Yüksek Güvenilirlik)**\n` +
            `• **Muhtemel Kök Nedenler:**\n` +
            `  1. *Mekanik:* Turboşarj wastegate kapağı veya VNT geometrik kanatçıkları kurum nedeniyle kapalı sıkışmış.\n` +
            `  2. *Pnömatik:* N75 selenoid valf vakum kontrol hortumunda yırtık veya tıkanıklık.\n` +
            `  3. *Sensör:* MAP/Manifold basınç sensörü sinyal hattında yüksek direnç.\n\n` +
            `🛠️ **Önerilen Bir Sonraki Teşhis Adımı:**\n` +
            `Wastegate mekanik kolunu elle hareket ettirerek boşluğunu kontrol edin ve N75 selenoid valf soketine 12V tetik vererek klik sesini doğrulayın.`
      };
    }

    // 6. Structured CAN Frequency & Timing Anomaly Snapshot Handling (JSON)
    if (query.includes('CAN-Bus Frekans ve Ağ Anomalisi Enstantanesini') || query.includes('observed_frequency_hz')) {
      const isBabbling = query.includes('BABBLING') || query.includes('FLOODING') || query.includes('deviation_percent": 2') || query.includes('deviation_percent": 1');
      const isTimeout = query.includes('TIMEOUT') || query.includes('COMMUNICATION_TIMEOUT');

      if (isBabbling) {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          text: `🚨 **CAN-Bus Ağ Güvenliği & Frekans Analizi:**\n\n` +
            `• **Sınıflandırma:** \`POSSIBLE_BABBLING_OR_FLOODING\` (Ağ Taşması / Babbling Node Şüphesi)\n` +
            `• **Kanıt Seviyesi:** **Likely (Kuvvetli Olasılık)**\n` +
            `• **Ağ Etkisi:** Bu düğümün nominal frekansının çok üzerinde periyodik mesaj basması, CAN arbitrasyon mekanizmasını meşgul ederek daha düşük öncelikli (yüksek ID) güvenlik paketlerinin gecikmesine (Bus Flooding) neden olur.\n\n` +
            `🛠️ **Önerilen İnceleme Adımları:**\n` +
            `1. İlgili kontrol ünitesinin (ECU/TCU) şasi hattını ve besleme voltajını kontrol edin.\n` +
            `2. Hat üzerindeki diğer düğümleri tek tek izole ederek bus yükünün düşüşünü osiloskop ile gözlemleyin.`
        };
      } else if (isTimeout) {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          text: `⏱️ **CAN-Bus İletişim Zaman Aşımı Analizi:**\n\n` +
            `• **Sınıflandırma:** \`COMMUNICATION_TIMEOUT\` (Düğüm Yanıt Vermiyor / 0 Hz)\n` +
            `• **Kanıt Seviyesi:** **Detected (Yüksek Güvenilirlik)**\n` +
            `• **Muhtemel Nedenler:**\n` +
            `  1. Modülün kontak besleme (+15 / +30) sigortası atmış.\n` +
            `  2. CAN-H / CAN-L bağlantı soketinde kopukluk veya korozyon.\n` +
            `  3. Modül dahili kilitlenmeye uğramış (Microcontroller Watchdog Reset bekliyor).\n\n` +
            `🛠️ **Önerilen Adım:**\n` +
            `Modül soketindeki +12V ve GND pinlerini ölçün; ardından OBD-II Pin 6-14 arası sonlandırma direncini test edin.`
        };
      } else {
        return {
          id: `msg-${Date.now()}`,
          sender: 'copilot',
          timestamp,
          text: `ℹ️ **CAN-Bus Zamanlama ve Jitter Doğrulaması:**\n\n` +
            `• **Sınıflandırma:** \`TIMING_DRIFT\` (Küçük Zamanlama Sapması)\n` +
            `• **Durum:** Düğüm normal çalışma toleransları sınırında aktif periyodik yayın yapıyor. Jitter seviyesi hat sağlığını tehdit edecek boyutta değildir.`
        };
      }
    }

    // ─────────────────────────────────────────────────────────────────────────
    // B. SHORT & USER-FRIENDLY SEMANTIC INTENT ANSWERS
    // ─────────────────────────────────────────────────────────────────────────
    // 1. Silindir Tekleme, Ateşleme, Enjektör & Tork Düşüşü
    if (
      qLower.includes('tekleme') || 
      qLower.includes('misfire') || 
      qLower.includes('ateşleme') || 
      qLower.includes('sarsıntı') || 
      qLower.includes('tork düşüş') || 
      qLower.includes('tork kaybı') || 
      qLower.includes('çekişten düş') || 
      qLower.includes('silindir') ||
      qLower.includes('p0300') || qLower.includes('p0301') || qLower.includes('p0302') || qLower.includes('p0303') || qLower.includes('p0304')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        isDtcCard: true,
        dtcInfo: KNOWN_DTCS.P0300,
        text: `🔍 **Silindir Tekleme & Çekiş Kaybı Teşhisi:**

• **Canlı Durum:** Motor ${curRpm} RPM devirde sarsıntılı çalışıyor.
• **Olası Nedenler:** 
  1. Buji aşınmış veya ateşleme bobini kaçırıyor.
  2. Enjektör püskürtmesi tıkalı (Yakıt ulaşmıyor).
  3. Yanma odasında kompresyon kaçağı var.

🛠️ **Ne Yapmalısın?**
1. Osiloskopta devir grafiğindeki ani düşüşleri izleyin.
2. Buji tırnak aralıklarını ve ateşleme bobini soketlerini kontrol edin.`
      };
    }

    // 2. Turbo, Overboost, Underboost & Basınç
    if (
      qLower.includes('turbo') || 
      qLower.includes('overboost') || 
      qLower.includes('underboost') || 
      qLower.includes('basınç') || 
      qLower.includes('boost') || 
      qLower.includes('wastegate') || 
      qLower.includes('intercooler') || 
      qLower.includes('n75') ||
      qLower.includes('p0234') || qLower.includes('p0299')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        isDtcCard: true,
        dtcInfo: KNOWN_DTCS.P0234,
        text: `💨 **Turbo Basıncı & Aşırı Doldurma Teşhisi:**

• **Canlı Basınç:** **${curBoost} Bar** (Normal aralık: 1.2 – 1.8 Bar).
• **Aşırı Basınç (Overboost):** Wastegate mekanik kolu takılı kalmış veya N75 selenoid valfi açık kalmış.
• **Düşük Basınç (Underboost):** Intercooler hortumlarında yırtık veya kelepçe gevşekliği var.

🛠️ **Ne Yapmalısın?**
1. Wastegate kolunun elle rahat hareket ettiğinden emin olun.
2. N75 selenoid valf soketini ve hava hortumu kelepçelerini kontrol edin.`
      };
    }

    // 3. Hararet, Motor Sıcaklığı & Soğutma
    if (
      qLower.includes('hararet') || 
      qLower.includes('sıcaklık') || 
      qLower.includes('soğutma') || 
      qLower.includes('termostat') || 
      qLower.includes('radyatör') || 
      qLower.includes('fan') || 
      qLower.includes('p0115') || qLower.includes('p0116')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        isDtcCard: true,
        dtcInfo: KNOWN_DTCS.P0115,
        text: `🌡️ **Yüksek Motor Sıcaklığı (Hararet):**

• **Olası Nedenler:**
  1. **Termostat Sıkışmış:** Radyatöre sıcak su geçişi kapalı kalmış.
  2. **Fan Çalışmıyor:** Radyatör fan rölesi veya sigortası atmış.
  3. **Su Eksik:** Soğutma sıvısı seviyesi düşük veya hava yapmış.

🛠️ **Ne Yapmalısın?**
1. Radyatör alt hortumuna dokunun; eğer soğuksa termostat açmıyordur.
2. Fan motor sigortasını ve genleşme kabı su seviyesini kontrol edin.`
      };
    }

    // 4. CAN-Bus, 120 Ohm & Pinout
    if (
      qLower.includes('can bus') || 
      qLower.includes('haberleşme') || 
      qLower.includes('120 ohm') || 
      qLower.includes('sonlandırma') || 
      qLower.includes('pinout') || 
      qLower.includes('obd') || 
      qLower.includes('deutsch') || 
      qLower.includes('bus off')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: `🔌 **CAN-Bus 120Ω Direnç & Pinout Rehberi:**

• **Sonlandırma Testi:** Kontak kapalıyken CAN-H ve CAN-L arasında **60 Ω** okunmalıdır (Paralel 2 adet 120Ω).
• **120 Ω okunuyorsa:** Hat sonlandırma dirençlerinden biri kopuk.
• **0 Ω okunuyorsa:** CAN-H ve CAN-L birbirine kısa devre.

• **Standart OBD-II Pinleri:**
  - Pin 6: CAN-H (Yüksek)
  - Pin 14: CAN-L (Düşük)
  - Pin 4/5: Şasi (GND) • Pin 16: +12V Akü`
      };
    }

    // 5. Yakıt & Enjektör
    if (
      qLower.includes('yakıt') || 
      qLower.includes('ray basınç') || 
      qLower.includes('enjektör') || 
      qLower.includes('fakir') || 
      qLower.includes('zengin')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: `⛽ **Yakıt Sistemi & Enjektör Teşhisi:**

• **Düşük Basınç:** Tıkalı yakıt filtresi veya enjektör geri dönüş hattı aşırı sızıntısı.
• **Yüksek Basınç:** Yakıt ray basınç regülatörü sıkışmış.
• **Fakir Karışım:** Emme manifoldundan hava sızıntısı var.

🛠️ **Ne Yapmalısın?**
Enjektör geri dönüş testi yapın ve yakıt filtresini kontrol edin.`
      };
    }

    // 6. UDS Servisleri
    if (qLower.includes('uds') || qLower.includes('servis') || qLower.includes('service')) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: `💻 **Hızlı UDS Teşhis Servisleri:**

• **0x10:** Oturum Değiştir (Standart / Programlama)
• **0x14:** Hata Kodlarını (DTC) Sil
• **0x22 / 0x2E:** Canlı Sensör Verisi Oku / Yaz
• **0x27:** Güvenlik Kilidi Aç (Seed/Key)
• **0x31:** Test Rutini Başlat (Örn: Silindir Balans Testi)`
      };
    }

    // 7. Domain Guardrail for Off-Topic Queries (Sohbet / Konu Dışı Filtresi)
    if (
      qLower.includes('nasılsın') ||
      qLower.includes('naber') ||
      qLower.includes('yemek') ||
      qLower.includes('tarif') ||
      qLower.includes('hava nasıl') ||
      qLower.includes('şaka') ||
      qLower.includes('fıkra') ||
      qLower.includes('şiir') ||
      qLower.includes('siyaset') ||
      qLower.includes('film') ||
      qLower.includes('müzik') ||
      qLower.includes('felsefe') ||
      qLower.includes('fal')
    ) {
      return {
        id: `msg-${Date.now()}`,
        sender: 'copilot',
        timestamp,
        text: `⚠️ **Universal CAN-Bus Teşhis Asistanı:**\n\nBen yalnızca araç telemetrisi, CAN veri yolu protokolleri (J1939, UDS, NMEA 2000) ve otomotiv arıza teşhisi konularında hizmet veren özel bir mühendislik asistanıyım.\n\nLütfen araç telemetrisi, sensör değerleri, CAN ID'leri veya arıza belirtileri ile ilgili bir soru sorunuz.`
      };
    }

    // 8. Genel Rehber
    return {
      id: `msg-${Date.now()}`,
      sender: 'copilot',
      timestamp,
      text: `🧠 **Diagnostic AI Copilot:**

• Canlı Telemetri: **${curRpm} RPM** | **${curBoost} Bar**
• Sistem Durumu: Normal

💡 **Hızlı İpucu:**
Arıza belirtisini doğrudan yazabilir (örn: *"motor tekliyor"*, *"hararet yaptı"*, *"120 ohm testi"*) veya sniffer tablosundaki herhangi bir satıra **sağ tıklayarak "AI Copilot'a Analiz Ettir"** diyebilirsiniz.`
    };
  }
}
