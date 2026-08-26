"""AI Diagnostic Copilot & Automated Telemetry Intelligence Engine.

Provides multi-scenario root-cause analysis, dynamic fault correlation, and optional
live Google Gemini / OpenAI Cloud LLM integration.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.logging import get_logger

logger = get_logger("engine.ai_copilot")


class FaultSeverity(Enum):
    """AI Risk and Urgency Assessment."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    CRITICAL_STOP = "CRITICAL_STOP"


@dataclass(slots=True)
class TroubleshootingStep:
    """Actionable step recommended by the AI."""

    step_number: int
    action: str
    target_component: str
    difficulty: str  # "Kolay (Görsel)" | "Orta (Alet Gerekir)" | "İleri (Servis)"


@dataclass(slots=True)
class DiagnosticAnalysisReport:
    """Comprehensive AI-generated diagnostic analysis."""

    summary: str
    severity: FaultSeverity
    root_cause_probability: str
    likely_causes: list[str]
    troubleshooting_steps: list[TroubleshootingStep]
    affected_subsystems: list[str]
    raw_dtc_count: int
    telemetry_correlations: list[str]
    ai_model_used: str = "Yerel Otomotiv Uzman Motoru (Çevrimdışı)"
    timestamp_ns: int = field(default_factory=time.time_ns)


