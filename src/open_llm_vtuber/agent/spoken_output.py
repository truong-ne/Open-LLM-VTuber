"""Keep model reasoning and machine diagnostics outside the spoken text stream."""

import re


_TAG = re.compile(r"[<\[]\s*(/?)\s*(think|thought|analysis|internal)\s*[>\]]", re.I)
_DIAGNOSTIC = re.compile(
    r'["\'](?:core|channels|competence|schema_version|arousal|pleasure|certainty|novelty|generation_epoch|turn_id)["\']\s*:',
    re.I,
)


class SpokenOutputGuard:
    """A turn-local scanner; partial tags/JSON cannot escape between chunks.

    Normal action tags and user-facing JSON are preserved. Internal blocks with
    no closing tag stay suppressed through the end of the turn. Structured
    candidates have a bounded buffer and are discarded if they exceed it.
    """

    def __init__(self):
        self.pending = ""
        self.hidden = 0
        self.structured = None
        self.depth = []
        self.quote = None
        self.escape = False

    def feed(self, text, final=False):
        self.pending += text
        output = []
        while self.pending:
            if self.structured is not None:
                char, self.pending = self.pending[0], self.pending[1:]
                if len(self.structured) < 16384:
                    self.structured += char
                if self.quote:
                    if self.escape:
                        self.escape = False
                    elif char == "\\":
                        self.escape = True
                    elif char == self.quote:
                        self.quote = None
                elif char == '"':
                    self.quote = char
                elif char in "[{":
                    self.depth.append(char)
                elif char in "]}" and self.depth:
                    self.depth.pop()
                    if not self.depth:
                        candidate = self.structured
                        if len(candidate) < 16384 and not _DIAGNOSTIC.search(candidate):
                            output.append(candidate)
                        self.structured = None
                continue
            if self.pending[0] in "<[":
                match = _TAG.match(self.pending)
                if match:
                    self.hidden = max(0, self.hidden + (-1 if match[1] else 1))
                    self.pending = self.pending[match.end() :]
                    continue
                # Wait only while a reserved tag could still be completed.
                prefix = re.sub(r"\s+", "", self.pending.lower())
                possible = any(
                    tag.startswith(prefix)
                    for name in ("think", "thought", "analysis", "internal")
                    for tag in (f"<{name}>", f"</{name}>", f"[{name}]", f"[/{name}]")
                )
                if possible:
                    if not final:
                        break
                    if len(prefix) > 1:
                        self.pending = ""
                        break
                if self.pending[0] == "[" and not self.hidden:
                    rest = self.pending[1:].lstrip()
                    if not rest and not final:
                        break
                    if rest.startswith(("{", "[")):
                        self.structured, self.depth = "[", ["["]
                        self.pending = self.pending[1:]
                        continue
            if not self.hidden and self.pending[0] == "{":
                self.structured, self.depth = "{", ["{"]
                self.pending = self.pending[1:]
                continue
            char, self.pending = self.pending[0], self.pending[1:]
            if not self.hidden:
                output.append(char)
        if final and self.structured is not None:
            if len(self.structured) < 16384 and not _DIAGNOSTIC.search(self.structured):
                output.append(self.structured)
            self.structured = None
        return "".join(output)


def spoken_text(text):
    return SpokenOutputGuard().feed(text, final=True).strip()
