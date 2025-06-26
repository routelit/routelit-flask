# routelit-flask

[![Release](https://img.shields.io/github/v/release/routelit/routelit-flask)](https://img.shields.io/github/v/release/routelit/routelit-flask)
[![Build status](https://img.shields.io/github/actions/workflow/status/routelit/routelit-flask/main.yml?branch=main)](https://github.com/routelit/routelit-flask/actions/workflows/main.yml?query=branch%3Amain)
[![Commit activity](https://img.shields.io/github/commit-activity/m/routelit/routelit-flask)](https://img.shields.io/github/commit-activity/m/routelit/routelit-flask)
[![License](https://img.shields.io/github/license/routelit/routelit-flask)](https://img.shields.io/github/license/routelit/routelit-flask)


![Routelit](https://wsrv.nl/?url=res.cloudinary.com/rolangom/image/upload/v1747976918/routelit/routelit_c2otsv.png&w=300&h=300)

A Flask adapter for the RouteLit framework, enabling seamless integration of RouteLit's reactive UI components with Flask web applications.

## Installation

```bash
pip install routelit routelit-flask
```

## Usage

```python
from flask import Flask
from routelit import RouteLit, RouteLitBuilder
from routelit_flask import RouteLitFlaskAdapter

app = Flask(__name__)
routelit = RouteLit()
routelit_adapter = RouteLitFlaskAdapter(routelit).configure(app)


def build_index_view(rl: RouteLitBuilder):
  rl.text("Hello, World!")


@app.route("/", methods=["GET", "POST"])
def index():
    return routelit_adapter.response(build_index_view)
```

Mantained by [@rolangom](https://x.com/rolangom).

---

Repository initiated with [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv).
