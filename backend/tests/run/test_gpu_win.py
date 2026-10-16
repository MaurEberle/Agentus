from app.run.gpu_win import (
    GpuAdapter,
    include_adapter,
    inference_luids,
    luid_key,
    merge_util,
    merge_vram,
    order_gpu_rows,
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


def _adapter(
    vendor: int,
    dedicated: int,
    *,
    shared: int = 0,
    name: str = "gpu",
    low: int = 1,
) -> GpuAdapter:
    return GpuAdapter(
        luid=luid_key(0, low),
        name=name,
        vendor_id=vendor,
        dedicated_bytes=dedicated,
        shared_bytes=shared,
    )


def test_inference_pool_skips_integrated_when_discrete_exists() -> None:
    intel = _adapter(0x8086, 128 * 1024**2, shared=32 * 1024**3, name="Intel Graphics", low=1)
    nvidia = _adapter(0x10DE, 8 * 1024**3, name="NVIDIA RTX", low=2)
    assert inference_luids([intel, nvidia]) == {nvidia.luid}


def test_inference_pool_sums_discrete_cards_of_one_vendor() -> None:
    small = _adapter(0x10DE, 8 * 1024**3, name="RTX A", low=1)
    large = _adapter(0x10DE, 16 * 1024**3, name="RTX B", low=2)
    intel = _adapter(0x8086, 128 * 1024**2, name="Intel Graphics", low=3)
    assert inference_luids([intel, small, large]) == {small.luid, large.luid}


def test_inference_pool_picks_the_vendor_with_more_memory() -> None:
    amd = _adapter(0x1002, 4 * 1024**3, name="Radeon", low=1)
    nvidia = _adapter(0x10DE, 8 * 1024**3, name="NVIDIA", low=2)
    assert inference_luids([amd, nvidia]) == {nvidia.luid}


def test_inference_pool_uses_the_largest_integrated_adapter() -> None:
    small = _adapter(0x8086, 0, shared=2 * 1024**3, name="small", low=1)
    large = _adapter(0x8086, 0, shared=8 * 1024**3, name="large", low=2)
    assert inference_luids([small, large]) == {large.luid}


def test_order_gpu_rows_puts_inference_gpus_first() -> None:
    rows = [
        {"index": 0, "inference": False, "vram_total_bytes": 128 * 1024**2},
        {"index": 1, "inference": True, "vram_total_bytes": 8 * 1024**3},
        {"index": 2, "inference": True, "vram_total_bytes": 16 * 1024**3},
    ]
    ordered = order_gpu_rows(rows)
    assert [row["index"] for row in ordered] == [2, 1, 0]


def test_merge_vram() -> None:
    luid = luid_key(0, 0x14991)
    assert merge_vram([(luid, 123.0), (luid, 50.0)])[luid] == 123


def test_resource_snapshot_serializes_gpu() -> None:
    from app.run.models import ResourceGpu, ResourceSnapshot

    snap = ResourceSnapshot(
        ts="t",
        cpu_percent=1.0,
        cpu_cores=6,
        cpu_threads=12,
        ram_used_bytes=1,
        ram_total_bytes=2,
        gpus=[
            ResourceGpu(
                index=0,
                name="AMD Radeon RX 7900 XTX",
                util_percent=12.5,
                vendor_id=0x1002,
                inference=True,
                vram_used_bytes=1024,
                vram_total_bytes=2048,
            )
        ],
    )
    dumped = snap.model_dump(by_alias=True)
    assert dumped["gpus"][0]["name"] == "AMD Radeon RX 7900 XTX"
    assert dumped["gpus"][0]["utilPercent"] == 12.5
    assert dumped["gpus"][0]["vendorId"] == 0x1002
    assert dumped["gpus"][0]["inference"] is True
    assert dumped["cpuCores"] == 6
    assert dumped["cpuThreads"] == 12
