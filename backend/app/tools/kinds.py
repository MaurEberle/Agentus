from typing import Literal, get_args

FirstPartyKind = Literal["http", "web_search", "datetime", "calculator"]
FIRST_PARTY_KINDS: tuple[FirstPartyKind, ...] = get_args(FirstPartyKind)
