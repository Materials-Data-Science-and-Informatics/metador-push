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
or use `pip install --user .` if you use pip.

## Usage

1. Prepare a Metador configuration file where you should at least set a correct `tusd`
   endpoint, assign some JSON schemas to filename patterns, and configure authentication
   (if you want it). You can start with the default configuration: `metador-cli
   default-conf > metador.toml`

1. Run `tusd` as you desire (you can keep the default settings for testing or internal
   use) with the argument `-hooks-http "http://localhost:8000$(metador-cli hook-route)"`.
   Adapt the host and port accordingly, if you serve metador under a different address.

2. Run Metador with your configuration. If you run `tusd` with default settings, this will
   be an URL like `http://localhost:1080/files/`. Adapt the host and port accordingly, if
   you serve `tusd` under a different address.

Make sure that:

1. The provided `tusd` endpoint is accessible from the client side.

2. The passed hook endpoint of Metador is accessible from `tusd`.

3. The file upload directory of `tusd` is accessible (read + write) by Metador.

The `metador-cli` utility provides commands that should help you with configuration.

## Copyright and Licence

See [LICENSE](./LICENSE).
