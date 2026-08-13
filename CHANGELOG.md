# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1](https://github.com/fabiocicerchia/toil-audit/compare/v1.0.0...v1.0.1) (2026-08-13)


### Bug Fixes

* security and code-quality findings ([#14](https://github.com/fabiocicerchia/toil-audit/issues/14)) ([ccbdade](https://github.com/fabiocicerchia/toil-audit/commit/ccbdade1d62e08bd427372a0a7b177f68713a623))

## 1.0.0 (2026-08-06)


### Features

* **ingest:** carry repo, workflow file, branch, actor and title ([2cd23d7](https://github.com/fabiocicerchia/toil-audit/commit/2cd23d7f2f29c0cf75afc470f7affe82ddb6ce0e))
* **ingest:** read GitLab CI pipelines ([8d940e6](https://github.com/fabiocicerchia/toil-audit/commit/8d940e6523ce388ff6ecca66fd2c0962ac8e861e))
* **ingest:** read GitLab CI pipelines ([b79afda](https://github.com/fabiocicerchia/toil-audit/commit/b79afda034291c01d7b1ad307be3a0a25affa646))
* **report:** per-file attribution, monthly trend and a sanity check ([14ea5fe](https://github.com/fabiocicerchia/toil-audit/commit/14ea5fe131e384a9f02a0041bdc870cdc85b1e83))
* **signals:** count runs parked waiting for approval ([5bec0b4](https://github.com/fabiocicerchia/toil-audit/commit/5bec0b432899153b5b59ff40c221a89082eb3c60))
* **signals:** price failure triage from the timeline, not a constant ([12609b2](https://github.com/fabiocicerchia/toil-audit/commit/12609b201ae8953b89446d756b35bfd2818f5b54))


### Bug Fixes

* add the missing final newline to data/sample_runs.json ([cbea9a8](https://github.com/fabiocicerchia/toil-audit/commit/cbea9a8a092d01e2e53bd08d33e2cd1f8ed41e11))
* **ci:** install pytest even when the package has no [dev] extra ([35d79f7](https://github.com/fabiocicerchia/toil-audit/commit/35d79f7ddfcd6cdbdc555e017bdab4bf962ba73c))
* **ci:** stop security workflows failing on private repos ([#2](https://github.com/fabiocicerchia/toil-audit/issues/2)) ([52f6e99](https://github.com/fabiocicerchia/toil-audit/commit/52f6e997775c3541d3c9f116ea219676f7906ddb))
* **ingest:** cap run duration at GitHub's per-job ceiling ([0b3a424](https://github.com/fabiocicerchia/toil-audit/commit/0b3a42415af1aa63f3ed01b9532065e67ee740d6))
* **pre-commit:** stop check-yaml failing on Helm templates and multi-doc manifests ([59b8295](https://github.com/fabiocicerchia/toil-audit/commit/59b82955648cdf14ea8bb4e7bd3f6567715d7fc2))

## [Unreleased]

### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [0.1.0] - 2026-08-01

### Added
- Initial release.

[Unreleased]: https://github.com/fabiocicerchia/toil-audit/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fabiocicerchia/toil-audit/releases/tag/v0.1.0
