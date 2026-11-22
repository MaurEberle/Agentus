"""How full the context window was, and signs that a prompt was cut.

Ollama does not fail when a prompt does not fit its loaded window: it drops the start
of the conversation and goes on. The model then misses earlier tool calls and their
errors. Finding out whether that happened needed a script over the log (investigation
2026-11-21). The watch keeps the largest prompt of an agent call and checks each
reported prompt size:

- drop: within one call and without compaction the transcript only grows, so a
  reported size that falls by more than 10 % (and 1000 tokens) means tokens were lost;
- edge: the estimate is at the window edge and the reported size far below it.

The estimate counts characters and is off by 20-30 % for code, so the checks are loose.
"""

from __future__ import annotations

from dataclasses import dataclass

DROP_RATIO = 0.9
DROP_MIN_TOKENS = 1000
EDGE_SHARE = 0.9
EDGE_RATIO = 0.75


@dataclass
class ContextWatch:
    # False for the orchestrator: its prompt is rebuilt from memory each decision and may shrink.
    detect_drops: bool = True
    prompt_max: int = 0
    context_max: int | None = None
    compactions: int = 0
    cuts: int = 0
    previous: int | None = None

    def compacted(self) -> None:
        """The transcript was made smaller on purpose: a smaller next prompt is expected."""
        self.compactions += 1
        self.previous = None

    def observe(self, *, reported: int | None, estimate: int | None, context_max: int | None) -> dict | None:
        """One model call. Returns the facts of a likely cut, or None."""
        if not isinstance(reported, int) or reported <= 0:
            return None
        if reported > self.prompt_max:
            self.prompt_max = reported
            self.context_max = context_max
        cut: dict | None = None
        previous = self.previous
        if (
            self.detect_drops
            and previous is not None
            and reported < previous * DROP_RATIO
            and previous - reported >= DROP_MIN_TOKENS
        ):
            cut = {"reason": "drop", "reported": reported, "expected": previous}
        elif (
            isinstance(estimate, int)
            and isinstance(context_max, int)
            and context_max > 0
            and estimate >= context_max * EDGE_SHARE
            and reported < estimate * EDGE_RATIO
        ):
            cut = {"reason": "edge", "reported": reported, "expected": estimate}
        if cut is not None:
            self.cuts += 1
            cut["contextMax"] = context_max
        self.previous = reported
        return cut

    def payload(self) -> dict:
        """For run.agent.done: the largest prompt, its window and share, compactions and cuts."""
        if not self.prompt_max:
            return {}
        body: dict = {"promptMax": self.prompt_max, "compactions": self.compactions, "contextCuts": self.cuts}
        if self.context_max:
            body["contextMax"] = self.context_max
            body["contextShare"] = round(100 * self.prompt_max / self.context_max, 1)
        return body
