"""Scout [RE/DBC] — Ampirik doğrulama: CRITICAL-5 (DBC cache yarışları) + B-05/B-22 + katalog bütünlüğü.

Üretim kodunu gerçek thread'lerle çalıştırır; yalnızca DBC tanımları sahte/özettir.
Çalıştırma:  python repro/scout_repro.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Yarış pencerelerini zorlamak için GIL switch aralığını kıs (review repro'sundaki yöntem):
sys.setswitchinterval(1e-7)

from src.core.models.can_frame import CanFrame  # noqa: E402
from src.engine.decoder.dbc_decoder import DbcSignalDecoder  # noqa: E402

RESULTS: dict[str, str] = {}

DBC_TEXT = '''VERSION ""

NS_ :

BS_:

BU_: Engine Tester

BO_ 2364539904 EEC1: 8 Engine
 SG_ EngineSpeed : 24|16@1+ (0.125,0) [0|8031.875] "rpm" Vector__XXX

BO_ 291 Msg291: 8 Engine
 SG_ Speed291 : 0|8@1+ (1,0) [0|255] "km/h" Vector__XXX

BO_ 3 Msg3: 8 Engine
 SG_ Speed3 : 0|8@1+ (1,0) [0|255] "km/h" Vector__XXX
'''


def f01a_units_cache_keyerror() -> None:
    """F-01a: okuyucu :83-84 doldurma bloğunda, add_dbc_file clear() çekiyor → :85'te KeyError."""
    dec = DbcSignalDecoder.from_dbc_string(DBC_TEXT, max_cache_size=8)
    msg = dec.db.get_message_by_frame_id(291)
    errors: list[Exception] = []
    stop = threading.Event()
    barrier = threading.Barrier(2)

    def reader() -> None:
        barrier.wait()
        try:
            for _ in range(6000):
                dec._get_signal_metadata(msg)
        except Exception as exc:  # noqa: BLE001 - repro kasti
            errors.append(exc)

    def churner() -> None:
        # add_dbc_file :117-119'da üç cache'i de clear() eder → doldurma yarışını tetikler
        dbc_file = None
        import tempfile as tf
        with tf.NamedTemporaryFile("w", suffix=".dbc", delete=False, encoding="utf-8") as fh:
            fh.write(DBC_TEXT)
            dbc_file = fh.name
        barrier.wait()
        try:
            while not stop.is_set():
                dec.add_dbc_file(dbc_file)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=churner)
    t1.start()
    t2.start()
    t1.join()
    stop.set()
    t2.join()
    keyerrors = sum(1 for e in errors if isinstance(e, KeyError))
    RESULTS["F01a_units_keyerror"] = (
        f"KeyError: {keyerrors} adet / {len(errors)} hata" if errors else "Tekrarlanamadı (yarış penceresi dar)"
    )


