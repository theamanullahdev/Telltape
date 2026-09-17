# Documentary Factory, Public Product Requirements Document

## About this document

This is the public version of the project requirements document. It describes the intended workflow and technical direction, while leaving out personal notes, private project references, local paths, API credentials, and other details that do not belong in a public repository.

## Purpose

Documentary Factory is a local, Linux focused command line toolkit for making narrated documentary videos from a script. It is designed to reduce repetitive production work while keeping the story, research, and creative choices in the hands of the person making the video.

The pipeline can generate narration, build a scene manifest from a script, retrieve stock footage, render basic maps and charts, add captions and music, assemble the final video, and write metadata.

This began as a personal workflow. It is shared because parts of it may be useful to other people, but it is not a finished product and may need adjustment for another setup or style of video.

## Goals

1. Keep the workflow local, scriptable, and easy to inspect.
2. Make individual pipeline stages safe to rerun.
3. Keep generated media out of Git.
4. Support a clear path from script to final render.
5. Store enough source information to help with attribution and review.
6. Let a capable LLM help with planning and implementation without making the repository depend on one specific model.

## Non goals

1. A web editor or hosted video service.
2. Automatic publishing to video platforms.
3. Redistribution of downloaded footage, music, photographs, narration, or renders.
4. A guarantee that every external provider, operating system, or model works without changes.

## Workflow

The project begins with a written `script.md`. The script can contain nearby `VISUAL:` comments that describe what should appear on screen. Those notes become a timed `scenes.json` manifest once narration timing is available.

The production stages are:

1. Create a project directory.
2. Write and review the script.
3. Generate narration and word timing data.
4. Build the scene manifest.
5. Resolve footage and generate graphics where needed.
6. Assemble video, captions, narration, and music with ffmpeg.
7. Generate metadata, source information, and chapter markers.

Every stage records its completed state. The full render command skips stages that have already produced valid local output, which makes iteration less painful.

## Repository layout

```text
main.py                  command line entry point
src/                     pipeline implementation
config/config.yaml       shared settings
projects/<slug>/         project script and working files
output/<slug>/           generated render and metadata
assets/geo/world.geojson map data for graphics
docs/PRDPublic.md        this public requirements document
```

Downloaded files, cached intermediate work, generated audio, graphics, and final video are intentionally ignored by Git. A public clone contains code and small example manifests only.

## Technical direction

The codebase uses Python for orchestration and ffmpeg for media assembly. It uses YAML for shared configuration and JSON for project state, timing data, scene manifests, and output metadata.

The footage layer is built around provider adapters so that a project can use supported external sources without hardcoding credentials. API keys are read from local environment variables and must never be committed.

The graphics layer creates simple maps, charts, and visual cards as media assets for assembly. The renderer combines those assets with scene timing, narration, captions, and optional music.

## Model use

The workflow can be used with any capable LLM. Image capable models are generally more useful for this kind of work because they can inspect visual output as well as code and logs.

In my own testing, Claude Sonnet 5 and Codex GPT 5.6 Sol gave the best results. Text only models may still be useful for planning and narrow implementation tasks. Nematron did not work reliably for the full workflow in my tests, but contributors are welcome to improve compatibility with it or any other model.

## Privacy and licensing

The repository does not include API keys or downloaded media. Anyone using the pipeline is responsible for checking the licences, attribution requirements, provider terms, and factual claims relevant to their own work.

The code is released under Apache License 2.0. External assets remain subject to their original licences.

## Contributions

Contributions are welcome, especially fixes that make the pipeline more reliable across Linux environments, media providers, and model setups. Please read `AGENTS.md`, keep changes focused, and do not commit generated media or credentials.
