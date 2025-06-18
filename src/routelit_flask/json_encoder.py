import json
from typing import Any

from flask.json.provider import JSONProvider


class CustomJSONProvider(JSONProvider):
    def dumps(self, obj: Any, **kwargs: Any) -> str:
        kwargs.setdefault("skipkeys", True)
        kwargs.setdefault("default", self._default)
        return json.dumps(obj, **kwargs)

    def _default(self, obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if v is not None}
        return super()._default(obj)  # type: ignore[misc]
