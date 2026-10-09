# Publishing BERA Tools

PyPI, Conda, and Windows installer releases are manually dispatched from the tagged `main` commit. Pushing a version tag does not start publishing. Windows signing is currently off by default; uncheck **Skip SignPath** to enable it for a run.

## Versioning

BERA Tools Versioning follows [PEP440](https://peps.python.org/pep-0440/): `major.minor.patch`.

| Versions | Description |
| --- | --- |
| **Major** | This is reserved for releases that introduce breaking features. |
| **Minor** | This is reserved for releases that introduce new functionality. |
| **Patch** | This is reserved for releases that only include bug fixes. |

## Packaging BERA Tools

BERA Tools is packaged for distribution on both PyPI and Anaconda. Both publishing workflows require an explicit manual run from the tagged `main` commit. Conda uses `python-igraph` for the Python bindings; the corresponding PyPI dependency is named `igraph`. Keep the Conda recipe, `environment.yml`, and `pixi.toml` consistent with this naming.

See the following workflows:

- Conda Packaging and Release: [publish_to_anaconda.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/publish_to_anaconda.yml)
- PyPI Packaging and Release: [publish_to_pypi.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/publish_to_pypi.yml)
- Windows Installer Build and Signing: [build-win-installer.yml](https://github.com/BERATool/beratools/blob/main/.github/workflows/build-win-installer.yml)

See the workflow inventory in the [Maintainer Guide](maintainer.md#actions).

### PyPI Publication

Open [Publish to PyPI](https://github.com/BERATool/beratools/actions/workflows/publish_to_pypi.yml) and select **Run workflow**. Leaving **Version tag to publish** empty builds and checks the wheel and source distribution without publishing. The distributions are attached to the run as `beratools-pypi-dry-run` when available.

For a PyPI release:

1. Merge the release changes into `main`.
2. Optionally run the workflow without a version tag for a final dry run.
3. Create and push a new `major.minor.patch` tag on that exact `main` commit.
4. Dispatch the workflow from `main` and enter the new tag in **Version tag to publish**.
5. Confirm metadata checks and version verification pass, then check the release on [PyPI](https://pypi.org/project/BERATools/).

Publishing proceeds only when the tag is the latest numeric version and points exactly to the dispatched `main` commit. A valid tag supplied from another branch, a mismatched commit, or an older tag becomes a dry run; a malformed or nonexistent tag fails validation. Runs for the same release are serialized. Keep `main` at the tagged commit until all release workflows finish. If a workflow fix changes that commit, create a new version tag.

#### PyPI Trusted Publisher

Under the existing BERATools project's **Publishing** settings on PyPI, register the GitHub publisher with owner `BERATool`, repository `beratools`, workflow filename `publish_to_pypi.yml`, and an empty environment name. The workflow does not declare a GitHub environment. Repository transfers require updating this publisher registration; changing the trigger to manual does not repair an old owner configuration.

#### Re-running a Failed PyPI Publication

If `publish_to_pypi.yml` fails before PyPI accepts any distribution files, a maintainer with write access can open the original GitHub Actions run and select **Re-run jobs -> Re-run failed jobs**. GitHub rebuilds and republishes from the same dispatched commit, Git ref, inputs, and trusted-publishing identity. Workflow runs can be rerun for up to 30 days.

Before rerunning, confirm that the version has no files on PyPI. If PyPI accepted any files before the failure, do not rerun blindly: distribution filenames are immutable and duplicate uploads fail. Inspect the release and publish a new patch version if the release is incomplete. A rerun uses the original run's workflow definition, so a defect in the workflow itself must be fixed before creating a new release tag. Recheck the latest tag before retrying; a newer tag makes an older release a dry run.

### Anaconda Publication

Open [Publish to Anaconda](https://github.com/BERATool/beratools/actions/workflows/publish_to_anaconda.yml) and select **Run workflow**. Leaving **Version tag to publish** empty runs a non-publishing build and smoke test of the selected branch. The resulting Conda package is attached to the workflow run as an artifact, including when smoke validation fails.

For an Anaconda release:

1. Merge the release changes into `main`.
2. Optionally dispatch the workflow from `main` without a version tag for a final dry run.
3. Create and push the new `major.minor.patch` tag on that exact `main` commit.
4. Dispatch the workflow from `main` again and enter the new tag in **Version tag to publish**.
5. Confirm the build and smoke test pass and the package appears on [Anaconda BERA Tools](https://anaconda.org/appliedgrg/beratools).

Pushing the tag does not trigger Anaconda publishing. Publishing proceeds only when the manually supplied tag is the latest numeric version tag and points exactly to the selected `main` commit. A valid tag supplied from another branch, a tag that does not match the selected commit, or an older tag automatically becomes a dry run; a malformed or nonexistent tag fails validation. Confirm that the version is absent from Anaconda before publishing because existing package files are never overwritten.

If `main` advances after a failed publication, fix the release issue and create a new version tag on the updated commit. The workflow will not publish an older tag from a newer `main` commit.

## Windows Installer Signing

Windows installers follow the project [Code signing policy](https://github.com/BERATool/beratools/blob/main/CODE_SIGNING_POLICY.md). **Skip SignPath** (`skip_signing`) is checked by default, so signing is off. Uncheck it to enable signing for a run. Test and release signing use the same SignPath artifact configuration so a manual test validates the artifact that will later be released.

| Trigger | Skip SignPath | Signing policy | Result |
| --- | --- | --- | --- |
| Manual dispatch with no release tag | Unchecked | `test-signing`, no approval | Test-signed Actions artifact only |
| Manual dispatch from `main` with a matching latest release tag | Unchecked | `release-signing`, one approval | Signed artifact and GitHub Release |
| Manual dispatch with no release tag | Checked | None | Unsigned Actions artifact only |
| Manual dispatch from `main` with a matching latest release tag | Checked | None | Unsigned artifact and GitHub Release |

### Manual Signing Test

Run a test after changing the installer, its build script, the signing workflow, or the SignPath artifact configuration.

1. Open [Build Windows Installer](https://github.com/BERATool/beratools/actions/workflows/build-win-installer.yml) in GitHub Actions.
2. Select **Run workflow**, choose the branch to test, leave the release tag empty, and uncheck **Skip SignPath**.
3. Wait for the `Submit installer to SignPath` step to complete using `test-signing`.
4. Confirm the run contains both `beratools-installer-unsigned` and `beratools-installer-signed` artifacts.
5. Confirm `Upload signed installer to release` was skipped.

The test certificate is self-signed, so `Get-AuthenticodeSignature` may report `UnknownError` because its root is not trusted by Windows. The workflow still requires a signer certificate and rejects an unsigned installer. Test-signed installers are for validation only and must not be distributed as releases.

### Production Release

1. Merge the release changes into `main` and ensure all release workflows are ready.
2. Create a `major.minor.patch` version tag on the current `main` commit and push the tag. Do not advance `main` until all release workflows complete.
3. Open [Build Windows Installer](https://github.com/BERATool/beratools/actions/workflows/build-win-installer.yml), select **Run workflow**, choose `main`, enter the version tag in **Version tag to release**, and uncheck **Skip SignPath**.
4. Confirm the workflow verifies that the supplied tag points exactly to the dispatched `main` commit, is the latest numeric version tag, and submits with `release-signing`.
5. Open the signing request from the SignPath email or the URL printed by the workflow.
6. An authorized SignPath approver must approve the request within the workflow's one-hour timeout.
7. Confirm the release signature status is `Valid`.
8. Confirm the signed installer was attached to the GitHub Release.

The person who creates the tag does not need to be a SignPath approver. With multiple approvers and one required approval, any listed approver can authorize the request. If the request is denied or times out, the workflow does not publish the installer. A rerun does not overwrite an installer asset that is already attached to the release.

### Explicit Unsigned Build or Release

While SignPath configuration is being updated, leave the default **Skip SignPath** selection checked when dispatching the installer workflow. This builds normally but skips SignPath submission, signature verification, and signed-artifact upload. A failed signing request never falls back to unsigned publishing automatically.

- Leave the release tag empty for an unsigned Actions artifact only.
- For a GitHub Release, dispatch from `main` with the latest numeric tag pointing exactly to that commit. The same tag validation applies even when signing is skipped.
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

For `release-signing`, require trusted-build-system verification and origin verification. Set the repository URL to `https://github.com/appliedgrg/beratools.git`, the allowed branch to `main`, and the allowed build definition to `.github/workflows/build-win-installer.yml`.

GitHub reports a tag-triggered workflow's tag name as its origin branch. Do not add version tags or wildcard patterns to the production policy's allowed branches. Release signing is dispatched from `main`, and the workflow verifies that the supplied tag resolves exactly to that `main` commit.

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

[Anaconda BERA Tools](https://anaconda.org/appliedgrg/beratools)

[PyPI BERA Tools](https://pypi.org/project/BERATools)
