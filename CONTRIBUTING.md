# Contribution guidelines

Thank you so much for contributing to the project. All contributions are
welcome. Please take a moment to review these guidelines. Following them will
ensure the contribution process is easy and effective for everyone involved.

## How to contribute to Pynab

### Reporting bugs

Please **Check [existing issues](https://github.com/nabaztag2018/pynab/issues)** to make sure the
bug was not already reported. If you are running latest release, make sure the
bug was not fixed on master branch by checking closed issues as well.

If you're unable to find an open issue addressing the problem,
[open a new one](https://github.com/nabaztag2018/pynab/issues/new). Be sure to include as much
relevant information as possible, ideally providing a reproduceable test case
demonstrating the expected behavior that is not occurring.

### New features or changes to existing features

If have new ideas but lack the skills to implement them, please discuss them
on the [community forum](https://tagtagtag.fr/forum/). Ideas that demonstrate
a strong community demand are more likely to find skilled developers willing
to implement them.

Please note that services can be added without being integrated to pynab base
project and could simply exploit the [Nabd protocol](PROTOCOL.md) and be installed separately.

If you intend to add a new feature or change an existing one, please engage
discussion first about what you are proposing by filing
[a new issue](https://github.com/nabaztag2018/pynab/issues/new) or discussing it on the
[Discussions page](https://github.com/nabaztag2018/pynab/discussions).

### Submitting patches

Please open a new GitHub pull request with the patch. Before submitting, please
read the guide below about developing. We are more likely to accept
patches for existing issues / enhancements.

### Your first code contribution

Unsure where to begin contributing to Pynab? You can start by looking at issues
tagged [`good first issue`](https://github.com/nabaztag2018/pynab/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
They have been especially selected as they seem not too difficult at first
sight.

## How to work with GitHub and Pull Requests

You can develop directly on your rabbit (Raspberry Pi) that you have of course
configured with ssh access (make sure you changed the default password). We
use editors with SFTP support.

If you haven't done so yet, fork the repository on GitHub, then add this fork
to your rabbit's repository.
```sh
cd $HOME/pynab
git remote add fork https://github.com/YOUR_GITHUB_USERNAME/pynab.git
```

To develop your code, create a local branch with a name that makes sense.
```sh
git fetch origin
git checkout -b feature-name origin/master
```

At anytime, you can run tests locally (on the rabbit) by first stopping pynab
and services. Hardware tests require root access.
```sh
sudo ./venv/bin/python manage.py stop_all
sudo ./venv/bin/pytest
sudo ./venv/bin/python manage.py start_all
```

Before committing your code, make sure the style is conforming by running pre-commit
```sh
./venv/bin/pre-commit
```

Once you are happy with the result, rebase and push it to a dedicated branch on
your own GitHub fork.
```sh
git fetch origin
git rebase origin/master
git push fork HEAD:feature-name
```

GitHub will display the URL to create a pull request, with a git message such
as:
```sh
remote:
remote: Create a pull request for 'branch-name' on GitHub by visiting:
remote:      https://github.com/user/pynab/pull/new/branch-name
remote:
```
Then create your pull request, adding relevant comments.
If your pull request is related to an open issue *XXX*, make sure your initial comment
starts with *Resolves #XXX*, so that the pull request is automatically linked to the issue.

Tests will be run through GitHub Actions, covering code style, code quality
and unit tests.

If tests fail, fix them and push to the branch, either with new commits or
by amending. Once tests pass, your request will be reviewed.

At any time, if you did commit your changes, you can go back to master with:
```sh
git fetch origin
git checkout master
bash upgrade.sh
```

The last command is required to run a full upgrade for any changes in localized
messages, drivers and dependencies.

## How to test a contributor Pull Request

1. Note the number *XXX* of the PR to test from the [Pull requests page](https://github.com/nabaztag2018/pynab/pulls).

2. Go to the pynab folder on your rabbit: `cd $HOME/pynab`

3. Checkout *PR #XXX* to a new local branch *prxxx* (see [Checking out GitHub pull requests locally](https://docs.github.com/en/github/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally))

4. Switch to this branch: `git checkout prxxx`

5. Prepare Pynab environment for testing:
    - if needed (when PR has changes in drivers, dependencies, data models or localisation messages) do a full upgrade: `bash install.sh --upgrade`
    - otherwise just restart the Pynab services: `sudo ./venv/bin/python manage.py stop_all && sudo ./venv/bin/python manage.py start_all`

6. Do your tests...

7. Switch back to default (master or release) branch: `git checkout master`

8. Rollback Pynab environment:
     - if needed (when PR had changes in drivers, dependencies, data models or localisation messages) do a full upgrade: `bash upgrade.sh`
     - otherwise just restart the Pynab services: `sudo ./venv/bin/python manage.py stop_all && sudo ./venv/bin/python manage.py start_all`

9. All done! You can delete your test branch: `git branch -D prxxx`

Then add comments on Pull Request as appropriate.
