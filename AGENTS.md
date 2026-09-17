# Working notes for contributors and coding agents

This is a local, command line documentary pipeline. Keep it that way unless there is a strong reason not to. The useful outcome is a dependable render, not a clever architecture diagram.

## Ground rules

Use Python and standard command line tools. Keep pipeline stages resumable and safe to run again. A stage should write only its own output and should not make unrelated network calls.

Project files belong under `projects/<slug>/`. Generated media, caches, downloaded footage, narration, and final output are local artifacts. Do not commit them. API credentials belong in `.env`, never in source code, examples, logs, or commits.

Keep visual instructions next to the script in readable prose. Scene manifests are generated data, so preserve their schema when changing the parser or renderer.

## Model guidance

This repository can be used with any capable LLM. In practice, models that can inspect images tend to do better because they can review frames, maps, charts, and finished renders instead of guessing from logs alone.

The best results so far have come from Claude Sonnet 5 and Codex GPT 5.6 Sol. Text only models can still handle planning and small code changes, but may struggle with the full production loop. Nematron was not reliable in the tests that informed this project, especially when a task needed visual judgment. That is an observation, not a ban. Contributors are very welcome to improve support for it or any other model.

## Before opening a pull request

Run the smallest relevant command or test you can. Check `git status` before committing. If a change touches configuration, make sure a fresh clone can follow the README without needing a private file.

Do not reformat unrelated files. Do not replace real workflow text with generic filler. Boring and understandable wins here.