def f01b_message_cache_eviction_keyerror() -> None:
    """F-01b: 4 okuyucu + 2 churner; LRU eviction, :261-263 check-then-act arasına giriyor."""
    dec = DbcSignalDecoder.from_dbc_string(DBC_TEXT, max_cache_size=3)
    errors: list[Exception] = []
    stop = threading.Event()
    barrier = threading.Barrier(6)

    def reader(aid: int) -> None:
        barrier.wait()
        try:
            for _ in range(5000):
                dec._lookup_message(aid, True)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def churner() -> None:
        barrier.wait()
        try:
            ids = list(range(0x100, 0x200))
            while not stop.is_set():
                for i in ids:
                    dec._lookup_message(i, True)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=reader, args=(aid,)) for aid in (291, 3, 0x0CF00400, 0x1CECFF00)]
    threads += [threading.Thread(target=churner) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads[:4]:
        t.join()
    stop.set()
    for t in threads[4:]:
        t.join()
    keyerrors = sum(1 for e in errors if isinstance(e, KeyError))
    runtime_errs = sum(1 for e in errors if isinstance(e, RuntimeError))
    RESULTS["F01b_message_cache_keyerror"] = (
        f"KeyError: {keyerrors}, RuntimeError: {runtime_errs} / toplam {len(errors)} hata"
        if errors else "Tekrarlanamadı"
    )


def b22_unbounded_signal_caches() -> None:
    """B-22: _signal_units_cache/_signal_defs_cache sınırsız; yalnız add_dbc_file temizler."""
    dec = DbcSignalDecoder.from_dbc_string(DBC_TEXT)
    ids = list(range(0x400, 0x800))
    for i in ids:
        dec._lookup_message(i, True)   # miss → hepsi _message_cache'e girmeye çalışır ama…
    # _message_cache LRU'lu; signal cache'ler ise yalnızca decode_frame doldurur.
    # Doğrudan ölçmek için _get_signal_metadata'yi sentetik msg_def'lerle dolduruyoruz:
    class FakeMsg:
        def __init__(self, fid: int) -> None:
            self.frame_id = fid
            self.signals = []
    for i in range(5000):
        dec._get_signal_metadata(FakeMsg(i))
    RESULTS["B22_signal_caches_unbounded"] = (
        f"5000 fake msg → units_cache={len(dec._signal_units_cache)}, defs_cache={len(dec._signal_defs_cache)}, "
        f"message_cache={len(dec._message_cache)}/{dec.max_cache_size} (signal cache'lerde sınır YOK)"
    )


def add_dbc_file_vs_decode_runtimeerror() -> None:
    """add_dbc_file canlı decode sürerken db.messages üzerinde büyüyor → RuntimeError riski."""
    big_dbc = PROJECT_ROOT / "data" / "dbc" / "heavy_duty" / "j1939_canboat.dbc"
    if not big_dbc.exists():
        RESULTS["add_dbc_vs_decode"] = "atla: j1939_canboat.dbc yok"
        return
    dec = DbcSignalDecoder.from_dbc_file(big_dbc)
    errors: list[Exception] = []
    stop = threading.Event()
    barrier = threading.Barrier(2)

    def decoder_thread() -> None:
        barrier.wait()
        try:
            # Cache'i bypass etmek için sürekli farklı ID'ler (miss → for candidate in self.db.messages)
            aid = 0x0CF00400
            while not stop.is_set():
                dec._lookup_message(aid & 0x1FFFFFFF, True)
                aid = (aid * 1664525 + 1013904223) & 0x1FFFFFFF  # pseudo-random ID
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def adder_thread() -> None:
        barrier.wait()
        try:
            for _ in range(40):
                dec.add_dbc_file(big_dbc)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            stop.set()

    t1 = threading.Thread(target=decoder_thread)
    t2 = threading.Thread(target=adder_thread)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    rt = sum(1 for e in errors if isinstance(e, RuntimeError))
    RESULTS["add_dbc_vs_decode_runtimeerror"] = (
        f"RuntimeError(list changed size): {rt}, diğer: {len(errors) - rt} / toplam {len(errors)}"
        if errors else "Bu koşuda istisna yok (pencere dar — raporun da notu)"
    )


def b06_catalog_integrity() -> None:
    """Katalog/manifest bütünlüğü + gerçek disk durumu."""
    data_dir = PROJECT_ROOT / "data" / "dbc"
    catalog = json.loads((data_dir / "catalog.json").read_text(encoding="utf-8"))

    cat_bytes = (data_dir / "catalog.json").read_bytes()
    man_bytes = (data_dir / "manifest.json").read_bytes()
    identical = cat_bytes == man_bytes
    RESULTS["catalog_manifest_identical"] = f"catalog.json == manifest.json byte-byte: {identical}"

    # relative_path'ler 'curated/...' önekli; diskte 'data/dbc/<category>/' var
    missing, present = [], []
    for cat in catalog["categories"].values():
        for f in cat["files"]:
            rel = f["relative_path"]
            # 'curated/heavy_duty/x.dbc' → data/dbc/heavy_duty/x.dbc testi
            if rel.startswith("curated/"):
                rel = rel[len("curated/"):]
            target = data_dir / rel
            (present if target.exists() else missing).append(str(rel))
    RESULTS["catalog_relative_paths"] = (
        f"manifest'te {len(present) + len(missing)} dosya; diskte mevcut: {len(present)}; "
        f"YOK: {len(missing)}"
    )
    if missing:
        RESULTS["catalog_missing_examples"] = ", ".join(missing[:5])

    # Üst-düzey toplamlar test iddiasıyla uyumlu mu?
    RESULTS["catalog_totals"] = (
        f"total_files={catalog['total_files']}, total_messages={catalog['total_messages']}, "
        f"total_signals={catalog['total_signals']} (test: >=70 / >=10000 / >=40000)"
    )

    # Dosya sayıları: files_count iddiası vs gerçek klasör
    for cat_name, cat in catalog["categories"].items():
        disk = len(list((data_dir / cat_name).glob("*.dbc")))
        RESULTS[f"count_{cat_name}"] = f"catalog files_count={cat['files_count']} / disk={disk}"


def b22_sentinel_float_skip() -> None:
    """B-22: (physical-offset)/scale float hatası → sentinel kontrolü sessizce atlanıyor."""
    dec = DbcSignalDecoder.from_dbc_string('''VERSION ""

NS_ :

BS_:

BU_: BMS

BO_ 512 BatMsg: 8 BMS
 SG_ CellV : 0|16@1+ (0.05,0) [0|3276] "V" Vector__XXX
 SG_ CellV2 : 16|16@1+ (0.125,0) [0|8031] "V" Vector__XXX
''')
    # CellV raw=0xFEFE (J1939 Not Available sentinel), scale=0.05
    frame = CanFrame.create("ch0", 512, bytes([0xFE, 0xFE, 0x00, 0x00, 0, 0, 0, 0]), is_extended=False)
    dec_msg = dec.decode_frame(frame)
    if dec_msg is None:
        RESULTS["B22_sentinel_float_skip"] = "decode None döndü — beklenmedik"
        return
    cv = dec_msg.signals["CellV"]
    # CellV2: 0xFF00 → 16-bit MSB sentinel
    frame2 = CanFrame.create("ch0", 512, bytes([0x00, 0x00, 0x00, 0xFF, 0, 0, 0, 0]), is_extended=False)
    cv2 = dec.decode_frame(frame2).signals["CellV2"]
    RESULTS["B22_sentinel_float_skip"] = (
        f"CellV(raw 0xFEFE, scale=0.05): value={cv.value}, status={cv.status.name}, is_valid={cv.is_valid}; "
        f"CellV2(raw 0xFF00, scale=0.125): status={cv2.status.name}, is_valid={cv2.is_valid}"
    )


def main() -> None:
    f01a_units_cache_keyerror()
    f01b_message_cache_eviction_keyerror()
    b22_unbounded_signal_caches()
    b22_sentinel_float_skip()
    add_dbc_file_vs_decode_runtimeerror()
    b06_catalog_integrity()

    print("=" * 72)
    print("SCOUT REPRO SONUÇLARI —", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 72)
    for k, v in RESULTS.items():
        print(f"[{k}]")
        print(f"    {v}")
        print()


if __name__ == "__main__":
    main()
