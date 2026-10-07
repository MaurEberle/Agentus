from app.runtime.vram_est import estimate_vram_bytes, kv_bytes_for_ctx, parse_vram_profile


def test_mla_glm_kv_matches_llama_log() -> None:
    payload = {
        "model_info": {
            "general.architecture": "deepseek2",
            "deepseek2.attention.head_count": 20,
            "deepseek2.attention.head_count_kv": 1,
            "deepseek2.attention.key_length": 576,
            "deepseek2.attention.key_length_mla": 256,
            "deepseek2.attention.kv_lora_rank": 512,
            "deepseek2.attention.value_length": 512,
            "deepseek2.block_count": 48,
            "deepseek2.context_length": 202752,
            "deepseek2.embedding_length": 2048,
            "deepseek2.expert_count": 64,
            "deepseek2.nextn_predict_layers": 1,
            "deepseek2.rope.dimension_count": 64,
        }
    }
    profile = parse_vram_profile(payload, 18_132_724_548)
    assert profile is not None
    assert profile.layers == 48
    assert profile.kv_bytes_per_token == 1152 * 47
    kv = profile.kv_bytes_per_token * 202752
    assert abs(kv / (1024 * 1024) - 10469.25) < 0.01
    need = estimate_vram_bytes(profile, num_ctx=202752, num_gpu_percent=100)
    assert need > 24 * 1024**3
    smaller = estimate_vram_bytes(profile, num_ctx=8192, num_gpu_percent=100)
    assert smaller < need
    assert smaller < 24 * 1024**3


def test_qwen_hybrid_full_attention_interval() -> None:
    payload = {
        "model_info": {
            "general.architecture": "qwen35",
            "qwen35.attention.head_count": 24,
            "qwen35.attention.head_count_kv": 4,
            "qwen35.attention.key_length": 256,
            "qwen35.attention.value_length": 256,
            "qwen35.block_count": 65,
            "qwen35.embedding_length": 5120,
            "qwen35.full_attention_interval": 4,
            "qwen35.nextn_predict_layers": 1,
        }
    }
    profile = parse_vram_profile(payload, 17_738_321_921)
    assert profile is not None
    assert profile.kv_bytes_per_token == 4096 * 16
    kv = profile.kv_bytes_per_token * 262144
    assert kv == 16 * 1024 * 1024 * 1024


def test_llama_gqa_kv() -> None:
    payload = {
        "model_info": {
            "general.architecture": "llama",
            "llama.attention.head_count": 32,
            "llama.attention.head_count_kv": 8,
            "llama.attention.key_length": 64,
            "llama.attention.value_length": 64,
            "llama.block_count": 16,
            "llama.embedding_length": 2048,
        }
    }
    profile = parse_vram_profile(payload, 1_321_098_329)
    assert profile is not None
    assert profile.layers == 16
    assert profile.kv_bytes_per_token == 2048 * 16
    half = estimate_vram_bytes(profile, num_ctx=8192, num_gpu_percent=50)
    full = estimate_vram_bytes(profile, num_ctx=8192, num_gpu_percent=100)
    assert 0 < half < full
    by_layer = estimate_vram_bytes(profile, num_ctx=8192, num_gpu=8)
    assert by_layer == half
    one = estimate_vram_bytes(profile, num_ctx=8192, num_gpu=1)
    assert 0 < one < by_layer


def test_parse_without_attention_still_has_weights() -> None:
    payload = {"model_info": {"general.architecture": "unknown", "unknown.block_count": 8}}
    profile = parse_vram_profile(payload, 4_000_000_000)
    assert profile is not None
    assert profile.weight_bytes == 4_000_000_000
    assert profile.kv_bytes_per_token is None
    assert profile.kv_swa_bytes_per_token is None


