# Metador Push

![Project status](https://img.shields.io/badge/status-beta-%23ffff00)
[
![Test](https://img.shields.io/github/workflow/status/Materials-Data-Science-and-Informatics/metador-push/test?label=test)
](https://github.com/Materials-Data-Science-and-Informatics/metador-push/actions?query=workflow:test)
[
![Coverage](https://img.shields.io/codecov/c/gh/Materials-Data-Science-and-Informatics/metador-push?token=BJJ15RHNJA)
](https://app.codecov.io/gh/Materials-Data-Science-and-Informatics/metador-push)
[
![Docs](https://img.shields.io/badge/read-docs-success)
](https://materials-data-science-and-informatics.github.io/metador-push/)

<img style="center-align: middle;" alt="Metador Logo" src="https://github.com/Materials-Data-Science-and-Informatics/Logos/raw/main/Metador/Metador_Logo_Text.png" width=70% height=70% /> **Push**

| Are you looking for :arrow_right: [the `metador` framework](https://github.com/Materials-Data-Science-and-Informatics/metador-core)? |
| --- |
| :exclamation: In the next update `metador-push` will be integrated into the `metador` ecosystem :exclamation: |


## TL;DR

* **Summary:** File upload service with resumable uploads and rich metadata requirements
* **Purpose:** Comfortably get data from someone else while **enforcing submission of relevant metadata**
* Easy to set up, no complicated dependencies or requirements
* Metadata validation based on dataset profiles using file name pattern matching and [JSON Schema](https://json-schema.org/)
* Authentication via ORCID, with optional allowlist to restrict access
* Successfully uploaded and annotated datasets can be passed over to some post-processing:
  - Either launch a script to handle the completed dataset directory,
  - or notify a different service via HTTP,
  - (or just collect the (meta)data from your "data mailbox" manually)

https://user-images.githubusercontent.com/371708/155495188-caa23208-3092-4639-acfc-970f062f98c4.mp4

## Overview

Metador Push is a metadata-aware mailbox for research data.

Like a real mailbox, it should be really simple to set up and use and should not be in your way.

Unlike a real mailbox where any content can be dropped, Metador Push wants to help you, the
data receiver, to make sense of the data, by requiring the uploader to fill out a form of
your choice for each file to provide all necessary metadata.

**Thereby, Metador Push faciliates FAIRification of research data by providing a structured
interface to condensate implicit contextual domain knowledge into machine-readable
structured metadata.**

If you **formalize** your metadata requirements in the form of JSON Schemas, then Metador Push
will **enforce** those requirements, if you let your collaborators share their data
with you through it. At the same time, you are **in full control** of the data, because
Metador Push is simple to set-up locally and eliminates the need of a middle-man service that
assists you with moving larger (i.e., multiple GB) files over the internet.

Using Metador Push, the sender can upload a dataset (i.e., a collection of files) and must
provide metadata for the files according to your requirements. After the upload and
metadata annotation is completed, Metador Push can notify other services to collect and further
process this data (*post-processing hooks*). For example, you can use this to put
completed and fully annotated datasets into your existing in-lab repository or storage, or
apply necessary transformations on the data or metadata. This makes Metador Push **easy to
integrate into your existing workflows**.

To achieve these goals, Metador Push combines state-of-the-art resumable file-upload technology
using [Uppy](https://uppy.io) and the [tus](https://tus.io/) protocol
with a [JSON Schema](https://json-schema.org/) driven multi-view metadata editor based on
[react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form)
and [JSONEditor](https://github.com/josdejong/jsoneditor).

## Why not a different self-hosted file uploader?

To the best of our knowledge, before starting work on Metador Push, there was no off-the-shelf
solution checking all of the following boxes:

* lightweight (easy to deploy and use on a typical institutional Linux server)
* supports convenient upload of large files (with progress indication, pauseable/resumable)
* supports rich and expressive metadata annotation that is **generic** (schema-driven)

If you care about this combination of features, then Metador Push is for you.
If you do not care about collecting metadata, feel free to pick a different solution.

## Installation

*If you are not a fluent command line user, it is recommended to let your local system
administrator set up an instance of Metador Push for you. You should then provide them with the
domain-specific dataset profiles and JSON Schemas as it is explained further below.*

* Clone this repository: `git clone git@github.com:Materials-Data-Science-and-Informatics/metador-push.git`

* Check that you have Python >=3.7 and Node.js >= 14.15 by running `python --version`, `node --version`

If you do not have a sufficiently recent Python or Node.js version installed,
use respectively [`pyenv`](https://github.com/pyenv/pyenv) or [`nvm`](https://github.com/nvm-sh/nvm)
in order to install a suitable Python or Node.js locally.

* Download and install [`tusd`](https://github.com/tus/tusd) (tested with 1.6.0)

This is the server component for the Tus protocol that will handle the low-level details
of the file uploading process. It is downloaded as a OS-specific executable to be placed into
either `/usr/bin` (global) or `~/.local/bin` (user) directory.

* go to the `frontend` subdirectory in the cloned repository and run `npm install && npm run build` to build the frontend.

* go back to the top level directory of the repository and install Metador Push using `poetry install`,
  if you use poetry, otherwise use `pip install --user .` (as usual, using a `venv` is recommended).

## Usage

### I want to see it in action, now!

* Ensure that tusd and Metador Push are installed
and that the `tusd` and `metador-push-cli` scripts are on your path, i.e. executable.

* Run `tusd` like this: `tusd -hooks-http "$(metador-push-cli tusd-hook-url)"`

* Run Metador Push like this: `metador-push-cli run`

* Navigate to `http://localhost:8000/` in your browser.

### I want to deploy Metador Push properly! (for system administrator)

As Metador Push tries to be a general building block and not impose too many assumptions on
your setup, here only a general overview of the required steps is provided.

For serious deployment into an existing infrastructure, the following steps are required:

* prepare JSON Schemas for the metadata you want to collect for the files.

* write dataset profiles linking the JSON Schemas to file name patterns (explained below).

* think about the way how both `tusd` and Metador Push will be visible to the outside world.
  This probably involves a reverse proxy, e.g. Apache or nginx to serve both applications
  and take care of HTTPS. Make sure that the public hostname is an alias for localhost in
  `/etc/hosts`, if running both services on the same machine.

  However your setup might be, you need to make sure that:

  1. both `tusd` and Metador Push are accessible from the client side (notice that by default
    they run on two different ports, unless you mask that with route rewriting).

  2. The passed hook endpoint URL of Metador Push is accessible by `tusd`.

  3. The file upload directory of `tusd` is accessible (read + write) by Metador Push.

* Use `metador-cli default-conf > metador.toml` to get a copy of the default config file,
  add your JSON schemas and
  at least change the `metadir.site` and `tusd.endpoint` entries according to your
  planned setup (you will probably at least change the domain, and maybe the ports).
  You can delete everything in your config that you do not want to override.

* *Optional:* For ORCID integration, you need access to the ORCID public API.
  If you don't use ORCID, you have to take care of authorization yourself!

* Run `tusd` as required with your setup, passing
  `-hooks-http "$(metador-push-cli tusd-hook-url)"` as argument.

* Run Metador Push with your configuration: `metador-push-cli run --conf YOUR_CONFIG_FILE`

  Metador Push will use the current directory as the working directory and also look for
  profiles and the configuration file there, unless told otherwise via CLI interface or
  configuration settings.

* To start metador-push and tusd automatically on start of the system or virtual machine,
  look at the example `.service` files. These must be adapted according to your setup
  and placed in `/etc/systemd/system`.
  After doing this, they can be enabled with
  `systemctl enable metador-push` and `systemctl enable metador-push-tusd`,
  and managed just like any other background service, i.e. the logs that are printed to
  the standard output then can be inspected with `journalctl`.

### Using HTTPS

**You definitely should set up some kind of encryption! Especially if you work with
sensitive data, classified data, data under an embargo or even just unpublished data!
If you do not encrypt your traffic, someone could read it in transit like a postcard!**

To enable https, use a reverse proxy that handles traffic encryption for you.
You can use the provided example nginx configuration as a starting point.
Remember to set the `-behind-proxy` flag when starting `tusd` in order to
handle proxy headers correctly.

For testing purposes, you can easily generate a self-signed certificate:
```
openssl req -nodes -x509 -newkey rsa:4096 -keyout cert.key -out cert.pem -days 365
```

For production use, get a certificate that is signed by your institution, or get
one from [Let's Encrypt](https://letsencrypt.org/), e.g. by following
[these](https://www.itzgeek.com/how-tos/linux/debian/how-to-install-lets-encrypt-ssl-certificate-for-nginx-on-debian-11.html)
[guides](https://stevenwestmoreland.com/2017/11/renewing-certbot-certificates-using-a-systemd-timer.html).

## Setting up ORCID Authentication

Follow instructions given e.g.
[here](https://info.orcid.org/documentation/integration-guide/registering-a-public-api-client/)
As redirect URL you should register the value you get from `metador-push-cli orcid-redir-url`
(the output is based on your configuration).

Afterwards, fill out the `orcid` section of your Metador Push configuration accordingly,
adding your client ID and secret token.

If you register on the ORCID sandbox server, do not forget to set `sandbox=true`!

## Deployment using Docker

To build a Docker image with a pre-configured setup of metador-push, tusd and nginx, run:

```
docker build -t metador-push:latest .
```

Prepare a directory (e.g. called `metador-push_rundir`) that contains the following items:

* your Metador Push configuration `metador-push.toml`
* a `profiles` directory containing your dataset profiles (explained below) and JSON schemas
* SSL certificate and key named `cert.pem` and `cert.key` valid for the domain you will use for accessing Metador Push

This directory is used both for configuration and retrieval of the data.

To run Metador Push with your prepared directory `./metador-push_rundir`, run:

```
docker run -it --mount type=bind,source="$(pwd)"/metador-push_rundir,target=/mnt -p 80:80 -p 443:443 metador-push:latest
```

Now you should be able to access Metador Push on your computer
by visiting `https://localhost` in your browser.

## Dataset profiles and JSON Schemas

In your configuration you must provide an existing directory that contains your
dataset profiles and (local) JSON Schemas that are referenced in the profiles.

A dataset profile must have the following shape:
```
{
  "title": "Dataset Profile Title",
  "description": "Short summary of what this dataset profile is intended for",
  "schemas": {
    "SCHEMA_NAME_1": <JSONSCHEMA>,
    ...,
    "SCHEMA_NAME_N": <JSONSCHEMA>,
  },
  "rootSchema": "SCHEMA_NAME" | bool,
  "patterns": [
    {"pattern": ".*\\.txt", "useSchema": "SCHEMA_NAME" | bool},
    {"pattern": ".*\\.jpg", "useSchema": "SCHEMA_NAME" | bool},
    {"pattern": ".*\\.mp4", "useSchema": "SCHEMA_NAME" | bool}
  ],
  "fallbackSchema": "SCHEMA_NAME" | bool
}
```

The `title` and `description` keys are self-explanatory.
The `schemas` section can be used to embed arbitrary JSON Schemas that are e.g. not
relevant for other profiles or for some other reason are not stored in a separate file.

The keys `rootSchema`, `fallbackSchema` and `patterns` are defining the behavior of the
dataset profile.

The key `rootSchema` defines the JSON Schema that is defining the metadata required for
the dataset itself, i.e. file-independent, general metadata or metadata that applies to
e.g. all the files (e.g. for reducing the effort for the user).

For each uploaded file, the filename is matched against the listed `patterns` in the
provided order. In case of a full match (i.e. the pattern must match the complete
filename) the corresponding schema is used. If no pattern matches, then the
`fallbackSchema` is applied.

Remember that in the pattern a regex is expected, so characters like `.`, `*` etc. are
interpreted as special symbols unless escaped by a backslash. But because backslashes also
must be escaped in a string, e.g. in order to match an actual `*` symbol, the pattern must
be `"\\*"`.

As a schema to be applied, you can use

* a boolean
* the name of an embedded schema in the `schemas` section
* a filename of a JSON schema (relative to the profile directory)

Setting the schema to `true` means that arbitrary metadata can be provided. In the UI this
special case is treated by providing the possibility to add arbitrary key-value pairs as
metadata.

Setting the schema to `false` would literally mean that no metadata could be valid. This
is not useful, so instead a `false` schema is interpreted as forbidding to use a file with
a name that matched the pattern (in case of `useSchema`) or to upload files that do not
match any pattern (in case of `fallbackSchema`).

## Cleaning up abandoned uploads and datasets

The upload server tusd will create intermediate files in its own data directory, in
normal operation they will be removed/relocated when a file upload is completed.
In the case that an upload is abandoned, these intermediate files will stay there forever,
unless cleaned up.

To clean up, you can run `metador-push-cli tusd-cleanup YOUR_TUSD_DATA_DIR`. The command should
be launched in the same directory where the server is run and with the same configuration,
so the tusd directory shall be either relative to that location, or an absolute path.

To automate this, you can e.g. set up a cronjob to run this script regularily.

## Technical FAQ

The following never actually asked questions might be of interest to you.

### Feature: Can I upload existing JSON metadata for the files?

The only purpose of Metador Push is to enable a human-friendly input form to simplify the
annotation of the data. If the users happen to have JSON files that are valid according to
the required schema, of course you can just switch to the raw JSON Editor view and paste
the content there. But if you do already have structured metadata, you most likely do not
need Metador Push.

### Feature: Will there be an API for external tools to automate uploads?

This service is intended for use by human beings, to send you data that originally has
ad-hoc or lacking metadata. If the dataset is already fully annotated, it probably should
be transferred in a different and simpler way offered by your database or repository
solution.

If you insist on using this service mechanically, in fact it is designed to be as RESTful
as possible so you might try to script an auto-uploader. The API is accessible under the
`/docs` route. For uploads you would also need a
[tus client](https://tus.io/implementations.html).
The only difficult point would be the automated ORCID authentication that you must handle.
There is no and probably will be no "API token" support.

### Feature: Will there be support for e.g. cloud-based storage?

No, this service is meant to bring annotated data to **your** hard drives, that must be
large enough to store the files at least temporarily.
Your post-processing script can do with completed datasets whatever it wants, including
moving it to arbitrary different locations.

### Feature: Will there be support for authentication mechanisms besides ORCID?

ORCID is highly adopted in research and allows to sign in using other mechanisms,
to that in the research domain it should be sufficient. If you or your partners do not
have an ORCID yet, maybe now it is the time!

If you want to restrict access to your instance to a narrow circle of persons, instead of
allowing anyone with an ORCID to use your service, just use the provided **allowlist**
functionality.

It is **not** planned to add authentication that requires the user to register
specifically to use this service. No one likes to create new accounts and invent new
passwords, and you probably have more important things to do and do not need the
additional responsibility of keeping these credentials secure.

If you, against all advice, want to have a custom authentication mechanism, use
this with ORCID disabled, i.e. in "open mode", and then restrict access to the service in
a different way.

## Development

### Initial Preparations

To setup Metador Push for development, perform the following steps:

1. Go to your Metador Push project directory and run `poetry install`.

2. Next, `pre-commit install` to enable the required pre-commit hooks.

2. Create a separate directory (ideally outside the `metador-push` project directory),
   e.g. call it `metador-push_rundir`.

3. Symlink the `profiles` from the project directory to your runtime directory or create a
   new profiles directory with your profiles for testing and development.

4. Create a `metador-push.toml` config file in the runtime directory and override some default
   settings. You might want to use a configuration like this:
```
[metador-push.log]
level = 'DEBUG'
file = 'metador-push.log'

[orcid]
enabled = true
use_fake = true
sandbox = true

[uvicorn]
reload = true
```

The option `use_fake` will enable a dummy sign-on that does not use real ORCID servers and
does not need having an ORCID. When `use_fake` is disabled, but `sandbox` is enabled,
Metador Push instead will use the [ORCID test server](https://sandbox.orcid.org/) instead of
the real one. Notice that both the test and production servers of ORCID respectively need
the setting up described above and a registered user account.

### Running Metador Push for development

To start, you should first go to the Metador Push project directory run `poetry shell`.
Then switch to the runtime directory (the one with your `metador-push.toml`)
and run `metador-push-cli run`.

For frontend development, you can run `npm run dev` in the frontend directory in addition
to the Metador Push server to get auto-reload for the frontend. Be sure to use the frontend
served by the backend server (by default running on port 8000), though!

Before commiting, run `pytest` and make sure you did not break anything.

To generate documentation locally, run `pdoc -o docs metador-push`.

To check coverage, use `pytest --cov`

Also verify that the pre-commit hooks all run and complete successfully.

## Copyright and Licence

See [LICENSE](./LICENSE).

### Main used libraries and dependencies

The following libraries are used directly (i.e. not only transitively) in this project:

**CLI:** typer (MIT), toml (MIT), colorlog (MIT)

**Backend:** FastAPI (MIT), pydantic (MIT), httpx (BSD-3), tusd (MIT), jsonschema (MIT)

**Backend testing:** pytest (MIT), pytest-cov (MIT), pytest-asyncio (Apache 2), aiotus (Apache 2)

**Frontend:** Svelte (MIT), svelte-fa (MIT), svelte-navigator (MIT), svelte-notifications (MIT),
svelte-jsoneditor (ISC), uppy (MIT), Picnic CSS (MIT), Font-Awesome (MIT/CC-BY-4.0), FileSaver.js (MIT), react-jsonschema-form (Apache 2)

More information is in the documentation of the corresponding packages.

## Acknowledgements

<div>
<img style="vertical-align: middle;" alt="HMC Logo" src="https://github.com/Materials-Data-Science-and-Informatics/Logos/raw/main/HMC/HMC_Logo_M.png" width=50% height=50% />
&nbsp;&nbsp;
<img style="vertical-align: middle;" alt="FZJ Logo" src="https://github.com/Materials-Data-Science-and-Informatics/Logos/raw/main/FZJ/FZJ.png" width=30% height=30% />
</div>
<br />

This project was developed at the Institute for Materials Data Science and Informatics
(IAS-9) of the Jülich Research Center and funded by the Helmholtz Metadata Collaboration
(HMC), an incubator-platform of the Helmholtz Association within the framework of the
Information and Data Science strategic initiative.

<img src="https://user-images.githubusercontent.com/371708/156158094-9b5fff08-ec62-4dc3-9715-dfe5be432fa2.png" width=50% height=50% />

This project has received financial support from the European Research Council through the
ERC Grant Agreement No. 759419 MuDiLingo (‘A Multiscale Dislocation Language for
Data-Driven Materials Science’).
