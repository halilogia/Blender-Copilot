# Contributing

Thank you for considering a contribution to Blender Copilot. Bug reports,
focused fixes, documentation improvements, and carefully scoped features are
welcome.

## Before you start

- Search existing issues and pull requests to avoid duplicate work.
- For questions or proposed behavior changes, open a
  [Discussion](https://github.com/halilogia/Blender-Copilot/discussions) first.
- Keep changes focused and preserve the boundary between Blender's main-thread
  API and background network work. See [ARCHITECTURE.md](ARCHITECTURE.md).
- Never include API keys, private prompts, personal logs, or other credentials
  in an issue, commit, test fixture, or pull request.

## Development setup

Clone the repository and use Python 3.11 or newer for the pure-Python test
runner. The add-on itself uses Python's standard library; Blender is needed to
run its integration tests.

```bash
git clone https://github.com/halilogia/Blender-Copilot.git
cd Blender-Copilot
```

## Run tests

Run the pure-Python unit suite before submitting a change:

```bash
python tests/run_unit_tests.py
```

For changes that interact with Blender's API, also run the headless integration
suite in an environment with Blender installed:

```bash
python tests/run_all_blender_tests.py
```

The live endpoint script is a manual integration check. Run it only when you
have a local OpenAI-compatible endpoint configured; it is not a substitute for
the offline unit suite:

```bash
python tests/manual/test_live_openai_endpoint.py
```

## Open a pull request

- Explain the problem and the behavior change in plain language.
- Include focused tests for code changes and report the commands and outcomes.
- Keep Blender data access and mutations on Blender's main thread; route
  background work through the existing event bridge.
- Preserve explicit approval for risky mutations and Blender's native undo
  behavior.
- Update the README or architecture documentation when user-facing behavior or
  system boundaries change.

Pull requests are reviewed before they are merged. Please keep each one small
enough to review on its own.