def test_gemma4_swa_and_per_layer_kv_heads() -> None:
    """Gemma 4 12B: 5 SWA + 1 global, n_kv 8 on SWA and 1 on global, 256 vs 512 head dim."""
    pattern = ([True] * 5 + [False]) * 8
    n_kv = ([8] * 5 + [1]) * 8
    payload = {
        "model_info": {
            "general.architecture": "gemma4",
            "gemma4.attention.head_count": 16,
            "gemma4.attention.head_count_kv": n_kv,
            "gemma4.attention.key_length": 512,
            "gemma4.attention.key_length_swa": 256,
            "gemma4.attention.sliding_window": 1024,
            "gemma4.attention.sliding_window_pattern": pattern,
            "gemma4.attention.value_length": 512,
            "gemma4.attention.value_length_swa": 256,
            "gemma4.block_count": 48,
            "gemma4.context_length": 262144,
            "gemma4.embedding_length": 3840,
        }
    }
    profile = parse_vram_profile(payload, 12_000_000_000)
    assert profile is not None
    assert profile.layers == 48
    assert profile.kv_bytes_per_token == 8 * 2048
    assert profile.kv_swa_bytes_per_token == 40 * 8192
    assert profile.swa_window == 1024
    kv_70k = kv_bytes_for_ctx(profile, 70_000)
    assert kv_70k == 16_384 * 70_000 + 327_680 * 1024
    assert kv_70k < 2 * 1024**3
    old_wrong = (512 + 512) * 16 * 2 * 48 * 70_000
    assert old_wrong > 100 * 1024**3
    a = estimate_vram_bytes(profile, num_ctx=1024, num_gpu=48)
    b = estimate_vram_bytes(profile, num_ctx=2048, num_gpu=48)
    assert b - a == 16_384 * 1024


def test_sliding_window_without_pattern_caps_every_layer() -> None:
    payload = {
        "model_info": {
            "general.architecture": "gemma2",
            "gemma2.attention.head_count": 8,
            "gemma2.attention.head_count_kv": 4,
            "gemma2.attention.key_length": 256,
            "gemma2.attention.value_length": 256,
            "gemma2.attention.sliding_window": 4096,
            "gemma2.block_count": 26,
            "gemma2.embedding_length": 2304,
        }
    }
    profile = parse_vram_profile(payload, 5_000_000_000)
    assert profile is not None
    assert profile.kv_bytes_per_token is None
    assert profile.kv_swa_bytes_per_token == 4096 * 26
    assert profile.swa_window == 4096
    short = kv_bytes_for_ctx(profile, 2048)
    full = kv_bytes_for_ctx(profile, 131072)
    assert short == 4096 * 26 * 2048
    assert full == 4096 * 26 * 4096
    assert full == kv_bytes_for_ctx(profile, 4096)


def test_kv_head_array_does_not_fall_back_to_query_heads() -> None:
    payload = {
        "model_info": {
            "general.architecture": "llama",
            "llama.attention.head_count": 32,
            "llama.attention.head_count_kv": [8, 8, 8, 8],
            "llama.attention.key_length": 64,
            "llama.attention.value_length": 64,
            "llama.block_count": 4,
            "llama.embedding_length": 2048,
        }
    }
    profile = parse_vram_profile(payload, 1_000_000_000)
    assert profile is not None
    assert profile.kv_bytes_per_token == (64 + 64) * 8 * 2 * 4
    assert profile.kv_swa_bytes_per_token is None


def test_mn_grand_full_attention_last_n_offload() -> None:
    """Dense llama GQA: 81 layers, 8 KV heads × 128, 67 on GPU at 176k."""
    payload = {
        "model_info": {
            "general.architecture": "llama",
            "llama.attention.head_count": 32,
            "llama.attention.head_count_kv": 8,
            "llama.attention.key_length": 128,
            "llama.attention.value_length": 128,
            "llama.block_count": 81,
            "llama.context_length": 1_024_000,
            "llama.embedding_length": 5120,
            "llama.feed_forward_length": 14336,
        }
    }
    size = 14_000_000_000
    profile = parse_vram_profile(payload, size)
    assert profile is not None
    assert profile.layers == 81
    assert len(profile.kv_layers) == 81
    assert profile.kv_bytes_per_token == 4096 * 81
    assert profile.kv_swa_bytes_per_token is None
    per_layer = 4096 * 176_000
    kv_on_gpu = 67 * per_layer
    zero = estimate_vram_bytes(profile, num_ctx=0, num_gpu=67)
    need = estimate_vram_bytes(profile, num_ctx=176_000, num_gpu=67)
    assert need - zero == kv_on_gpu
    weights = int(size * 67 / 81)
    overhead = int((256 * 1024 * 1024 + 81 * 2 * 1024 * 1024) * 67 / 81)
    assert need == weights + kv_on_gpu + overhead
    assert kv_on_gpu == 67 * 4096 * 176_000


