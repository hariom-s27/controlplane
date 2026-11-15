# Repository rulesets

GitHub rulesets decide who may change protected branches and tags. The JSON
files here are copies of those settings, kept in the repository so a reader
can see them without admin access. GitHub, not this folder, enforces them: a
file here changes nothing on its own.

| File | Applies to | Status |
|---|---|---|
| `ruleset-main.json` | branch `main` | **applied** (ruleset 27251565) |
| `ruleset-tags.json` | tags matching `refs/tags/v*` | **applied** (ruleset 27320545) |

## `ruleset-main.json` (applied)

The request body used to create ruleset 27251565 on 14 Nov 2026, byte for
byte (sha256 `4d5944998e7ba3df8aefb5a0a380efcf00254912f1badfc9d3711b756a86df25`).
GitHub's read-back adds its default `do_not_enforce_on_create: false`; all
other fields matched (checked with `gh api … GET`). On `main` it:

- requires the `ci-ok` check from GitHub Actions (integration id 15368) to pass
  before a change lands; `ci-ok` succeeds only when every CI job succeeded
  (see `.github/workflows/ci.yml`);
- blocks force-pushes (`non_fast_forward`) and deletion of the branch;
- has an empty bypass list, so the rules also apply to the repository owner.

## `ruleset-tags.json` (applied)

Applied as ruleset 27320545 (`release-tags`). GitHub's read-back (checked
with `gh api … GET`) matched `name`, `target`, `enforcement`,
`bypass_actors`, `conditions` and `rules` in this file. It also adds `id`,
`source_type`, `source`, `node_id`, `created_at`, `updated_at`,
`current_user_can_bypass` (`never`) and `_links`, which are not part of the
file. It stops release tags (`v*`, for example `v1.0-round2`) from being
moved to another commit (`update`) or deleted (`deletion`), with an empty
bypass list.

## Other repository settings

- Immutable releases are enabled.
- Private vulnerability reporting is enabled (see `SECURITY.md`).

## Checking a live ruleset against these files

With read access to the repository settings:

```
gh api repos/hariom-s27/controlplane/rulesets/27251565
gh api repos/hariom-s27/controlplane/rulesets/27320545
```

Compare `name`, `target`, `enforcement`, `bypass_actors`, `conditions` and
`rules` in the output with `ruleset-main.json` and `ruleset-tags.json`.
GitHub also returns fields such as `id`, `source`, links, timestamps and,
for the `main` ruleset, its default `do_not_enforce_on_create`, which are
not part of the submitted body.
