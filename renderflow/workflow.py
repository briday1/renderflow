"""Workflow result builder API for provider workflows."""


class Workflow:
    """Collect ordered text/table/plot results emitted by a workflow."""

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self._results = []

    def add_text(self, content):
        if isinstance(content, str):
            content = [content]
        self._results.append({"type": "text", "content": content})
        return self

    def add_table(self, title, data):
        self._results.append({"type": "table", "title": title, "data": data})
        return self

    def add_plot(self, figure):
        self._results.append({"type": "plot", "figure": figure})
        return self

    def build(self):
        return {"results": self._results}

    def clear(self):
        self._results = []
        return self
