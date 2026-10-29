# Publishing BERA Tools

PyPI, Conda, and Windows installer releases are manually dispatched using the workflow on `main`, with a release tag selecting the source to build. Older tags are supported. Pushing a version tag does not start publishing. Windows signing is currently off by default; uncheck **Skip SignPath** to enable it for a run.

## Versioning

BERA Tools Versioning follows [PEP440](https://peps.python.org/pep-0440/): `major.minor.patch`.

| Versions | Description |
| --- | --- |
| **Major** | This is reserved for releases that introduce breaking features. |
| **Minor** | This is reserved for releases that introduce new functionality. |
| **Patch** | This is reserved for releases that only include bug fixes. |

## Packaging BERA Tools

BERA Tools is packaged for distribution on both PyPI and Anaconda. Conda uses `python-igraph` for the Python bindings; the corresponding PyPI dependency is named `igraph`. Keep the Conda recipe, `environment.yml`, `pixi.toml`, and compatibility workflow consistent with this naming.

See the following workflows:

- Conda Packaging and Release: [publish_to_anaconda.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/publish_to_anaconda.yml)
- PyPI Packaging and Release: [publish_to_pypi.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/publish_to_pypi.yml)
- Windows Installer Build and Signing: [build-win-installer.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/build-win-installer.yml)

See the workflow inventory in the [Maintainer Guide](maintainer.md#actions).

### Shared Source Selection

All three publishing workflows use native `actions/checkout` to select the input tag (`refs/tags/...`) or the triggering commit, followed by inline Bash validation before building:

| Input | Source | Publication |
| --- | --- | --- |
| Empty release tag | Selected branch's commit when the run started | Actions artifacts only |
| Existing numeric tag, dispatched from `main` | Exact commit of that tag, including older tags | Enabled after build checks pass |
| Malformed or nonexistent tag, unmerged tag, or tag supplied from another branch | Validation fails before building | Disabled |

A release tag must match `major.minor.patch` and its commit must be an ancestor of, or equal to, the `main` commit that launched the run. There is no latest-tag or exact-current-commit restriction. Tags are resolved to commit SHAs before checkout. Blank inputs never switch to a tag and never publish, even if the selected commit is tagged.

The run summary records the mode, tag, source commit, and workflow commit. For an older release, the source SHA and workflow SHA will differ: the current workflow selects the source, then all application code, dependency declarations, recipes, packaging scripts, and processing tests come from the tag. Later changes to `main` do not change the selected source.

Fixes to the workflow itself can be used by starting a new manual run from updated `main` with the same tag. Fixes to tagged source or packaging files require a new tag containing those fixes. For example, `0.5.4` predates the Conda `python-igraph` recipe fix; selecting it also selects that old recipe. Existing package files and installer release assets are not overwritten.

### PyPI Publication

Open [Publish to PyPI](https://github.com/BERATool/beratools/actions/workflows/publish_to_pypi.yml) and select **Run workflow**. Leaving **Version tag to publish** empty builds and checks the wheel and source distribution without publishing. The distributions are attached to the run as `beratools-pypi-dry-run` when available.

For a PyPI release:

1. Select an existing release tag in `main`'s history, or merge release changes and create a new `major.minor.patch` tag.
2. Optionally run the workflow without a version tag to test the selected branch's current commit.
3. Confirm the version has no files on PyPI.
4. Dispatch the workflow from `main` and enter the chosen tag in **Version tag to publish**.
5. Confirm metadata checks and version verification pass, then check the release on [PyPI](https://pypi.org/project/BERATools/).

Runs for the same release are serialized. Both the wheel and source distribution must match the requested tag version. Invalid release requests fail clearly rather than becoming dry runs; only an empty tag selects dry-run mode.

#### PyPI Trusted Publisher

Under the existing BERATools project's **Publishing** settings on PyPI, register the GitHub publisher with owner `BERATool`, repository `beratools`, workflow filename `publish_to_pypi.yml`, and an empty environment name. The workflow does not declare a GitHub environment. Repository transfers require updating this publisher registration; changing the trigger to manual does not repair an old owner configuration.

#### Re-running a Failed PyPI Publication

If `publish_to_pypi.yml` fails before PyPI accepts any distribution files, a maintainer with write access can open the original GitHub Actions run and select **Re-run jobs -> Re-run failed jobs**. GitHub rebuilds and republishes from the same dispatched commit, Git ref, inputs, and trusted-publishing identity. Workflow runs can be rerun for up to 30 days.

Before rerunning, confirm that the version has no files on PyPI. If PyPI accepted any files before the failure, do not rerun blindly: distribution filenames are immutable and duplicate uploads fail. Inspect the release and publish a new patch version if the release is incomplete. A rerun uses the original run's workflow definition. To use a workflow-only fix, start a new manual run from updated `main` and supply the same tag. A newer tag or newer `main` commit does not prevent retrying an older tag in `main`'s history.

### Anaconda Publication

Open [Publish to Anaconda](https://github.com/BERATool/beratools/actions/workflows/publish_to_anaconda.yml) and select **Run workflow**. Leaving **Version tag to publish** empty runs a non-publishing build and smoke test of the selected branch. The resulting Conda package is attached to the workflow run as an artifact, including when smoke validation fails.

For an Anaconda release:

1. Select an existing release tag in `main`'s history, or merge release changes and create a new `major.minor.patch` tag.
2. Optionally dispatch the workflow without a version tag to test the selected branch's current commit.
3. Confirm the version is absent from Anaconda.
4. Dispatch the workflow from `main` and enter the chosen tag in **Version tag to publish**.
5. Confirm the build and smoke test pass and the package appears on [Anaconda BERA Tools](https://anaconda.org/beratools/beratools).

The workflow builds the tagged recipe, installs the resulting package into a separate smoke-test environment, checks its version and CLI, and runs the tagged processing integration test before uploading. The upload targets the `beratools` Anaconda account. A successful dry run uploads a GitHub Actions artifact, not an Anaconda package. Check the source summary for `release` mode and the **Upload to Anaconda.org** step for actual publication.

## Windows Installer Signing

Windows installers follow the project [Code signing policy](https://github.com/BERATool/beratools/blob/main/CODE_SIGNING_POLICY.md). **Skip SignPath** (`skip_signing`) is checked by default, so signing is off. Uncheck it to enable signing for a run. Test and release signing use the same SignPath artifact configuration so a manual test validates the artifact that will later be released.

| Trigger | Skip SignPath | Signing policy | Result |
| --- | --- | --- | --- |
| Manual dispatch with no release tag | Unchecked | `test-signing`, no approval | Test-signed Actions artifact only |
| Manual dispatch from `main` with a tag in its history | Unchecked | `release-signing`, one approval | Signed artifact and GitHub Release |
| Manual dispatch with no release tag | Checked | None | Unsigned Actions artifact only |
| Manual dispatch from `main` with a tag in its history | Checked | None | Unsigned artifact and GitHub Release |

### Manual Signing Test

Run a test after changing the installer, its build script, the signing workflow, or the SignPath artifact configuration.

1. Open [Build Windows Installer](https://github.com/BERATool/beratools/actions/workflows/build-win-installer.yml) in GitHub Actions.
2. Select **Run workflow**, choose the branch to test, leave the release tag empty, and uncheck **Skip SignPath**.
3. Wait for the `Submit installer to SignPath` step to complete using `test-signing`.
4. Confirm the run contains both `beratools-installer-unsigned` and `beratools-installer-signed` artifacts.
5. Confirm `Upload signed installer to release` was skipped.

The test certificate is self-signed, so `Get-AuthenticodeSignature` may report `UnknownError` because its root is not trusted by Windows. The workflow still requires a signer certificate and rejects an unsigned installer. Test-signed installers are for validation only and must not be distributed as releases.

### Production Release

1. Ensure the publishing workflow and SignPath configuration are ready.
2. Select an existing numeric release tag in `main`'s history, or merge release changes and create a new tag.
3. Open [Build Windows Installer](https://github.com/BERATool/beratools/actions/workflows/build-win-installer.yml), select **Run workflow**, choose `main`, enter the version tag in **Version tag to release**, and uncheck **Skip SignPath**.
4. Confirm the source summary shows the chosen tag's SHA, the installer version matches the tag, and the workflow submits with `release-signing`.
5. Open the signing request from the SignPath email or the URL printed by the workflow.
6. An authorized SignPath approver must approve the request within the workflow's one-hour timeout.
7. Confirm the release signature status is `Valid`.
8. Confirm the signed installer was attached to the GitHub Release.

The person who creates the tag does not need to be a SignPath approver. With multiple approvers and one required approval, any listed approver can authorize the request. If the request is denied or times out, the workflow does not publish the installer. A rerun does not overwrite an installer asset that is already attached to the release.

### Explicit Unsigned Build or Release

While SignPath configuration is being updated, leave the default **Skip SignPath** selection checked when dispatching the installer workflow. This builds normally but skips SignPath submission, signature verification, and signed-artifact upload. A failed signing request never falls back to unsigned publishing automatically.

- Leave the release tag empty for an unsigned Actions artifact only.
- For a GitHub Release, dispatch from `main` with an existing numeric tag in that commit's history. The same tag validation applies even when signing is skipped.
- Download `beratools-installer-x.y.z-unsigned.exe` from the `beratools-installer-unsigned` artifact or the GitHub Release. Release notes explicitly identify it as unsigned. Windows may display an unknown-publisher or SmartScreen warning.
- Uncheck **Skip SignPath** on a later run to resume signing. The signed filename is separate from the unsigned filename; existing assets are not overwritten.

### Installer Identity

Before tagging a release, update `beratools.__version__` to the same `major.minor.patch` value. The validated release tag becomes `APP_VERSION`, which supplies that version to `packaging/beratools.iss` for the installer filename, Installed Apps version, and executable product/file versions. Do not hardcode a separate version in the Inno script. Publisher, company, support, and update metadata remain stable; for signed releases the Authenticode publisher comes from the signing certificate and therefore appears as **SignPath Foundation**. Explicit unsigned builds have no Authenticode publisher and add `-unsigned` to the installer filename after building.

### SignPath Configuration

Open **Projects -> beratools -> Signing policies** in SignPath to review policy settings.

| Setting | `test-signing` | `release-signing` |
| --- | --- | --- |
| Certificate | Self-signed test certificate | Active SignPath Foundation release certificate |
| Submitter | `CI builds` | `CI builds` |
| Approval process | Disabled | Enabled; one approval required |
| Intended origin | Branch selected for the manual test | `main` only |
| Allowed build definition | `.github/workflows/build-win-installer.yml` | `.github/workflows/build-win-installer.yml` |
| Result | Actions artifact only | Approved GitHub Release |

For `release-signing`, require trusted-build-system verification and origin verification. Set the repository URL to `https://github.com/BERATool/beratools.git`, the allowed branch to `main`, and the allowed build definition to `.github/workflows/build-win-installer.yml`.

Release signing is dispatched from `main`, while the source is checked out at the validated tag. SignPath obtains origin metadata from GitHub's run context. When enabling signing after the portal update, test an older-tag build and inspect the signing request's origin alongside the recorded source SHA and workflow SHA. Verify that the connector and signing policy accept the intended tagged source; do not assume the dispatched `main` SHA is the source SHA of an older release.

Both policies use the default artifact configuration below. Only these artifact rules are shared; certificates, approval requirements, branch restrictions, and origin settings remain policy-specific.

```xml
<?xml version="1.0" encoding="utf-8" ?>
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <parameters>
    <parameter name="version" required="true" />
  </parameters>
  <zip-file>
    <pe-file path="beratools-installer-${version}.exe">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

Inno Setup pads text fields in the PE version resource. Do not add `product-name`, `product-version`, or `file-version` restrictions without confirming a supported configuration with SignPath and completing a manual signing test.

The GitHub workflow reads `SIGNPATH_API_TOKEN` and `SIGNPATH_ORGANIZATION_ID` from repository Actions secrets. Never expose secret values, organization identifiers, user email addresses, or signing-request URLs in documentation or source control.

For maintainer handoff, add replacement users as SignPath approvers and retain at least one organization administrator or project configurator. With multiple approvers and one required approval, any listed approver can approve. Require MFA, keep the `CI builds` submitter independent of personal accounts, and verify replacement access before removing a departing maintainer.

After any portal or artifact-configuration change, run the manual signing test. The message `No GitHub policy found at .signpath/policies/...` is informational when no repository policy file is configured; open the signing request in SignPath for actual processing failures. GitHub connector requests contain attestation authorization data and cannot be promoted with SignPath's resubmit API.

## Releases

[Anaconda BERA Tools](https://anaconda.org/beratools/beratools)

[PyPI BERA Tools](https://pypi.org/project/BERATools)
