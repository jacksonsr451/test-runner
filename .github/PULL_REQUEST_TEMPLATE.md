<!--
Thanks for submitting a PR, your contribution is really appreciated!

BRANCH POLICY
-------------
Normal contribution PRs MUST target `dev`, not `main`.

Expected flow:
  work branch -> dev -> main

Create feature/fix/refactor/docs/test/security/build/ci branches from an up-to-date
`dev` branch and open the PR back to `dev`. The stable `main` branch receives
changes through an integration PR from `dev` after the development branch has
passed its required checks.

See the branch and pull request workflow documentation:
https://github.com/jacksonsr451/test-runner/blob/dev/doc/en/contributing-workflow.rst

Here is a quick checklist that should be present in PRs.

- [ ] This PR targets `dev` (unless this is the dedicated `dev` -> `main` integration PR).
- [ ] The branch was created from an up-to-date `dev` branch when applicable.
- [ ] The PR has a focused scope and unrelated changes are excluded.
- [ ] Include documentation when adding or changing public features, architecture, configuration, or contributor workflow.
- [ ] Include new tests or update existing tests when applicable.
- [ ] Required GitHub Actions checks pass before merge.
- [ ] Review conversations are resolved before merge.
- [X] Allow maintainers to push and squash when merging my commits. Please uncheck this if you prefer to squash the commits yourself.

If this change fixes an issue, please:

- [ ] Add text like `closes #XYZW` to the PR description and/or commits (where `XYZW` is the issue number). See the GitHub documentation for linking pull requests to issues.

> [!IMPORTANT]
> **Unsupervised agentic contributions are not accepted**. See our AI/LLM-Assisted Contributions Policy in `CONTRIBUTING.rst`.

- [ ] If AI agents were used, they are credited in `Co-authored-by` commit trailers when appropriate.

Unless your change is trivial or a small documentation fix (e.g. a typo or reword of a small section) please:

- [ ] Create a new changelog file in the `changelog` directory, with a name like `<ISSUE NUMBER>.<TYPE>.rst`. See `changelog/README.rst` for details.

  Write sentences in the **past or present tense**, examples:

  * *Improved verbose diff output with sequences.*
  * *Terminal summary statistics now use multiple colors.*

  Also make sure to end the sentence with a `.`.

- [ ] Add yourself to `AUTHORS` in alphabetical order.
-->
