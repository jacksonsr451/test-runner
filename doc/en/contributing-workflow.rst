.. _contributing-workflow:

Branch and pull request workflow
================================

TestRunner uses a two-stage integration model. Development changes are integrated
into ``dev`` first. The stable ``main`` branch receives changes through integration
pull requests from ``dev``.

Branch roles
------------

``main``
    Stable integration branch. Normal feature, fix, refactor, documentation,
    security, test, build, and CI branches must not target ``main`` directly.
    Changes reach ``main`` through a pull request whose source branch is ``dev``.

``dev``
    Development integration branch. Normal work branches target ``dev``. Changes
    must pass the repository's required GitHub Actions checks before they are
    merged.

Work branches
    Create a focused branch from the current ``dev`` branch. Use a descriptive
    prefix such as ``feat/``, ``fix/``, ``refactor/``, ``docs/``, ``test/``,
    ``security/``, ``build/``, or ``ci/`` according to the nature of the change.

Normal contribution flow
------------------------

The expected flow is::

    Issue or planned change
            |
            v
    work branch created from dev
            |
            v
    Pull Request: work branch -> dev
            |
            v
    required GitHub Actions check
            |
            v
    merge into dev
            |
            v
    Pull Request: dev -> main
            |
            v
    required GitHub Actions check
            |
            v
    merge into main

Do not open a normal work-branch pull request directly against ``main``. Keeping
``dev`` as the integration boundary ensures that related development changes are
validated together before promotion to the stable branch.

Creating a work branch
----------------------

Start from an up-to-date ``dev`` branch::

    git fetch origin
    git switch dev
    git pull --ff-only origin dev
    git switch -c feat/example-change

Use the prefix that best describes the change. Keep each branch focused on one
issue or one coherent unit of work whenever practical.

Pull requests into dev
----------------------

A normal pull request must use the work branch as its source and ``dev`` as its
base. The pull request should:

* explain the problem and the implemented change;
* reference the related issue when one exists;
* include or update tests when behavior changes;
* update documentation when public behavior, architecture, configuration, or
  contributor workflow changes;
* keep unrelated changes out of the diff;
* pass the required ``check`` status from GitHub Actions;
* resolve review conversations before merge.

The protected ``dev`` branch requires pull requests, linear history, resolved
review conversations, and the required ``check`` status. Force pushes and branch
deletion are blocked by the repository ruleset. The permitted merge strategies
are squash and rebase.

Promoting dev to main
---------------------

After changes have been integrated and validated in ``dev``, promotion to the
stable branch is performed with a dedicated pull request::

    dev -> main

The ``main`` ruleset requires the GitHub Actions ``check`` status and requires the
branch to be up to date before merge. Review conversations must be resolved.
Force pushes and deletion are blocked, and history remains linear. The permitted
merge strategies are squash and rebase.

Do not bypass this promotion path by opening a feature or fix branch directly
against ``main``.

Continuous integration
----------------------

The main test workflow runs for pull requests targeting both ``dev`` and ``main``.
Its matrix validates the supported environments and feeds the aggregate ``check``
job used by branch protection. A pull request is not ready to merge until the
required status checks enforced by the target branch ruleset are satisfied.

Documentation changes
---------------------

Documentation follows the same process as code. Create a ``docs/...`` branch from
``dev``, make the documentation changes, and open the pull request against
``dev``. Documentation is promoted to ``main`` with the next ``dev -> main``
integration pull request.

Emergency changes
-----------------

The default policy remains work branch -> ``dev`` -> ``main``. If an exceptional
production or security situation requires a different process, maintainers must
make that decision explicitly and preserve the repository's required checks and
review requirements rather than silently bypassing branch protection.
