# Releasing Akceo

Pushing a version tag, such as `v0.1.0`, runs `.github/workflows/release.yml`. It tests the
package, builds it, publishes it to PyPI as `akceo`, and creates a GitHub Release whose notes are
that version's section of `CHANGELOG.md`.

## One-time setup

1. **PyPI trusted publisher.** On PyPI, add a trusted publisher for the project `akceo`. Before the
   first release the project doesn't exist yet, so add it as a *pending* publisher under your
   account's publishing settings. Use these values:

   | Field | Value |
   | --- | --- |
   | Owner | `LunarCommand` |
   | Repository | `akceo` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

   PyPI then trusts that workflow, so no API token is stored in GitHub.

2. **GitHub environment.** In the repository settings, create an environment named `pypi`. Adding
   yourself as a required reviewer is optional; it makes every publish wait for your approval.

## Release steps

1. **Bring the changelog up to date.** Every change since the last release that a user would
   notice belongs in the `Unreleased` section of `CHANGELOG.md`. Compare with
   `git log --oneline <last tag>..main`.

2. **Check the docs.** For each change in the release, search the docs for the old wording, file
   names and option descriptions, and update them: `README.md`, `docs/syntax.md`,
   `docs/how-it-works.md`, `docs/speaker-notes.md` and the `--help` text in `src/akceo/cli.py`.

3. **Set the version and date**, on a branch, in one commit:
   - `pyproject.toml`: `version = "0.2.0"`. This is the only place the version is set; `akceo
     --version` reads it from the installed package.
   - `CHANGELOG.md`: rename `## [Unreleased]` to `## [0.2.0] - YYYY-MM-DD` with the date you'll tag
     on, and add a new empty `## [Unreleased]` above it.
   - Run `uv lock`, so `uv.lock` records the new version.

4. **Review what's about to ship.** Before merging, look at the full change since the last
   release (`git diff <last tag>..HEAD`) next to the new changelog section. Then merge to `main`.

5. **Tag and push**, from the merged `main`:

   ```sh
   git checkout main && git pull
   git tag v0.2.0
   git push origin v0.2.0
   ```

   The tag must match the version in `pyproject.toml`. If the changelog date isn't today, fix it
   before tagging.

6. **The workflow does the rest:**
   - checks that the tag matches `pyproject.toml` and that `CHANGELOG.md` has a section for it,
     dated within a day of the tag
   - runs ruff, pyright and pytest
   - builds the sdist and the wheel
   - publishes both to PyPI, waiting for approval if the `pypi` environment requires it
   - creates the GitHub Release with the changelog section as its notes and the files attached

## Checking a release

- PyPI: <https://pypi.org/project/akceo/>
- GitHub: the repository's Releases page
- A clean install: `uv tool install akceo==0.2.0`, then `akceo --version` and a build of
  `examples/demo/deck.md`

## Versions

Akceo follows semantic versioning. While the version is below 1.0, a minor release (0.x.0) may
change the deck format or the command line; a patch release (0.1.x) only fixes bugs.

## Troubleshooting

**The workflow didn't start.** The tag has to match `v[0-9]*.[0-9]*.[0-9]*` and be pushed to
GitHub. A tag created only locally does nothing.

**"tag … doesn't match version …".** The tag and `pyproject.toml` disagree. Delete the tag
(`git tag -d v0.2.0 && git push origin :refs/tags/v0.2.0`), fix the version on `main`, and tag
again.

**"CHANGELOG.md has no '## [0.2.0] - YYYY-MM-DD' heading".** Step 3 was missed, or the heading
isn't exactly that form. Same fix as above.

**"the 0.2.0 heading is dated …; date it the day you tag".** The changelog date has to be the
release day, give or take one day for time zones. Fix the date on `main`, delete the tag and tag
again.

**The publish step fails.** Check that the PyPI trusted publisher's owner, repository, workflow file
and environment exactly match the values in the setup table, and that the `pypi` environment exists.

**A version was published with a mistake.** PyPI never lets a version number be used twice, even
after deleting it. Fix the mistake and release the next patch version. If needed, yank the bad one
on PyPI, which hides it from new installs without breaking pinned ones.
