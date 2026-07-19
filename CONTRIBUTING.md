# Contributing

Thanks for your interest in **HSR Story Auto Skipper**.

## End users

Most people should **not** build from source. Download the latest Windows build from:

https://github.com/luszechai/HSR-Story-Auto-Skipper/releases/latest

Report bugs or ask questions via [Issues](https://github.com/luszechai/HSR-Story-Auto-Skipper/issues).

## Development setup

1. Fork and clone the repository.
2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

3. To rebuild the packaged app: run `build_app.bat`.

## Pull requests

- Keep changes focused and described clearly.
- Do **not** commit `.venv/`, `dist/`, `build/`, personal `config.json`, or learned blacklist/reinforce crops.
- Match existing code style; avoid unrelated refactors.
- Test on Windows with Honkai: Star Rail in **windowed** mode when behavior changes.

## Code of conduct

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
