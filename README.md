# Metador

**M**etadata **E**nrichment and **T**ransmission **A**ssistance for **D**igital **O**bjects in **R**esearch

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
with a JSON Schema driven metadata editor.

## Why not a different self-hosted file uploader?

Before starting work on Metador, I was not able to find an existing solution checking all
of the following boxes:

* lightweight (easy to deploy and use on a typical institutional Linux server)
* supports upload of large files conveniently (with progress, resumable)
* supports rich and expressive metadata annotation that is **generic** (schema-driven)

If you care about this combination of features, then Metador is for you.
If you do not care about collecting metadata, feel free to pick a different solution.

## Installation

If you do not have a recent version of Python installed, you can use
[`pyenv`](https://github.com/pyenv/pyenv) to install e.g. Python 3.9.0 and enable it.

Download and install [`tusd`](https://github.com/tus/tusd),
the server component for the Tus protocol that will handle the low-level details
of the file uploading process.

Install Metador using `poetry install`, if you use poetry,
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
  add your JSON schemas (TODO: explain how) and
  at least change the `metadir.site` and `tusd.endpoint` entries according to your
  planned setup (you will probably at least change the domain, and maybe the ports).
  You can delete everything in your config that you do not want to override.

* *Optional:* For ORCID integration, you need access to the ORCID public API.

  Follow instructions given e.g. 
  [here](https://info.orcid.org/documentation/integration-guide/registering-a-public-api-client/)
  As redirect URL you should register the value you get from `metador-cli orcid-redir-url`.
  Afterwards, fill out the `orcid` section of your Metadir configuration accordingly.

* Run `tusd` as required with your setup, passing 
  `-hooks-http "$(metador-cli tusd-hook-url)"` as argument.

* Run Metador with your configuration: `metador-cli run --conf YOUR_CONFIG_FILE`


## Copyright and Licence

See [LICENSE](./LICENSE).

## Acknowledgements

Built using FastAPI, typer, pydantic, tusd, uppy, milligram

Checked using pytest, pre-commit, black, flake8, mypy

Packaged using poetry
