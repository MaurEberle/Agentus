from pathlib import Path

from app.common.http import client
from app.runtime.ollama_gen import RunnerGenTail


def test_unbounded_read_has_no_socket_deadline() -> None:
    with client(timeout_sec=180.0, unbounded_read=True) as http:
        assert http.timeout.read is None
        assert http.timeout.connect == 10.0


def test_runner_tail_reads_only_new_generation_lines(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_text(
        "slot print_timing: n_gen =    100, tg =  20.00 t/s, tg_3s =  20.00 t/s\n",
        encoding="utf-8",
    )
    tail = RunnerGenTail(log)
    assert tail.poll() is False
    assert tail.tokens == 0

    with log.open("a", encoding="utf-8") as handle:
        handle.write("slot print_timing: id  0 | task 511 | n_gen =    100, tg =  29.36 t/s, tg_3s =  29.66 t/s\n")
        handle.write("noise\n")
        handle.write("slot print_timing: id  0 | task 511 | n_gen =   1200, tg =  31.50 t/s, tg_3s =  32.10 t/s\n")
    assert tail.poll() is True
    assert tail.tokens == 1200
    assert tail.rate == 31.5

    with log.open("a", encoding="utf-8") as handle:
        handle.write("slot print_timing: n_gen =    400, tg =  10.00 t/s\n")
    assert tail.poll() is False
    assert tail.tokens == 1200


def test_runner_tail_keeps_a_split_line(tmp_path: Path) -> None:
    log = tmp_path / "server.log"
    log.write_bytes(b"")
    tail = RunnerGenTail(log)
    with log.open("ab") as handle:
        handle.write(b"slot print_timing: n_gen =    80")
    assert tail.poll() is False
    with log.open("ab") as handle:
        handle.write(b", tg =  24.00 t/s\n")
    assert tail.poll() is True
    assert tail.tokens == 80
    assert tail.rate == 24.0
