# Contributing

Thanks for helping make LinePulse OEE useful for real shop-floor work.

## Good First Contributions

- Add anonymized CSV examples from different manufacturing processes.
- Improve reason-code mapping and documentation.
- Add tests for edge cases such as missing timestamps, zero runtime, or partial shifts.
- Build adapters for common exports from historians, MES systems, or maintenance logs.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
python -m unittest discover -s tests
```

## Principles

- Keep the core dependency-light.
- Prefer transparent calculations over black-box scoring.
- Make every metric traceable to input rows.
- Avoid storing sensitive plant, customer, or operator data in examples.
