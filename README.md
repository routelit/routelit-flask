# RouteLit Flask Adapter

A Flask adapter for the RouteLit framework, enabling seamless integration of RouteLit's reactive UI components with Flask web applications.

## Installation

```bash
pip install routelit-flask
```

## Usage

```python
from flask import Flask
from routelit import RouteLit
from routelit_flask import RouteLitFlaskAdapter

app = Flask(__name__)
routelit_adapter = RouteLitFlaskAdapter(RouteLit(...)).configure(app)


def build_index_view(...):
  ...


@app.route("/", methods=["GET", "POST"])
def index():
    return routelit_adapter.response(build_index_view)
```