def test_gemma4_last_n_offload_uses_tail_layers() -> None:
    pattern = ([True] * 5 + [False]) * 8
    n_kv = ([8] * 5 + [1]) * 8
    payload = {
        "model_info": {
            "general.architecture": "gemma4",
            "gemma4.attention.head_count": 16,
            "gemma4.attention.head_count_kv": n_kv,
            "gemma4.attention.key_length": 512,
            "gemma4.attention.key_length_swa": 256,
            "gemma4.attention.sliding_window": 1024,
            "gemma4.attention.sliding_window_pattern": pattern,
            "gemma4.attention.value_length": 512,
            "gemma4.attention.value_length_swa": 256,
            "gemma4.block_count": 48,
            "gemma4.embedding_length": 3840,
        }
    }
    profile = parse_vram_profile(payload, 12_000_000_000)
    assert profile is not None
    six = estimate_vram_bytes(profile, num_ctx=70_000, num_gpu=6)
    six_base = estimate_vram_bytes(profile, num_ctx=0, num_gpu=6)
    assert six - six_base == 2048 * 70_000 + 5 * 8192 * 1024
    seven = estimate_vram_bytes(profile, num_ctx=70_000, num_gpu=7)
    seven_base = estimate_vram_bytes(profile, num_ctx=0, num_gpu=7)
    assert seven - seven_base == 2 * 2048 * 70_000 + 5 * 8192 * 1024
    uniform_seven = int(kv_bytes_for_ctx(profile, 70_000) * 7 / 48)
    assert seven - seven_base != uniform_seven


def test_layer_types_sliding_and_full() -> None:
    payload = {
        "model_info": {
            "general.architecture": "llama4",
            "llama4.attention.head_count": 8,
            "llama4.attention.head_count_kv": 2,
            "llama4.attention.key_length": 128,
            "llama4.attention.layer_types": [
                "sliding_attention",
                "full_attention",
                "sliding_attention",
                "full_attention",
            ],
            "llama4.attention.sliding_window": 2048,
            "llama4.attention.value_length": 128,
            "llama4.block_count": 4,
            "llama4.embedding_length": 2048,
        }
    }
    profile = parse_vram_profile(payload, 1_000_000_000)
    assert profile is not None
    assert profile.kv_bytes_per_token == 2 * 1024
    assert profile.kv_swa_bytes_per_token == 2 * 1024
    assert profile.swa_window == 2048
    short = kv_bytes_for_ctx(profile, 1024)
    long = kv_bytes_for_ctx(profile, 8192)
    assert short == 2 * 1024 * 1024 + 2 * 1024 * 1024
    assert long == 2 * 1024 * 8192 + 2 * 1024 * 2048


def test_recurrent_ssm_does_not_grow_with_context() -> None:
    payload = {
        "model_info": {
            "general.architecture": "mamba",
            "mamba.attention.head_count": 0,
            "mamba.attention.head_count_kv": 0,
            "mamba.block_count": 4,
            "mamba.embedding_length": 2048,
            "mamba.ssm.conv_kernel": 4,
            "mamba.ssm.group_count": 1,
            "mamba.ssm.inner_size": 256,
            "mamba.ssm.state_size": 128,
        }
    }
    profile = parse_vram_profile(payload, 500_000_000)
    assert profile is not None
    per = ((4 - 1) * (256 + 2 * 1 * 128) + 128 * 256) * 4
    assert kv_bytes_for_ctx(profile, 1024) == per * 4
    assert kv_bytes_for_ctx(profile, 131072) == per * 4
