# Contributing to ConductHotline.com

Thank you for being interested in contributing!

There is a mailing list for contributors if that's your thing. It's [conducthotlinecom-contributors@googlegroups.com](https://groups.google.com/forum/#!forum/conducthotlinecom-contributors).

I'm often open to pair programming on specific features. If you're interested, you can reach out to me at me@thea.codes.

## About conducthotline's architecture

Conducthotline is written as a single monolithic Python application. It uses PostgreSQL as the database, Firebase Auth as the authentication provider, and Nexmo as the telephony provider.

It is deployed to Google App Engine (3.7 runtime on standard) and uses CloudSQL's hosted PostgreSQL instance.

## Setting up your machine for development.

If you want to contribute you might need to install a few things before getting started.

### Install Python 3.7 (or later).

For Windows and Mac, I recommend just using the [python.org](https://python.org) installers. They should work fine. Alternatively, for Mac, you can use [pyenv](https://github.com/pyenv/pyenv).

For Linux, I recommend just compiling from source. For debian-based systems, this looks like this:

```bash
# Install build dependencies
sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev wget
# Download source
wget https://www.python.org/ftp/python/3.7.4/Python-3.7.4.tar.xz
# Extract
tar -xf Python-3.7.4.tar.xz
# Build
cd Python-3.7.4
./configure
make -j 8
# Install to /usr/local/bin/python3.7
sudo make altinstall
# Verify Python version
python3.7 --version
```

### Install Nox

[Nox](https://nox.thea.codes) is used to manage development tasks including starting the development server and running tests.

It's recommend you install Nox into the [user prefix](https://pip.pypa.io/en/stable/reference/pip_install/#cmdoption-user):

```bash
python3.7 -m pip install --user nox
```

You can then execute Nox with:

```
python3.7 -m nox --version
```

Optionally you can add the user prefix to your path (`~/.local/bin` or `%APPDATA%Python/Scripts` on Windows) and just use `nox --version`.

### Attempt to run the tests

The best way to see if your installation is setup is to run the tests.

Clone the repo and try running Nox

```
cd conductholine.com
python3.7 -m nox -s test
```

If there's any issues with your environment this will throw an error. If you run into trouble reach out to conducthotlinecom-contributors@googlegroups.com


## Running the application locally

To run the application locally you'll need to configure a secrets file and setup the database.

### Configuring secrets.json

Copy `secrets.example.json` to `secrets.json`.

You can leave the values as-is for now, however, you won't be able to test telephony and auth-related stuff. Telephony will error, but auth will give you access to everything.

If you wish to actually test telephony or auth locally you'll need to get the configuration values for your own Nexmo or Firebase account respectively and update the values in `secrets.json`.

### Setting up the database

To initialize the database run:

```bash
python3.7 -m nox -s cli -- reset-database
```

### Running the development server

Once you have secrets and a database, you can run the development server using:

```bash
python3.7 -m nox -s serve
```

The server should start and automatically watch for changes.


## Modifying the database and applying migrations

If you're working on a feature that requires modifying the database structure (new table or field), you'll need to code the change into a migration and apply it.

See the existing migrations in `hotline/database/migrations` for examples. Once you've written your migration you can run it using:

```bash
python3.7 -m nox -s cli -- apply-migration 0004_add_number_features
```

Where you'd replace the example `0004_add_number_features` with your migration.

You'll also need to either apply new migrations or reset your database if you `git pull` changes from upstream that introduced database structure changes.
