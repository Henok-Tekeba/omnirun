# Security policy

OmniRun reads model metadata only and never downloads tensor payloads. Do not
include Hugging Face tokens, private model contents, or other secrets in a
public issue.

## Supported versions

Security fixes target the current `main` branch and the latest published
release.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository:

https://github.com/Henok-Tekeba/omnirun/security/advisories/new

If private reporting is unavailable, open an issue that describes the affected
area without including exploit details or credentials.

## Scope

Useful reports include token leakage, SSRF or unsafe URL handling, request-size
or timeout bypasses, cache poisoning, and dependency vulnerabilities. OmniRun
does not currently operate a paid bug bounty program.