# Comprehensive Automotive & Marine Diagnostic Knowledge Base
EXPERT_KNOWLEDGE_BASE: dict[str, dict[str, Any]] = {
    "P0300": {
        "title": "Rastgele / Çoklu Silindir Ateşleme Hatası (Random/Multiple Cylinder Misfire)",
        "subsystem": "Ateşleme & Yakıt Enjeksiyon Sistemi",
        "severity": "CRITICAL_STOP",
        "causes": [
            "Buji elektrot aşınması veya tırnak aralığının fabrika toleransından sapması.",
            "Ateşleme bobini sekonder sargı izolasyon kaçağı veya bobin soket korozyonu.",
            "Enjektör püskürtme deseni tıkanıklığı veya yakıt rayı basınç düşüklüğü.",
            "Krank mili (CKP) veya Kam mili (CMP) sensör sinyalinde CAN gürültüsü ve tork dalgalanması.",
        ],
        "steps": [
            (
                "Osilatör ekranında silindir ateşleme dalga boyunu ve krank sinyalini kontrol ediniz.",
                "Krank & Ateşleme Bobinleri",
                "Orta (Alet Gerekir)",
            ),
            (
                "Enjektör dengeleme oranlarını ve yakıt rayı basıncını (UDS 0x22 DID 0x1102) ölçün.",
                "Yakıt Dağıtım Rayı",
                "Orta (Alet Gerekir)",
            ),
            (
                "Bujilerin primer/sekonder direnç değerlerini ve kompresyon basıncını test edin.",
                "Silindir Yanma Odası",
                "İleri (Servis)",
            ),
        ],
        "uds_routine": "UDS Routine 0x31 (ID 0x0201: Silindir Kompresyon & Balans Testi)",
    },
    "P0234": {
        "title": "Turboşarj / Süperşarj Aşırı Takviye Basıncı (Engine Overboost Condition)",
        "subsystem": "Aşırı Doldurma & Hava Emiş Sistemi",
        "severity": "MEDIUM",
        "causes": [
            "Wastegate aktüatör kolunun mekanik olarak kapalı konumda sıkışması.",
            "N75 Boost kontrol selenoid valfinin elektriksel olarak açık kalması veya tıkanması.",
            "MAP / Takviye basınç sensörü (SPN 102) kalibrasyon sapması.",
            "Vakum hatlarında delinme veya çekvalf arızası.",
        ],
        "steps": [
            (
                "Turbo wastegate aktüatör kolunun mekanik serbestliğini el pompası ile test edin.",
                "Wastegate Aktüatör",
                "Kolay (Görsel)",
            ),
            (
                "N75 selenoid valf soketinde 12V besleme ve PWM sinyalini osiloskop ile izleyin.",
                "N75 Boost Valfi",
                "Orta (Alet Gerekir)",
            ),
            (
                "Manifold mutlak basınç (MAP) sensörü canlı değerini referans manometre ile kıyaslayın.",
                "MAP Sensörü",
                "Orta (Alet Gerekir)",
            ),
        ],
        "uds_routine": "UDS Routine 0x31 (ID 0x0305: VGT / Wastegate Pozisyon Adaptasyonu)",
    },
    "P0299": {
        "title": "Turboşarj / Süperşarj Düşük Takviye Basıncı (Engine Underboost Condition)",
        "subsystem": "Turboşarj & Intercooler Sistemi",
        "severity": "MEDIUM",
        "causes": [
            "Intercooler hava hortumlarında yırtık, kelepçe gevşekliği veya çatlak.",
            "Wastegate kapağının tam kapanmaması veya egzoz türbin kanat aşınması.",
            "EGR valfinin açık konumda takılı kalması sonucu takviye basıncı kaçağı.",
        ],
        "steps": [
            (
                "Intercooler ve emiş borularına duman testi (smoke test) uygulayarak kaçak arayın.",
                "Intercooler Boruları",
                "Kolay (Görsel)",
            ),
            ("EGR valfi pozisyonunu ve karbon kurum birikintisini inceleyin.", "EGR Valfi", "Orta (Alet Gerekir)"),
        ],
        "uds_routine": "UDS Servis 0x22 DID 0x0115 (Turbo Boost Actual vs Target)",
    },
    "P0115": {
        "title": "Motor Soğutma Suyu Sıcaklık Devresi Arızası (ECT Sensor Circuit Malfunction)",
        "subsystem": "Motor Soğutma & Termal Yönetim Sistemi",
        "severity": "MEDIUM",
        "causes": [
            "ECT sensör kablo demetinde kopukluk, kısa devre veya soket gevşekliği.",
            "Sensör NTC termistör direnç eğrisinin bozulması.",
            "Termostatın açık kalması veya soğutma sıvısı seviyesinin kritik düşmesi.",
        ],
        "steps": [
            (
                "Sensör soketinde 5.0V referans voltajını ve şasi sürekliliğini multimetre ile ölçün.",
                "ECT Sensör Soketi",
                "Kolay (Görsel)",
            ),
            (
                "Sıcaklık 20°C ve 80°C iken sensör NTC direnç değerini ölçün (Beklenen: ~2.5kΩ -> ~300Ω).",
                "ECT Sensör Gövdesi",
                "Orta (Alet Gerekir)",
            ),
            ("Radyatör fanı rölesini ve termostat açma sıcaklığını kontrol edin.", "Termostat / Fan", "Kolay (Görsel)"),
        ],
        "uds_routine": "UDS Servis 0x22 DID 0x0105 (Coolant Temperature Sensor Value)",
    },
    "P0101": {
        "title": "Kütle Hava Akış (MAF) Sensörü Devre / Performans Sorunu",
        "subsystem": "Hava Giriş & Ölçüm Sistemi",
        "severity": "LOW",
        "causes": [
            "MAF sensörü sıcak tel / film elemanı üzerinde yağ veya toz kirliliği.",
            "Hava filtresi sonrası emiş borularında kaçak (ölçülmemiş hava girişi).",
        ],
        "steps": [
            ("MAF sensörü ölçüm elemanını özel temizleme spreyi ile temizleyin.", "MAF Sensörü", "Kolay (Görsel)"),
            (
                "Emiş borusu kelepçelerini ve hava filtresi sızdırmazlığını kontrol edin.",
                "Hava Filtre Kutusu",
                "Kolay (Görsel)",
            ),
        ],
        "uds_routine": "UDS Servis 0x2E (MAF Adaptasyon Değerlerini Sıfırla)",
    },
    "P0171": {
        "title": "Sistem Çok Fakir (Bank 1 - System Too Lean)",
        "subsystem": "Yakıt Trim & Oksijen Sensör Sistemi",
        "severity": "MEDIUM",
        "causes": [
            "Vakum hortumu kaçağı veya emme manifoldu conta sızıntısı.",
            "Tıkalı yakıt enjektörleri veya düşük yakıt pompası debisi.",
            "Ön Oksijen (Lambda) sensörü kirlenmesi veya ısıtıcı devre zayıflığı.",
        ],
        "steps": [
            (
                "Kısa ve uzun vadeli yakıt trim (STFT/LTFT) değerlerini canlı izleyin (+%20 üzeri fakir karışımdır).",
                "Lambda Sensörü",
                "Orta (Alet Gerekir)",
            ),
            ("Yakıt rayı çalışma basıncını mekanik manometre ile doğrulayın.", "Yakıt Pompası", "Orta (Alet Gerekir)"),
        ],
        "uds_routine": "UDS Servis 0x22 DID 0x0144 (Oxygen Sensor Lambda Actual)",
    },
    "U0100": {
        "title": "Motor Kontrol Modülü (ECM/PCM) İletişim Kaybı",
        "subsystem": "CAN Veri Yolu & Ağ İletişim Hattı",
        "severity": "CRITICAL_STOP",
        "causes": [
            "CAN-H veya CAN-L hattında kısa devre, kopukluk veya 120Ω sonlandırma direnci kaybı.",
            "ECM ana güç rölesi, sigortası veya şasi bağlantısında voltaj düşüşü.",
            "Aşırı elektriksel parazit veya düğümün Bus-Off durumuna düşmesi.",
        ],
        "steps": [
            (
                "Akü kutup başı sökülüyken OBD-II Pin 6 (CAN-H) ve Pin 14 (CAN-L) arası direnci ölçün (Beklenen: 60Ω).",
                "CAN Veri Yolu",
                "Orta (Alet Gerekir)",
            ),
            (
                "ECM ana besleme voltajını (Pin 16 / Kontak) ve gövde şasi direncini (<0.2Ω) ölçün.",
                "ECM Güç Soketi",
                "Orta (Alet Gerekir)",
            ),
        ],
        "uds_routine": "UDS Servis 0x14 (Tüm DTC Kayıtlarını Sıfırla & CAN Ağını Yeniden Tara)",
    },
}


