# Security policy

ControlPlane is a research prototype built for the Accenture Innovation
Challenge 2026. It is not a production service, and the public demo has no
uptime or security guarantee.

## Reporting a vulnerability

Please report security problems privately through GitHub's private
vulnerability reporting: open this repository's **Security** tab and choose
**Report a vulnerability**. Do not open a public issue for a security problem.

We read reports and reply on the report itself. We cannot promise a response
time or a fix date.

## Scope

In scope: the code in this repository, including problems found through the
public demo on Render, which runs this code (fixture mode, synthetic data, no
user accounts). Out of scope: Render's platform and other third-party services.

The receipt keys in `.env.example`, `.github/workflows/ci.yml` and the
benchmark harnesses are public test values, not secrets (README, "Where it
fails").
