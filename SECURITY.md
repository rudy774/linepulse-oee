# Security Policy

## Supported Versions

LinePulse OEE is early-stage software. Security fixes are made on the `main` branch and included in the next tagged release.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| `v0.1.x` | Yes |

## Reporting a Vulnerability

Please do not open a public issue for sensitive security reports.

To report a vulnerability, open a private GitHub security advisory if available, or contact the maintainer through the GitHub profile at:

https://github.com/rudy774

Include:

- affected version or commit
- reproduction steps
- expected and actual impact
- whether real plant, customer, or operator data is involved

## Data Safety Notes

LinePulse OEE is designed to run locally on CSV exports. Contributors should not commit proprietary plant data, customer names, operator names, production rates, or other sensitive operational data. Use anonymized or synthetic examples in issues, tests, and documentation.

