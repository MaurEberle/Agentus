from app.runtime.vram_est import estimate_vram_bytes, parse_vram_profile


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
