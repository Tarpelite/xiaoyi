import os
import subprocess

import modal

app_name = "timecopilot.dev"
preview = os.environ.get("PREVIEW_DEPLOY", "false").lower() == "true"
if preview:
    app_name = f"preview.{app_name}"


app = modal.App(name=app_name)


@app.function(
    image=modal.Image.debian_slim()
    .add_local_dir("site", remote_path="/root/site", copy=True)
    .workdir("/root/site")
)
@modal.web_server(8000, custom_domains=[app_name])
def run():
    cmd = "python -m http.server 8000"
    subprocess.Popen(cmd, shell=True)