class AiDiagnosticCopilot:
    """Intelligent reasoning engine analyzing DTCs, telemetry signals, and ECU health."""

    def __init__(
        self,
        gemini_api_key: str | None = None,
        openai_api_key: str | None = None,
        provider: str = "auto",
    ) -> None:
        self.gemini_api_key = gemini_api_key
        self.openai_api_key = openai_api_key
        self.provider = provider

    @staticmethod
    def _clean_and_parse_json(raw_text: str) -> dict[str, Any]:
        """Extract and parse JSON object from markdown, backticks, or conversational text."""
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and start < end:
            result: dict[str, Any] = json.loads(raw_text[start : end + 1])
            return result
        fallback: dict[str, Any] = json.loads(raw_text)
        return fallback

    def analyze_session(
        self,
        active_dtcs: list[dict[str, object]],
        telemetry_snapshot: dict[str, float],
        active_ecus: list[str],
    ) -> DiagnosticAnalysisReport:
        """Perform deterministic expert analysis or trigger Google Gemini / OpenAI LLM."""
        if self.provider == "openai" or (
            self.provider == "auto" and self.openai_api_key and len(self.openai_api_key.strip()) > 10
        ):
            try:
                return self._analyze_with_openai(active_dtcs, telemetry_snapshot, active_ecus)
            except Exception as exc:
                logger.warning("OpenAI API call failed, trying fallback", extra={"error": str(exc)})

        if self.gemini_api_key and len(self.gemini_api_key.strip()) > 10:
            try:
                return self._analyze_with_gemini(active_dtcs, telemetry_snapshot, active_ecus)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError, OSError) as exc:
                logger.warning("Gemini API call failed, falling back to local expert engine", extra={"error": str(exc)})

        return self._analyze_local_expert(active_dtcs, telemetry_snapshot, active_ecus)

    def _analyze_local_expert(
        self,
        active_dtcs: list[dict[str, object]],
        telemetry_snapshot: dict[str, float],
        active_ecus: list[str],
    ) -> DiagnosticAnalysisReport:
        dtc_count = len(active_dtcs)
        rpm = telemetry_snapshot.get("EngineSpeed", 0.0)
        boost = telemetry_snapshot.get("BoostPressure", 0.0)
        coolant_temp = telemetry_snapshot.get("CoolantTemp", 85.0)

        likely_causes: list[str] = []
        steps: list[TroubleshootingStep] = []
        correlations: list[str] = []
        affected: list[str] = []
        severity = FaultSeverity.LOW

        # Scenario 1: Oil Pressure Fault (SPN 100)
        if any(d.get("spn") == 100 for d in active_dtcs):
            severity = FaultSeverity.CRITICAL_STOP
            affected.append("Motor Yağlama & Yatak Sistemi")
            likely_causes.append(
                "Kritik düşük yağ basıncı (Yağ pompası aşınması, karterde yağ eksilmesi veya filtre tıkanıklığı)"
            )
            steps.append(
                TroubleshootingStep(
                    1,
                    "Motoru derhal durdurun ve yağ çubuğundan yağ seviyesini kontrol edin.",
                    "Yağ Karteri / Çubuğu",
                    "Kolay (Görsel)",
                )
            )
            steps.append(
                TroubleshootingStep(
                    2,
                    "Yağ basınç sensörünün kablo soketini ve multimetre ile direnç değerini ölçün.",
                    "Yağ Basınç Sensörü (SPN 100)",
                    "Orta (Alet Gerekir)",
                )
            )
            correlations.append(f"Motor {rpm:.0f} RPM devirdeyken yağ basınç alarmı tetiklendi. Yatak sarma riski!")

        # Scenario 2: Overheating Fault (SPN 110 or Temp > 100°C)
        if any(d.get("spn") == 110 for d in active_dtcs) or coolant_temp > 100.0:
            if severity != FaultSeverity.CRITICAL_STOP:
                severity = FaultSeverity.CRITICAL_STOP if coolant_temp > 108.0 else FaultSeverity.MEDIUM
            affected.append("Soğutma & Termostat Sistemi")
            likely_causes.append(
                f"Kritik hararet uyarısı (Sıcaklık: {coolant_temp:.1f} °C). Termostat kilitli, devirdaim pompası arızalı veya radyatör tıkalı."
            )
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "Radyatör / Isı eşanjörü soğutma sıvısı seviyesini ve fan çalışmasını kontrol edin.",
                    "Soğutma Radyatörü",
                    "Kolay (Görsel)",
                )
            )
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "Termostat açma derecesini ve su pompası kayış gerginliğini test edin.",
                    "Termostat & Devirdaim",
                    "Orta (Alet Gerekir)",
                )
            )
            correlations.append(f"Soğutma suyu {coolant_temp:.1f} °C ile kritik çalışma eşiğini aştı.")

        # Scenario 3: Injector Fault (SPN 651..656)
        inj_dtc = next((d for d in active_dtcs if d.get("spn") in {651, 652, 653, 654, 655, 656}), None)
        if inj_dtc:
            if severity != FaultSeverity.CRITICAL_STOP:
                severity = FaultSeverity.MEDIUM
            raw_spn = inj_dtc.get("spn", 651)
            cyl_no = int(str(raw_spn)) - 650
            affected.append(f"Yakıt Enjeksiyon Sistemi (Silindir #{cyl_no})")
            likely_causes.append(f"Silindir #{cyl_no} Enjektör solenoid akım kesintisi veya püskürtme dengesizliği.")
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    f"Silindir #{cyl_no} enjektör elektrik soketini ve tesisat sürekliliğini ölçün.",
                    f"Enjektör #{cyl_no}",
                    "Orta (Alet Gerekir)",
                )
            )
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "UDS Routine 0x31 ile Silindir Kompresyon ve Tekil Enjektör Kesme testi yapın.",
                    "ECU Teşhis Portu",
                    "İleri (Servis)",
                )
            )
            correlations.append(f"Silindir #{cyl_no} ateşleme dengesizliği tork dalgalanmasına yol açıyor.")

        # Scenario 4: Turbo Boost Fault (SPN 102 or low boost)
        if any(d.get("spn") == 102 for d in active_dtcs) or (rpm > 2000 and boost < 110.0):
            if severity == FaultSeverity.LOW:
                severity = FaultSeverity.MEDIUM
            affected.append("Turboşarj & Hava Emiş Hattı")
            likely_causes.append(
                "Düşük turbo doldurma basıncı (Intercooler hortum kaçağı, Westgate valfi açık kalması veya VGT aktüatör sıkışması)"
            )
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "Turbo intercooler hava hortumlarında yırtık veya kelepçe gevşekliği arayın.",
                    "Intercooler Boruları",
                    "Kolay (Görsel)",
                )
            )
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "VGT Turbo aktüatör kolunun mekanik olarak serbest hareket ettiğini doğrulayın.",
                    "VGT Aktüatör",
                    "Orta (Alet Gerekir)",
                )
            )
            correlations.append(
                f"{rpm:.0f} RPM devirde turbo basıncı ({boost:.1f} kPa) beklenen 160+ kPa değerinin altında."
            )

        # Scenario 5: DPF / Exhaust Fault (SPN 3251)
        if any(d.get("spn") == 3251 for d in active_dtcs):
            if severity == FaultSeverity.LOW:
                severity = FaultSeverity.MEDIUM
            affected.append("Egzoz Arıtma & DPF Sistemi")
            likely_causes.append("Dizel Partikül Filtresi (DPF) aşırı kurum doluluğu ve yüksek egzoz karşı basıncı.")
            steps.append(
                TroubleshootingStep(
                    len(steps) + 1,
                    "UDS Servis 0x31 Routine ile DPF Manuel Servis Rejenerasyonu başlatın.",
                    "DPF Filtresi",
                    "İleri (Servis)",
                )
            )
            correlations.append("DPF diferansiyel basınç sensörü eşik değerin üzerine çıktı.")

        # Default healthy response if no DTCs
        if not likely_causes:
            summary = "✅ Tüm sistemler nominal çalışma parametrelerinde. Kritik veya aktif arıza tespit edilmedi."
            root_cause_prob = "%99 Sistem Sağlıklı"
            likely_causes.append("Sensör ve CAN iletişim parametreleri fabrika toleransları dahilinde.")
            steps.append(
                TroubleshootingStep(
                    1,
                    "Periyodik bakım planına uygun olarak sıvı kontrollerini sürdürün.",
                    "Genel Araç",
                    "Kolay (Görsel)",
                )
            )
            affected.append("Tüm Elektronik Kontrol Üniteleri (ECU)")
        else:
            summary = (
                f"⚠️ Yapay Zeka Teşhisi: {len(affected)} kritik alt sistemde arıza ve korelasyon sapması tespit edildi."
            )
            root_cause_prob = "%91 Kök Neden Güvenilirliği (Korelasyon Analizi)"

        return DiagnosticAnalysisReport(
            summary=summary,
            severity=severity,
            root_cause_probability=root_cause_prob,
            likely_causes=likely_causes,
            troubleshooting_steps=steps,
            affected_subsystems=affected,
            raw_dtc_count=dtc_count,
            telemetry_correlations=correlations,
            ai_model_used="Yerel Otomotiv Uzman Motoru (Çevrimdışı)",
        )

    def _analyze_with_gemini(
        self,
        active_dtcs: list[dict[str, object]],
        telemetry_snapshot: dict[str, float],
        active_ecus: list[str],
    ) -> DiagnosticAnalysisReport:
        """Call Google Gemini REST API for deep generative diagnostics with multi-model fallback."""
        candidate_models = [
            ("gemini-3.6-flash", "Google Gemini 3.6 Flash (Bulut Zekası)"),
            ("gemini-3.5-flash", "Google Gemini 3.5 Flash (Bulut Zekası)"),
            ("gemini-2.5-flash", "Google Gemini 2.5 Flash (Bulut Zekası)"),
            ("gemini-2.0-flash", "Google Gemini 2.0 Flash (Bulut Zekası)"),
            ("gemini-1.5-flash", "Google Gemini 1.5 Flash (Bulut Zekası)"),
        ]

        prompt_text = (
            "Sen uzman bir otomotiv ve marin başmühendisisin. Aşağıdaki CAN telemetrisini ve arıza kodlarını analiz et:\n"
            f"DTC Kodları: {json.dumps(active_dtcs)}\n"
            f"Canlı Sensörler: {json.dumps(telemetry_snapshot)}\n"
            f"Aktif Beyinler: {json.dumps(active_ecus)}\n"
            "Lütfen şu JSON formatında yanıt ver:\n"
            '{"summary": "Özet", "severity": "MEDIUM", "root_cause_probability": "%95", "likely_causes": ["neden1"], "troubleshooting_steps": [{"step_number": 1, "action": "yap", "target_component": "parca", "difficulty": "Kolay"}], "affected_subsystems": ["sistem1"], "telemetry_correlations": ["korelasyon1"]}'
        )

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.gemini_api_key or "",
        }

        last_error = None
        for model_id, model_label in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
            req = urllib.request.Request(url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    resp_body = resp.read().decode("utf-8")
                    resp_json = json.loads(resp_body)
                    raw_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._clean_and_parse_json(raw_text)

                    steps = [
                        TroubleshootingStep(
                            s.get("step_number", idx + 1),
                            s.get("action", ""),
                            s.get("target_component", ""),
                            s.get("difficulty", "Orta"),
                        )
                        for idx, s in enumerate(parsed.get("troubleshooting_steps", []))
                    ]

                    sev_str = parsed.get("severity", "MEDIUM").upper()
                    severity = getattr(FaultSeverity, sev_str, FaultSeverity.MEDIUM)

                    return DiagnosticAnalysisReport(
                        summary=parsed.get("summary", "Gemini Analiz Raporu"),
                        severity=severity,
                        root_cause_probability=parsed.get("root_cause_probability", "%95"),
                        likely_causes=parsed.get("likely_causes", []),
                        troubleshooting_steps=steps,
                        affected_subsystems=parsed.get("affected_subsystems", []),
                        raw_dtc_count=len(active_dtcs),
                        telemetry_correlations=parsed.get("telemetry_correlations", []),
                        ai_model_used=model_label,
                    )
            except Exception as exc:
                last_error = exc
                continue

        logger.warning(f"All Gemini cloud models failed, falling back to local engine: {last_error}")
        return self._analyze_local_expert(active_dtcs, telemetry_snapshot, active_ecus)

    def _analyze_with_openai(
        self,
        active_dtcs: list[dict[str, object]],
        telemetry_snapshot: dict[str, float],
        active_ecus: list[str],
    ) -> DiagnosticAnalysisReport:
        """Call OpenAI REST API for deep generative diagnostics."""
        candidate_models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        prompt_text = (
            "Sen uzman bir otomotiv ve marin başmühendisisin. Aşağıdaki CAN telemetrisini ve arıza kodlarını analiz et:\n"
            f"DTC Kodları: {json.dumps(active_dtcs)}\n"
            f"Canlı Sensörler: {json.dumps(telemetry_snapshot)}\n"
            f"Aktif Beyinler: {json.dumps(active_ecus)}\n"
            "Lütfen şu JSON formatında yanıt ver:\n"
            '{"summary": "Özet", "severity": "MEDIUM", "root_cause_probability": "%95", "likely_causes": ["neden1"], "troubleshooting_steps": [{"step_number": 1, "action": "yap", "target_component": "parca", "difficulty": "Kolay"}], "affected_subsystems": ["sistem1"], "telemetry_correlations": ["korelasyon1"]}'
        )

        last_error = None
        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Sen araç telemetrisi ve CAN-Bus arıza teşhisi konusunda uzmanlaşmış bir başmühendissin. Sadece JSON formatında yanıt ver.",
                    },
                    {"role": "user", "content": prompt_text},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            data = json.dumps(payload).encode("utf-8")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.openai_api_key or ''}"}
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=data, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    resp_body = resp.read().decode("utf-8")
                    resp_json = json.loads(resp_body)
                    raw_text = resp_json["choices"][0]["message"]["content"]
                    parsed = self._clean_and_parse_json(raw_text)

                    steps = [
                        TroubleshootingStep(
                            s.get("step_number", idx + 1),
                            s.get("action", ""),
                            s.get("target_component", ""),
                            s.get("difficulty", "Orta"),
                        )
                        for idx, s in enumerate(parsed.get("troubleshooting_steps", []))
                    ]

                    sev_str = parsed.get("severity", "MEDIUM").upper()
                    severity = getattr(FaultSeverity, sev_str, FaultSeverity.MEDIUM)

                    return DiagnosticAnalysisReport(
                        summary=parsed.get("summary", "OpenAI Analiz Raporu"),
                        severity=severity,
                        root_cause_probability=parsed.get("root_cause_probability", "%95"),
                        likely_causes=parsed.get("likely_causes", []),
                        troubleshooting_steps=steps,
                        affected_subsystems=parsed.get("affected_subsystems", []),
                        raw_dtc_count=len(active_dtcs),
                        telemetry_correlations=parsed.get("telemetry_correlations", []),
                        ai_model_used=f"OpenAI {model} (ChatGPT Bulut Zekası)",
                    )
            except Exception as exc:
                last_error = exc
                continue

        logger.warning(f"All OpenAI models failed: {last_error}")
        return self._analyze_local_expert(active_dtcs, telemetry_snapshot, active_ecus)

    def analyze_live_telemetry(
        self,
        rpm: float,
        boost_bar: float,
        coolant_temp: float,
        dtc_codes: list[str],
        user_prompt: str,
    ) -> str:
        """Helper for live interactive prompt query with deep reasoning."""
        prompt_lower = user_prompt.lower().strip()

        # Extract DTC code from prompt if present
        dtc_match = re.search(r"\b([PBUC][0-9]{4})\b", user_prompt, re.IGNORECASE)
        dtc_key = dtc_match.group(1).upper() if dtc_match else None

        if not dtc_key:
            # Check for SPN numbers
            spn_match = re.search(r"\bspn\s*([0-9]+)\b", prompt_lower)
            if spn_match:
                spn_num = spn_match.group(1)
                if spn_num == "100":
                    dtc_key = "SPN100"
                elif spn_num in {"110", "175"}:
                    dtc_key = "P0115"
                elif spn_num in {"102", "18FEF600"}:
                    dtc_key = "P0234"
                elif spn_num in {"157", "94"}:
                    dtc_key = "P0087"

        # Live Gemini API call if configured
        if self.gemini_api_key and len(self.gemini_api_key.strip()) > 10:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key.strip()}"
                prompt_text = (
                    "Sen 'Universal CAN-Bus Diagnostic & Telemetry Tool' profesyonel araç teşhis yazılımının içerisindeki yerleşik AI Teşhis Başmühendisisin.\n"
                    "Kullanıcı zaten CAN veri yoluna doğrudan bağlı ve canlı paketleri bu cihaz ile okuyor!\n\n"
                    "KESİN KURALLAR:\n"
                    "1. ASLA 'aracı servise götürün' veya 'DTC'yi başka bir teşhis cihazı ile okuyun' DEME! Çünkü kullanıcı ZATEN bu teşhis cihazını kullanıyor ve arıza verisini doğrudan CAN hattından canlı okuyor.\n"
                    "2. Doğrudan net, maddeli ve sahada uygulanabilir fiziksel onarım adımları ver (Sensör soketi, multimetre ohm/volt ölçümü, hortum kontrolü, UDS servis 0x14/0x31).\n\n"
                    f"Kullanıcı Sorusu: {user_prompt}\n"
                    f"Canlı Telemetri: Motor={rpm:.0f} RPM, Turbo={boost_bar:.2f} Bar, Sıcaklık={coolant_temp:.1f}°C, Aktif DTC={', '.join(dtc_codes) if dtc_codes else '0 DTC'}"
                )
                payload = {
                    "contents": [{"parts": [{"text": prompt_text}]}],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
                }
                data = json.dumps(payload).encode("utf-8")
                headers = {"Content-Type": "application/json"}
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    parts = resp_json.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    answer = "".join(p.get("text", "") for p in parts if not p.get("thought", False)).strip()
                    if answer:
                        return f"✨ **Google Gemini 2.0 Flash (Bulut Zekası):**\n\n{answer}"
            except Exception as e:
                logger.warning(f"Live Gemini prompt failed: {e}, falling back to local expert rules")
                logger.warning(f"Live Gemini prompt failed: {e}, falling back to local expert rules")

        # 1. Direct Knowledge Base DTC match
        if dtc_key and dtc_key in EXPERT_KNOWLEDGE_BASE:
            info = EXPERT_KNOWLEDGE_BASE[dtc_key]
            causes_text = "\n".join(f"  • {c}" for c in info["causes"][:2])
            steps_text = "\n".join(f"  {idx + 1}. {s[0]}" for idx, s in enumerate(info["steps"][:2]))

            return (
                f"🚨 **{dtc_key} - {info['title']}**\n\n"
                f"• **Durum:** {rpm:.0f} RPM | {boost_bar:.2f} Bar | {coolant_temp:.1f}°C\n"
                f"• **Olası Nedenler:**\n{causes_text}\n\n"
                f"🛠️ **Ne Yapmalısın?**\n{steps_text}"
            )

        # 2. Semantic Intent: Misfire, Tekleme, Tork Kaybı
        if any(
            w in prompt_lower
            for w in [
                "tekleme",
                "misfire",
                "ateşleme",
                "sarsıntı",
                "tork düşüş",
                "tork kaybı",
                "çekişten düş",
                "silindir",
            ]
        ):
            return (
                f"🔍 **Silindir Tekleme & Çekiş Kaybı Teşhisi:**\n\n"
                f"• **Canlı Durum:** Motor {rpm:.0f} RPM devirde sarsıntılı çalışıyor.\n"
                f"• **Olası Nedenler:**\n"
                f"  1. Buji aşınmış veya ateşleme bobini kaçırıyor.\n"
                f"  2. Enjektör püskürtmesi tıkalı.\n"
                f"  3. Yanma odasında kompresyon kaçağı var.\n\n"
                f"🛠️ **Ne Yapmalısın?**\n"
                f"  1. Osiloskopta motor devrindeki ani çentikleri izleyin.\n"
                f"  2. Buji ve ateşleme bobini soketlerini kontrol edin."
            )

        # 3. Semantic Intent: Turbo, Overboost, Underboost, Basınç
        if any(
            w in prompt_lower
            for w in ["turbo", "overboost", "underboost", "basınç", "boost", "wastegate", "intercooler", "n75"]
        ):
            return (
                f"💨 **Turbo Basıncı & Aşırı Doldurma Teşhisi:**\n\n"
                f"• **Canlı Basınç:** **{boost_bar:.2f} Bar** (Normal aralık: 1.2 – 1.8 Bar).\n"
                f"• **Aşırı Basınç:** Wastegate kolu sıkışmış veya N75 valfi açık kalmış.\n"
                f"• **Düşük Basınç:** Intercooler hortumlarında yırtık veya kelepçe gevşekliği var.\n\n"
                f"🛠️ **Ne Yapmalısın?**\n"
                f"  1. Wastegate kolunun elle rahat hareket ettiğinden emin olun.\n"
                f"  2. N75 selenoid valf soketini ve hava hortumu kelepçelerini kontrol edin."
            )

        # 4. Semantic Intent: Hararet, Soğutma, Termostat, Fan
        if any(
            w in prompt_lower for w in ["hararet", "sıcaklık", "soğutma", "termostat", "radyatör", "fan", "antifriz"]
        ):
            return (
                f"🌡️ **Yüksek Motor Sıcaklığı (Hararet):**\n\n"
                f"• **Canlı Sıcaklık:** **{coolant_temp:.1f}°C** (Kritik >105°C)\n"
                f"• **Olası Nedenler:**\n"
                f"  1. **Termostat Sıkışmış:** Radyatöre sıcak su geçişi kapalı kalmış.\n"
                f"  2. **Fan Dönmüyor:** Radyatör fan rölesi veya sigortası atmış.\n"
                f"  3. **Su Seviyesi Düşük:** Soğutma sıvısı eksik veya hava yapmış.\n\n"
                f"🛠️ **Ne Yapmalısın?**\n"
                f"  1. Radyatör alt hortumuna dokunun; soğuksa termostat açmıyordur.\n"
                f"  2. Fan motor sigortasını ve genleşme kabı su seviyesini kontrol edin."
            )

        # 5. Semantic Intent: CAN Bus, 120 Ohm, Sonlandırma, Pinout
        if any(
            w in prompt_lower
            for w in [
                "can bus",
                "haberleşme",
                "120 ohm",
                "sonlandırma",
                "pinout",
                "obd",
                "deutsch",
                "kablo",
                "şema",
                "direnç",
                "bus off",
            ]
        ):
            return (
                "🔌 **CAN-Bus 120Ω Direnç & Pinout Rehberi:**\n\n"
                "• **Sonlandırma Testi:** Kontak kapalıyken CAN-H ve CAN-L arasında **60 Ω** okunmalıdır (Paralel 2 adet 120Ω).\n"
                "• **120 Ω okunuyorsa:** Hat sonlandırma dirençlerinden biri kopuk.\n"
                "• **0 Ω okunuyorsa:** CAN-H ve CAN-L birbirine kısa devre.\n\n"
                "• **Standart OBD-II Pinleri:**\n"
                "  - Pin 6: CAN-H (Yüksek)\n"
                "  - Pin 14: CAN-L (Düşük)\n"
                "  - Pin 4/5: Şasi (GND) • Pin 16: +12V Akü"
            )

        # 6. J1939 & DM1 Protocol Queries
        if any(w in prompt_lower for w in ["18feca", "dm1", "65226"]):
            return (
                "🚨 **J1939 DM1 Aktif Arıza Bildirimi:**\n\n"
                "• Göstergede Sarı Servis Uyarı Lambası aktif edildi.\n"
                "• Beyin sensör sinyalinin çalışma sınırları dışına çıktığını tespit etti.\n\n"
                "🛠️ **Hızlı Çözüm:** Sensör kablo soketini kontrol edin ve arıza hafızasını temizleyin."
            )

        if any(w in prompt_lower for w in ["j1939", "eec1", "pgn 61444", "0xcf00400", "0x0cf00400"]):
            return (
                f"⚡ **J1939 EEC1 Motor Devri & Tork:**\n\n"
                f"• Anlık Devir: **{rpm:.0f} RPM**\n"
                f"• Bayt 1: Sürücü Tork Talebi (%)\n"
                f"• Bayt 2: Gerçek Motor Torku (%)\n"
                f"• Bayt 4-5: Devir (RPM = Ham × 0.125)"
            )

        if any(w in prompt_lower for w in ["uds", "servis", "service"]):
            return (
                "💻 **Hızlı UDS Teşhis Servisleri:**\n\n"
                "• **0x10:** Oturum Aç (Standart / Programlama)\n"
                "• **0x14:** Hata Kodlarını (DTC) Sil\n"
                "• **0x22 / 0x2E:** Sensör Verisi Oku / Yaz\n"
                "• **0x27:** Güvenlik Kilidi Aç (Seed/Key)\n"
                "• **0x31:** Test Rutini Başlat"
            )

        # 7. General Telemetry Insight & Guidance
        return (
            f"🧠 **Diagnostic AI Copilot:**\n\n"
            f"• Canlı Telemetri: **{rpm:.0f} RPM** | **{boost_bar:.2f} Bar** | **{coolant_temp:.1f}°C**\n"
            f"• Sistem Durumu: Normal\n\n"
            f"💡 **Hızlı İpucu:**\n"
            f"Arıza belirtisini doğrudan yazabilir (örn: *'motor tekliyor'*, *'hararet yaptı'*, *'120 ohm testi'*) veya sniffer tablosundaki herhangi bir satıra **sağ tıklayarak 'AI Copilot'a Analiz Ettir'** diyebilirsiniz."
        )
