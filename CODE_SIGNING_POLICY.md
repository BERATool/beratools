# Code signing policy

Free code signing is provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

## Team roles

- Committers and reviewers: [AppliedGRG developers](https://github.com/orgs/appliedgrg/teams/developers)
- Approvers: [AppliedGRG administrators](https://github.com/orgs/appliedgrg/teams/admin)

## Release process

Official Windows installers are built by manually dispatching GitHub Actions from `main` with the latest numeric version tag pointing exactly to the dispatched commit. Signing is currently disabled by default: **Skip SignPath** (`skip_signing`) starts checked. Maintainers can uncheck it to enable signing for a run. When enabled, SignPath verifies the `main` build origin and requires an authorized approver to approve each `release-signing` request before a signed installer is published.

With signing enabled, manual GitHub Actions runs without a release tag use the `test-signing` policy, do not require signing approval, and do not use the release certificate. Release signing uses a separate policy that requires an authorized approver.

With **Skip SignPath** checked, the workflow skips signing and signature verification; a signing failure never enables this option automatically. Unsigned builds are retained as Actions artifacts and, when the release tag passes the same validation, attached to the GitHub Release as `beratools-installer-x.y.z-unsigned.exe`. Release notes identify the absence of an Authenticode signature. Windows may display an unknown-publisher or SmartScreen warning. Uncheck the option to resume normal signing on later runs.

Maintainers can find test-signing and release instructions in [Publishing BERA Tools](docs/files/developer/publishing.md#windows-installer-signing).

## Privacy

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.
