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

## FAQ

The following never actually asked questions might be of interest to you.

### Feature: Will there be an API for external tools to automate uploads?

No, this service is intended strictly for use by human beings, to send you data that
originally has ad-hoc or lacking metadata. If the dataset is already fully annotated, it
should be transferred in a different way.

### Feature: Will there be support for e.g. cloud-based storage?

No, this service is meant to bring annotated data to **your** hard drives. Your
post-processing script can do with completed datasets whatever it wants, including
moving it to arbitrary different locations.

### Feature: Will there be support for HTTP-based post-processing hooks?

No, the only kind of hook ever provided will be the automatic calling of a script. The
datasets are located on the hard-drive, your post-processing needs access to it anyway. It
makes no sense to involve networking, in the same way as it would be absurd to make `git`
hooks use the network. Of course, you can write a hook script that uses networking
yourself, e.g. to send a network request to trigger an E-Mail about the new dataset.

### Feature: Will there be support for authentication mechanisms besides ORCID?

ORCID is highly adopted in research and allows to sign in using other mechanisms,
to that in the research domain it should be sufficient. If you or your partners do not
have an ORCID yet, maybe now it is the time!

If you want to restrict access to your instance to a narrow circle of persons, instead of
allowing anyone with an ORCID to use your service, just use the provided **whitelist**
functionality (TODO).

It is **not** planned to add authentication that requires the user to register
specifically to use this service. No one likes to create new accounts and invent new
passwords, and you probably have more important things to do and do not need the
additional responsibility of keeping these credentials secure.

If you, against all advice, want to have a custom authentication mechanism, use 
this with ORCID disabled, i.e. in "open mode", and then restrict access to the service in
a different way.

### Security: Can any (logged-in) user edit any dataset, knowing its UUID?

In principle - for non-completed datasets, yes, but this is not a problem.

This service tries to store as few information as possible, except for the actual
annotated data. Dataset upload and annotation is a transient workflow, this service does
not care about completed datasets after the user confirmed completion of the dataset and 
the post-processing hook has been called.

The UUID of a new dataset is given out by the server and is known only to the user who
created it. If you use HTTPS, but an attacker is still able to obtain the UUID of a
currently edited dataset of a regular user, then you have a serious security problem
elsewhere.

Finally, guessing UUIDs randomly, hoping that one can access a dataset to tamper with in
the narrow timeslot that the actual creator has not completed it yet, is clearly not a
feasible attack scenario.

Completed datasets can no longer be accessed by anyone from the client-side and therefore
can be considered to be as secure as the rest of your system.

## Development

Before commiting, run `pytest` and make sure you did not break anything.

Also verify that the pre-commit hooks are run, which includes `mypy` for type checking and
`black` and `flake8` for formatting.

## Copyright and Licence

See [LICENSE](./LICENSE).

### Used libraries and tools

#### Libraries

**CLI:** typer (MIT), toml (MIT)

**Backend:** FastAPI (MIT), pydantic (MIT), tusd (MIT), httpx (BSD-3), python-multipart (Apache 2.0)

**Frontend:** uppy (MIT), milligram (MIT)

...and of course, the Python standard library.

#### Tools

**Checked by:** pytest (MIT), pre-commit (MIT), black (MIT), flake8 (MIT), mypy (MIT)

**Packaged by:** poetry (MIT)

More information is in the documentation of the corresponding packages.
