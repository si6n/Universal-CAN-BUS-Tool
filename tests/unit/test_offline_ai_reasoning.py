"""Unit test suite for Offline AI Reasoning Engine, Automotive Tokenizer, and Causal Fault Tree."""


from src.engine.ai.diagnostic_copilot import (
    AiDiagnosticCopilot,
    AutomotiveTokenizer,
    CausalBayesianInferenceEngine,
)


class TestAutomotiveTokenizer:
    """Test morphological normalization, stemming, and typo-tolerant intent extraction."""

    def test_turkish_normalization(self) -> None:
        raw = "Şanzıman Yağ Seviyesi & Çekiş Düşüklüğü!"
        norm = AutomotiveTokenizer.normalize_text(raw)
        assert norm == "sanziman yag seviyesi cekis dusuklugu"

    def test_lemmatization(self) -> None:
        assert AutomotiveTokenizer.lemmatize_word("enjektorlerden") == "enjektor"
        assert AutomotiveTokenizer.lemmatize_word("bobinlerdeki") == "bobin"
        assert AutomotiveTokenizer.lemmatize_word("hararetten") == "hararet"

    def test_misfire_slang_extraction(self) -> None:
        text = "araç dip gazda fena tekliyor ve sarsıntı yapıyor"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "MISFIRE" in intents
        assert intents["MISFIRE"] > 0.4

    def test_turbo_boost_slang_extraction(self) -> None:
        text = "araç kara duman atıyor ve yokuşta bayılıyor"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "TURBO_BOOST" in intents
        assert intents["TURBO_BOOST"] > 0.4

    def test_ev_battery_terms_extraction(self) -> None:
        text = "yüksek voltaj batarya izolasyon kaçağı var turtle mode girdi"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "EV_HV_BATTERY" in intents
        assert intents["EV_HV_BATTERY"] > 0.5

    def test_j1939_heavy_duty_terms_extraction(self) -> None:
        text = "adblue def kalite uyarısı ve dpf rejenerasyon kilitlendi"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "HEAVY_DUTY_J1939" in intents
        assert intents["HEAVY_DUTY_J1939"] > 0.5

    def test_marine_n2k_terms_extraction(self) -> None:
        text = "tekne marin motorda impeller yandı deniz suyu basmıyor"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "MARINE_NMEA2000" in intents
        assert intents["MARINE_NMEA2000"] > 0.5

    def test_can_physical_layer_terms_extraction(self) -> None:
        text = "obd pin 6 ve 14 arası 120 ohm sonlandırma direnci arızası"
        intents = AutomotiveTokenizer.extract_semantic_intents(text)
        assert "CAN_PHYSICAL_LAYER" in intents
        assert intents["CAN_PHYSICAL_LAYER"] > 0.5


