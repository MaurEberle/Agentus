from app.run.gpu_win import (
    include_adapter,
    luid_key,
    merge_util,
    merge_vram,
    parse_engtype,
    parse_luid,
)


def test_parse_luid_and_engine() -> None:
    name = r"pid_13448_luid_0x00000000_0x00014991_phys_0_eng_2_engtype_Compute 0"
    assert parse_luid(name) == luid_key(0, 0x14991)
    assert parse_engtype(name) == "Compute 0"


def test_include_known_vendors() -> None:
    assert include_adapter(0x1002, "AMD Radeon RX 7900 XTX", 24 * 1024**3) is True
    assert include_adapter(0x10DE, "NVIDIA GeForce RTX 4090", 24 * 1024**3) is True
    assert include_adapter(0x8086, "Intel Arc A770", 16 * 1024**3) is True
    assert include_adapter(0x8086, "Intel(R) UHD Graphics", 0) is True
    assert include_adapter(0x1414, "Microsoft Basic Render Driver", 0) is False


def test_merge_util_sums_processes_max_engine() -> None:
    luid = luid_key(0, 0x14991)
    rows = [
        (luid, "3D", 10.0),
        (luid, "3D", 5.0),
        (luid, "Compute 0", 40.0),
        (luid, "Copy", 90.0),
        (luid_key(0, 0x164DD), "3D", 1.0),
    ]
    merged = merge_util(rows)
    assert merged[luid] == 40.0
    assert merged[luid_key(0, 0x164DD)] == 1.0


def test_merge_vram() -> None:
    luid = luid_key(0, 0x14991)
    assert merge_vram([(luid, 123.0), (luid, 50.0)])[luid] == 123


def test_resource_snapshot_serializes_gpu() -> None:
    from app.run.models import ResourceGpu, ResourceSnapshot

    snap = ResourceSnapshot(
        ts="t",
        cpu_percent=1.0,
        ram_used_bytes=1,
        ram_total_bytes=2,
        gpus=[
            ResourceGpu(
                index=0,
                name="AMD Radeon RX 7900 XTX",
                util_percent=12.5,
                vram_used_bytes=1024,
                vram_total_bytes=2048,
            )
        ],
    )
    dumped = snap.model_dump(by_alias=True)
    assert dumped["gpus"][0]["name"] == "AMD Radeon RX 7900 XTX"
    assert dumped["gpus"][0]["utilPercent"] == 12.5
