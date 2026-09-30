# Model report: who can drive Blender Copilot

Single runs of the standard tasks through the add-on's own agent (9router). `ok` = the agent finished and the file or film exists; calls and errors are tool calls and failed tool calls. A free model that finishes in few calls is better than a fast one that needs many.

| Model | Runs | Finished | Avg calls | Avg tool errors | Avg minutes |
|---|---|---|---|---|---|
| `ag/claude-sonnet-4-6` | 16 | 16/16 | 35 | 1.1 | 3.0 |
| `ag/gemini-pro-agent` | 11 | 11/11 | 32 | 7.0 | 1.8 |
| `cmc/deepseek/deepseek-v4-flash` | 16 | 16/16 | 44 | 4.1 | 5.3 |
| `openrouter/space-bunny-alpha` | 10 | 9/10 | 57 | 3.2 | 6.8 |

Finished means the agent reached the end and produced the file or film; it does not say the result is beautiful (look at the pictures in `demos/`). Numbers come from one run per task, so read them as a first impression.


## Standard tasks

| Task | `ag/claude-sonnet-4-6` | `ag/gemini-pro-agent` | `cmc/deepseek/deepseek-v4-flash` | `openrouter/space-bunny-alpha` |
|---|---|---|---|---|
| bench-model-check | not run | ok, 21 calls, 3 errors | ok, 27 calls, 3 errors | ok, 31 calls, 3 errors |
| bench-baked-bench | not run | ok, 19 calls, 4 errors | ok, 32 calls, 4 errors | ok, 19 calls, 0 errors |
| bench-terrain-forest | not run | ok, 33 calls, 16 errors | ok, 30 calls, 1 errors | ok, 141 calls, 12 errors |

Tasks: model-check = build a table with deliberate defects and fix them with `check_model`; baked-bench = wood and metal bench, `bake_material`, export; terrain-forest = terrain, house, 40 scattered trees, lamps along a path, orbit film.