class TestCausalBayesianInferenceEngine:
    """Test 4-stage technician report synthesis and deterministic reasoning."""

    def test_direct_ev_dtc_p0aa6(self) -> None:
        query = "Araçta P0AA6 arızası var ne yapmalıyım?"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 25.0}
        )
        assert "P0AA6" in report
        assert "Megger" in report or "İzolasyon" in report
        assert "Aşama 1: Görsel & Mekanik Kontrol" in report
        assert "Aşama 2: Kesin Multimetre & Osiloskop Toleransları" in report
        assert "Aşama 3: UDS / J1939 Özel Teşhis Rutinleri" in report
        assert "Aşama 4: Parça Değişim & Adaptasyon Prosedürü" in report

    def test_direct_ev_dtc_p0a0b_hvil(self) -> None:
        query = "P0A0B kodu aldım"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 25.0}
        )
        assert "P0A0B" in report
        assert "HVIL" in report
        assert "MSD" in report
        assert "100 Hz" in report

    def test_direct_j1939_spn100(self) -> None:
        query = "Ağır vasıta SPN 100 hatası verdi"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 1500.0, "BoostPressure": 1.2, "CoolantTemp": 85.0}
        )
        assert "SPN100" in report
        assert "Yağ Basıncı" in report
        assert "CRITICAL_STOP" in report

    def test_direct_j1939_spn3364_def_quality(self) -> None:
        query = "SPN 3364 arızası"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 1800.0, "BoostPressure": 2.0, "CoolantTemp": 85.0}
        )
        assert "SPN3364" in report
        assert "AdBlue" in report or "DEF" in report
        assert "%32.5" in report

    def test_uds_nrc_0x22_diagnosis(self) -> None:
        query = "ECU NRC 0x22 yanıtı döndü"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 20.0}
        )
        assert "0x22" in report
        assert "conditionsNotCorrect" in report
        assert "Ignition ON, Engine OFF" in report

    def test_uds_nrc_0x33_diagnosis(self) -> None:
        query = "NRC 0x33 hatası nedir"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 20.0}
        )
        assert "0x33" in report
        assert "securityAccessDenied" in report
        assert "0x27" in report

    def test_marine_impeller_failure_reasoning(self) -> None:
        query = "Tekne motoru devirdaim yapmıyor impeller sağlam mı nasıl anlarım"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 2200.0, "BoostPressure": 0.5, "CoolantTemp": 98.0}
        )
        assert "N2K_IMPELLER" in report
        assert "Deniz Suyu" in report
        assert "1.5°C/saniye" in report

    def test_marine_mixing_elbow_overheat(self) -> None:
        query = "Marin egzoz dirseği aşırı sıcaklık mixing elbow alarmı"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 2000.0, "BoostPressure": 0.8, "CoolantTemp": 90.0}
        )
        assert "N2K_EXHAUST_ELBOW" in report
        assert "85°C" in report or "105°C" in report

    def test_can_physical_layer_termination_reasoning(self) -> None:
        query = "CAN hattında 120 ohm okuyorum sonlandırma nerede kopuk"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 20.0}
        )
        assert "CAN_TERM_60" in report
        assert "60.0 Ω" in report
        assert "Pin 6" in report
        assert "Pin 14" in report

    def test_ev_bms_cell_voltage_frame_0x1808E5F4(self) -> None:
        query = (
            "Lütfen şu CAN karesini detaylı analiz et:\n"
            "• CAN ID: 0x1808E5F4 (Ext)\n"
            "• Kanal: vcan0 | Yön: RX | DLC: 8\n"
            "• Hex Payload: 01 7A 01 7C 00 14 00 00\n"
            "Bu mesajın olası protokolünü, içerdiği fiziksel sinyalleri ve varsa aktif arıza kodunu açıkla."
        )
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[{"code": "P0A0B"}], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 25.0}
        )
        assert "0x1808E5F4" in report
        assert "Hücre Voltaj" in report or "Cell Voltage" in report
        # AI-C-001: no fabricated live measurements — without decoded BMS
        # telemetry the engine must say so instead of inventing numbers.
        assert "Canlı ölçüm yok" in report
        assert "3.78" not in report  # the old hardcoded fake voltage
        assert "P0A0B" not in report

    def test_ev_bms_cell_voltage_frame_with_real_telemetry(self) -> None:
        """AI-C-001: decoded BMS telemetry is surfaced when actually present."""
        query = "CAN ID 0x1808E5F4 nedir?"
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query,
            active_dtcs=[],
            telemetry={
                "bms_cell_voltage_min_v": 3.78,
                "bms_cell_voltage_max_v": 3.80,
            },
        )
        assert "3.780" in report or "3.78" in report
        assert "Delta V" in report
        assert "(ölçüm)" in report

    def test_physical_can_error_frame_analysis(self) -> None:
        query = (
            "Lütfen şu CAN karesini detaylı analiz et:\n"
            "• CAN ID: 0x00000000 (ERR)\n"
            "• Kanal: vcan0 | Yön: RX | DLC: 0\n"
            "• Hex Payload: 00 00 00 00\n"
            "Bu mesajın olası protokolünü ve hata türünü açıkla."
        )
        report = CausalBayesianInferenceEngine.evaluate_diagnostic_query(
            query, active_dtcs=[{"code": "P0A0B"}], telemetry={"EngineSpeed": 0.0, "BoostPressure": 0.0, "CoolantTemp": 25.0}
        )
        assert "Hata Karesi" in report or "Error Frame" in report
        assert "Bit Stuffing" in report
        assert "120Ω" in report or "60.0 Ω" in report
        assert "P0A0B" not in report

    def test_live_telemetry_copilot_fallback(self) -> None:
        copilot = AiDiagnosticCopilot()
        response = copilot.analyze_live_telemetry(
            rpm=2100.0,
            boost_bar=2.8,
            coolant_temp=92.0,
            dtc_codes=["P0234"],
            user_prompt="Turbo overboost yapıyor araç",
        )
        assert "P0234" in response
        assert "Wastegate" in response or "N75" in response
