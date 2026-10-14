from __future__ import annotations

from flask import Flask, jsonify, redirect, render_template, request, url_for

from .config import PROJECT_ROOT
from .controller import controller


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    controller.start()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/status")
    def api_status():
        return jsonify(controller.snapshot().__dict__)

    @app.post("/submit")
    def submit():
        text = request.form.get("text", "")
        unknown = controller.validate_text(text)
        if unknown:
            return render_template(
                "index.html",
                error=f"Unsupported characters: {', '.join(unknown)}",
                text=text,
            ), 400
        controller.submit_text(text)
        return redirect(url_for("index"))

    @app.post("/restart")
    def restart():
        controller.restart()
        return redirect(url_for("index"))

    @app.post("/position/<name>")
    def position(name: str):
        try:
            controller.submit_position(name)
        except ValueError as exc:
            return render_template("index.html", error=str(exc)), 400
        return redirect(url_for("index"))

    return app


app = create_app()
