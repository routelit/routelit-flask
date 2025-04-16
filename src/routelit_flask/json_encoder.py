from flask.json.provider import JSONProvider
import json


class CustomJSONProvider(JSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault("skipkeys", True)
        kwargs.setdefault("default", self._default)
        return json.dumps(obj, **kwargs)

    def _default(self, obj):
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if v is not None}
        return super()._default(obj)
