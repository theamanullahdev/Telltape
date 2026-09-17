# Documentary Factory

This is a small Linux first toolkit for turning a written documentary script into a narrated video. It handles the repetitive parts: speech, stock footage lookup, simple maps and charts, subtitles, music, and final assembly with ffmpeg.

I made this for my own documentary workflow, not as a polished product or a platform. There is no web app, no account system, and no mysterious queue somewhere. You write the story, describe what should be on screen, then run the pipeline locally.

It works for me, but it may have rough edges, missing cases, or bugs in your setup. Please treat it as a useful starting point, not a promise that every workflow will behave nicely on the first try.

## Linux only, for now

This repository is built and tested for Linux. It expects a normal shell, Python, and ffmpeg to be available. Windows is not supported, and I would rather say that clearly than offer instructions that are almost right. WSL may work, but it has not been tested here.

## What it does

Each project lives in `projects/<slug>/`. The important human authored inputs are `script.md` and the visual notes inside it. The pipeline can then create narration, turn paragraphs into timed scenes, fetch footage, render maps or charts where needed, assemble a video, and write basic metadata.

The included shipping project is an example of the file format, not a finished video package. Downloaded clips, images, audio, cached renders, and final exports are intentionally not included. That keeps the repository light and avoids redistributing media I do not own. A tiny act of self restraint, rare on the internet.

## Setup

Install Python 3.11 or newer, ffmpeg, and the libraries needed by the renderer. On Debian or Ubuntu, the system part is roughly:

```bash
sudo apt install ffmpeg python3-venv
```

Then create a virtual environment and install the Python requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your own Pexels and Freesound API keys to `.env` if you want automatic footage and music lookup. `.env` is ignored by Git, so please keep it that way.

## A normal workflow

Create a project:

```bash
python main.py new "Why Container Ships Are So Cheap"
```

Write the narration in `projects/<slug>/script.md`. Add a nearby HTML comment beginning with `VISUAL:` before each passage to give the renderer a visual direction. Generate each stage as you go:

```bash
python main.py narrate <slug>
python main.py scenes <slug>
python main.py footage <slug>
python main.py assemble <slug>
python main.py metadata <slug>
```

Or use the resumable all in one command:

```bash
python main.py render <slug>
```

Generated work stays under `projects/<slug>/` and `output/<slug>/`. Those paths are deliberately ignored, so a render does not quietly turn into a multi gigabyte commit.

## Model choice

This toolkit can work with any capable LLM. In my experience, models with image support usually do a better job because they can inspect frames, maps, charts, and renders rather than relying only on terminal output.

I got the best results in this project from Claude Sonnet 5 and Codex GPT 5.6 Sol. Text only models are still useful for planning and smaller code tasks, but they may struggle with the full visual production loop. Nematron failed pretty badly in my tests, though contributors are welcome to improve support for it or any other model.

## Project layout

```text
main.py                  command line entry point
src/                     pipeline code
config/config.yaml       defaults and output paths
docs/PRDPublic.md        public requirements and design notes
projects/<slug>/         scripts, scene manifests, local working files
output/<slug>/           final renders and generated metadata
assets/geo/world.geojson map data used by the graphics renderer
```

## A note on media and sources

This code can call external services and can download material from them. Check the relevant provider terms, licensing requirements, and the facts in your script before publishing a video. The repository includes source metadata in the example scene manifest so the provenance is visible, but it does not include the downloaded media itself.

## Contributing

Small, focused changes are welcome. Please read [AGENTS.md](AGENTS.md) before changing the pipeline, and do not add API keys, renders, downloaded footage, or virtual environments to commits.

## License

The code is available under the Apache License 2.0. Example scripts and project data are provided as reference material. External media and provider content remain subject to their own licenses.
