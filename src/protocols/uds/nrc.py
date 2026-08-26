"""ISO 14229-1 Negative Response Codes (NRC) Specification and Lookups."""

from __future__ import annotations

from enum import IntEnum


class UdsNrc(IntEnum):
    """Standard ISO 14229-1 Negative Response Codes."""

    POSITIVE_RESPONSE = 0x00
    GENERAL_REJECT = 0x10
    SERVICE_NOT_SUPPORTED = 0x11
    SUB_FUNCTION_NOT_SUPPORTED = 0x12
    INCORRECT_MESSAGE_LENGTH_OR_INVALID_FORMAT = 0x13
    RESPONSE_TOO_LONG = 0x14
    BUSY_REPEAT_REQUEST = 0x21
    CONDITIONS_NOT_CORRECT = 0x22
    REQUEST_SEQUENCE_ERROR = 0x24
    NO_RESPONSE_FROM_SUBNET_COMPONENT = 0x25
    FAILURE_PREVENTS_EXECUTION_OF_REQUESTED_ACTION = 0x26
    REQUEST_OUT_OF_RANGE = 0x31
    SECURITY_ACCESS_DENIED = 0x33
    AUTHENTICATION_REQUIRED = 0x34
    INVALID_KEY = 0x35
    EXCEEDED_NUMBER_OF_ATTEMPTS = 0x36
    REQUIRED_TIME_DELAY_NOT_EXPIRED = 0x37
    SECURE_DATA_TRANSMISSION_REQUIRED = 0x38
    SECURE_DATA_TRANSMISSION_NOT_ALLOWED = 0x39
    SECURE_DATA_VERIFICATION_FAILED = 0x3A
    CERTIFICATE_VERIFICATION_FAILED_INVALID_TIME_PERIOD = 0x50
    CERTIFICATE_VERIFICATION_FAILED_INVALID_SIGNATURE = 0x51
    CERTIFICATE_VERIFICATION_FAILED_INVALID_CHAIN_OF_TRUST = 0x52
    CERTIFICATE_VERIFICATION_FAILED_INVALID_TYPE = 0x53
    CERTIFICATE_VERIFICATION_FAILED_INVALID_FORMAT = 0x54
    CERTIFICATE_VERIFICATION_FAILED_INVALID_CONTENT = 0x55
    CERTIFICATE_VERIFICATION_FAILED_INVALID_SCOPE = 0x56
    CERTIFICATE_VERIFICATION_FAILED_INVALID_CERTIFICATE = 0x57
    OWNERSHIP_VERIFICATION_FAILED = 0x58
    CHALLENGE_CALCULATION_FAILED = 0x59
    SETTING_ACCESS_RIGHTS_FAILED = 0x5A
    SESSION_KEY_CREATION_DERIVATION_FAILED = 0x5B
    CONFIGURATION_DATA_USAGE_FAILED = 0x5C
    DE_AUTHENTICATION_FAILED = 0x5D
    UPLOADING_DOWNLOAD_NOT_ACCEPTED = 0x70
    TRANSFER_DATA_SUSPENDED = 0x71
    GENERAL_PROGRAMMING_FAILURE = 0x72
    WRONG_BLOCK_SEQUENCE_COUNTER = 0x73
    REQUEST_CORRECTLY_RECEIVED_RESPONSE_PENDING = 0x78
    SUB_FUNCTION_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7E
    SERVICE_NOT_SUPPORTED_IN_ACTIVE_SESSION = 0x7F
    RPM_TOO_HIGH = 0x81
    RPM_TOO_LOW = 0x82
    ENGINE_IS_RUNNING = 0x83
    ENGINE_IS_NOT_RUNNING = 0x84
    ENGINE_RUN_TIME_TOO_LOW = 0x85
    TEMPERATURE_TOO_HIGH = 0x86
    TEMPERATURE_TOO_LOW = 0x87
    VEHICLE_SPEED_TOO_HIGH = 0x88
    VEHICLE_SPEED_TOO_LOW = 0x89
    THROTTLE_PEDAL_TOO_HIGH = 0x8A
    THROTTLE_PEDAL_TOO_LOW = 0x8B
    TRANSMISSION_RANGE_NOT_IN_NEUTRAL = 0x8C
    TRANSMISSION_RANGE_NOT_IN_GEAR = 0x8D
    BRAKE_SWITCH_NOT_CLOSED = 0x8F
    SHIFTER_LEVER_NOT_IN_PARK = 0x90
    TORQUE_CONVERTER_CLUTCH_LOCKED = 0x91
    VOLTAGE_TOO_HIGH = 0x92
    VOLTAGE_TOO_LOW = 0x93


NRC_DESCRIPTIONS: dict[int, tuple[str, str]] = {
    0x10: ("General Reject", "Genel Red"),
    0x11: ("Service Not Supported", "Servis Desteklenmiyor"),
    0x12: ("Sub-Function Not Supported", "Alt Fonksiyon Desteklenmiyor"),
    0x13: ("Incorrect Message Length Or Invalid Format", "Hatalı Mesaj Uzunluğu veya Geçersiz Format"),
    0x22: ("Conditions Not Correct", "Çalışma Koşulları Uygun Değil"),
    0x24: ("Request Sequence Error", "İstek Sıralama Hatası"),
    0x31: ("Request Out Of Range", "İstek Değeri Aralık Dışı"),
    0x33: ("Security Access Denied", "Güvenlik Erişimi Reddedildi"),
    0x35: ("Invalid Key", "Geçersiz Güvenlik Anahtarı"),
    0x36: ("Exceeded Number Of Attempts", "Maksimum Deneme Sayısı Aşıldı"),
    0x37: ("Required Time Delay Not Expired", "Gereken Güvenlik Bekleme Süresi Dolmadı"),
    0x78: ("Request Correctly Received - Response Pending", "İstek Alındı - Yanıt Bekleniyor"),
    0x7E: ("Sub-Function Not Supported In Active Session", "Aktif Oturumda Alt Fonksiyon Desteklenmiyor"),
    0x7F: ("Service Not Supported In Active Session", "Aktif Oturumda Servis Desteklenmiyor"),
    0x88: ("Vehicle Speed Too High", "Araç Hızı Çok Yüksek (Güvenlik Kilidi)"),
}
