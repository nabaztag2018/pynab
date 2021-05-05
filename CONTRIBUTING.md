# Welcome to Pynab!

Thank you so much for contributing to the project. All contributions are
welcome. Please take a moment to review these guidelines. Following them will
ensure the contribution process is easy and effective for everyone involved.

## How-to contribute to Pynab

### Reporting bugs

Please **Check [existing issues](/nabaztag2018/pynab/issues)** to make sure the
bug was not already reported. If you are running latest release, make sure the
bug was not fixed on master branch by checking closed issues as well.

If you're unable to find an open issue addressing the problem,
[open a new one](/nabaztag2018/pynab/issues/new). Be sure to include as much
relevant information as possible, ideally providing a reproduceable test case
demonstrating the expected behavior that is not occurring.

### New features or changes to existing features

If have new ideas but lack the skills to implement them, please discuss them
on the [community forum](http://tagtagtag.fr/forum/). Ideas that demonstrate
a strong community demand are more likely to find skilled developers willing
to implement them.

Please note that services can be added without being integrated to pynab base
project and could simply exploit the Nabd PROTOCOL and be installed separately.

If you intend to add a new feature or change an existing one, please engage
discussion first about what you are proposing by filing
[a new issue](/nabaztag2018/pynab/issues/new) or discussing it on the
[community forum](http://tagtagtag.fr/forum/).

### Submitting patches

Please open a new GitHub pull request with the patch. Before submitting, please
read the guide below about developing. We are more likely to accept
patches for existing issues / enhancements.

### Your first code contribution

Unsure where to begin contributing to Pynab? You can start by looking at issues
tagged [`good first issue`](https://github.com/nabaztag2018/pynab/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
They have been especially selected as they seem not too difficult at first
sight.

## How-to test a contributor Pull Request (PR)

1. Connect to your Nabaztag 🐰: `ssh pi@nabaztag.local`
2. Go to the pynab folder: `cd /home/pi/pynab`
3. List references in a remote repository: `git ls-remote --refs origin`
4. Open [Pull Request (PR) page](https://github.com/nabaztag2018/pynab/pulls) and memorize the PR number you want to test
5. Switch to the PR code, here PR #123, change number for your test: `git checkout master && git pull origin master && git fetch origin pull/123/head:pr/123 && git checkout pr/123 && git merge master`
6. Full upgrade for changes in drivers, dependencies, data models and localisation messages: `bash upgrade.sh`
7. Do your test 🚦
8. Rollback to default branch: `git checkout release`
9. Full upgrade for changes in drivers, dependencies, data models and localisation messages: `bash upgrade.sh`
10. All done ! 🎉

Then add comments on pull request 😉.

## How-to work with GitHub and Pull Requests

You can develop directly on your rabbit (RasperryPi) that you have of course
configured with ssh access (make sure you changed the default password). We
use editors with SFTP support.

If you haven't done so yet, fork the repository on GitHub, then add this fork
to your rabbit's repository.

```
git remote add fork https://github.com/YOUR_GITHUB_USERNAME/pynab.git
```

To develop your code, create a local branch with a name that makes sense.

```
git fetch origin
git checkout -b feature-name origin/master
```

At anytime, you can run tests locally (on the rabbit) by first stopping pynab
and services. Hardware tests require root access.

```
sudo ./venv/bin/python manage.py stop_all
sudo ./venv/bin/pytest
sudo ./venv/bin/python manage.py start_all
```

Before committing your code, make sure the style is conforming by running
black.

```
./venv/bin/black -l79 modified_file.py
```

Once you are happy with the result, rebase and push it to a dedicated branch on
your own GitHub fork.

```
git fetch origin
git rebase origin/master
git push fork HEAD:feature-name
```

GitHub will display the URL to create a pull request, with a git message such
as:

```
remote:
remote: Create a pull request for 'branch-name' on GitHub by visiting:
remote:      https://github.com/user/pynab/pull/new/branch-name
remote:
```

If you have a [Travis](http://travis-ci.org/) account and configured it to work
on your pynab fork (you should), you can wait for tests to pass on Travis
(currently takes less than 10 minutes).

Then create your pull request. More tests will be run, concerning style (if you
ran black, the only problem you might have concern some issues black could not
solve automatically), code quality and unit tests on Travis.

If tests fail, fix them and push to the branch, either with new commits or
by amending. Once tests pass, your request will be reviewed.

At any time, if you did commit your changes, you can go back to master with:

```
git fetch origin
git checkout master
bash upgrade.sh
```

The last command is required to run a full upgrade for changes in localized
messages, drivers and dependencies.
