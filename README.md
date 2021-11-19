# Metador

[
![Test](https://img.shields.io/github/workflow/status/Materials-Data-Science-and-Informatics/metador/test?label=test)
](https://github.com/Materials-Data-Science-and-Informatics/metador/actions?query=workflow:test)
[
![Coverage](https://img.shields.io/codecov/c/gh/Materials-Data-Science-and-Informatics/metador?token=BJJ15RHNJA)
](https://app.codecov.io/gh/Materials-Data-Science-and-Informatics/metador)
[
![Docs](https://img.shields.io/badge/read-docs-success)
](FIXME_GHPAGES_URL/metador)
[
![PyPIPkgVersion](https://img.shields.io/pypi/v/metador)
](https://pypi.org/project/metador/)


**M**etadata **E**nrichment and **T**ransmission **A**ssistance for **D**igital **O**bjects in **R**esearch

## TL;DR

* **Summary:** File upload service with resumable uploads and rich metadata requirements
* **Purpose:** Comfortably get data from outside while enforcing collection of certain metadata
* Easy to set up, no complicated dependencies
* Metadata validation based on file name pattern matching and JSON Schema
* Authentication via ORCID, with optional allowlist to restrict access
* Successfully uploaded and annotated datasets are passed to postprocessing:
  - Either launch a script to handle the completed dataset directory,
  - or notify a different service via HTTP.

## Overview

Metador is a metadata-aware mailbox for research data.

Like a real mailbox, it should be really simple to set up and use and should not be in your way.

Unlike a real mailbox where any content can be dropped, Metador wants to help you, the
data receiver, to make sense of the data, by requiring the uploader to fill out a form of
your choice for each file to provide all necessary metadata.

**Thereby, Metador faciliates FAIRification of research data and forms a boundary between
the unstructured, unannotated outside world and the FAIR, semantically annotated data
inside your amazing research institution.**

If you **formalize** your metadata requirements in the form of JSON Schemas, then Metador
will **enforce** those requirements, if you let your external partners share their data
with you through it. At the same time, you are **in full control** of the data, because
Metador is simple to set-up locally and eliminates the need of a middle-man service that
assists you with moving larger (i.e., multiple GB) files over the internet.

Using Metador, the sender can upload a dataset (i.e., a set of files) and must annotate
the files according to your requirements. After the upload and annotation is completed, a
hook can be triggered that will get a complete dataset for further processing. For
example, you can put completed and annotated datasets into your in-lab repository. This
makes Metador **easy to integrate into your existing workflows**.

To achieve these goals, Metador combines state-of-the-art resumable file-upload technology
using [Uppy](https://uppy.io) and the [tus](https://tus.io/) protocol
with a [JSON Schema](https://json-schema.org/) driven multi-view metadata editor based on
[react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form)
and [JSONEditor](https://github.com/josdejong/jsoneditor).

## Why not a different self-hosted file uploader?

Before starting work on Metador, I was not able to find an existing solution checking all
of the following boxes:

* lightweight (easy to deploy and use on a typical institutional Linux server)
* supports convenient upload of large files (with progress indication, pauseable/resumable)
* supports rich and expressive metadata annotation that is **generic** (schema-driven)

If you care about this combination of features, then Metador is for you.
If you do not care about collecting metadata, feel free to pick a different solution.

## Installation

If you do not have a recent version of Python (>=3.7) installed, you can use
[`pyenv`](https://github.com/pyenv/pyenv) to install e.g. Python 3.10 and enable it.

For the frontend, you need npm >= 7 to build the frontend (default for node >= 16)
and you can use e.g. [nvm](https://github.com/nvm-sh/nvm) to install it locally.

Download and install [`tusd`](https://github.com/tus/tusd),
the server component for the Tus protocol that will handle the low-level details
of the file uploading process.

First, go to the `frontend` directory and run `npm run build` to compile the frontend.

Then install Metador using `poetry install`, if you use poetry,
or use `pip install --user .` if you use pip (as usual, using a `venv` is recommended).

## Usage

### I want to see it in action, now!

Ensure that tusd and Metador are installed
and that the `tusd` and `metador-cli` scripts are on your path.

Run `tusd` like this: `tusd -hooks-http "$(metador-cli tusd-hook-url)"`

Run Metador like this: `metador-cli run`

Navigate to `http://localhost:8000/` in your browser.

### I want to deploy Metador properly!

For serious deployment into an existing infrastructure, some more steps are required:

* prepare JSON Schemas for the metadata you want to collect for the files.

* think about the way how both `tusd` and Metador will be visible to the outside world.
  I cannot give you assistance with your specific setup that might involve e.g. Apache
  or nginx to serve both applications.

   However your setup might be, you need to make sure that:

   1. both `tusd` and Metador are accessible from the client side (notice that by default
      they run on two different ports, unless you mask that with route rewriting and
      forwarding).

   2. The passed hook endpoint URL of Metador is accessible by `tusd`.

   3. The file upload directory of `tusd` is accessible (read + write) by Metador.

* Use `metador-cli default-conf > metador.toml` to get a copy of the default config file,
  add your JSON schemas and
  at least change the `metadir.site` and `tusd.endpoint` entries according to your
  planned setup (you will probably at least change the domain, and maybe the ports).
  You can delete everything in your config that you do not want to override.

* *Optional:* For ORCID integration, you need access to the ORCID public API.

* Run `tusd` as required with your setup, passing
  `-hooks-http "$(metador-cli tusd-hook-url)"` as argument.

* Run Metador with your configuration: `metador-cli run --conf YOUR_CONFIG_FILE`

## Using HTTPS with Uvicorn server

To enable https, use a reverse proxy that handles https for you.
You can use the provided example nginx configuration as a starting point.
Remember to set `-behind-proxy` flag when starting `tusd` in order to
handle proxy headers correctly.

For testing purposes, you can easily generate a self-signed certificate:
```
openssl req -nodes -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
```

## Setting up ORCID Authentication

Follow instructions given e.g.
[here](https://info.orcid.org/documentation/integration-guide/registering-a-public-api-client/)
As redirect URL you should register the value you get from `metador-cli orcid-redir-url`.

Afterwards, fill out the `orcid` section of your Metadir configuration accordingly,
adding your client ID and secret token.

If you register on the ORCID sandox server, do not forget to set `sandbox=true`!

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

To clean up, you can run `metador-cli tusd-cleanup YOUR_TUSD_DATA_DIR`. The command should
be launched in the same directory where the server is run and with the same configuration,
so the tusd directory shall be either relative to that location, or an absolute path.

To automate this, you can e.g. set up a cronjob to run this script regularily.

## Technical FAQ

The following never actually asked questions might be of interest to you.

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

For backend development, you can enable auto-reload of uvicorn in the `metador.toml`.
For frontend development, run `npm run dev` in the frontend directory in addition to the
Metador server to get auto-reload.

Before commiting, run `pytest` and make sure you did not break anything.

To generate documentation, run `pdoc -o docs metador`.

To check coverage, use `pytest --cov`

Also verify that the pre-commit hooks all run successfully.

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
