# Security

`sift` runs shell commands on your machine and sends text to a model over the
network. Both of those deserve a straight answer, so this file is what it does,
what it does not do, and how to tell someone if it is wrong.

## What runs

`sift run` executes the command it is given. That is the whole tool, and it is
not sandboxed: a command handed to `sift` can do exactly what it could do if you
had typed it, because it *is* what you typed.

Over MCP this matters more, because the caller is a model. The `run` and `tool`
tools are declared **destructive** in their annotations for that reason —
`run` executes an arbitrary command line, and `tool` passes its arguments
through to `ast-grep`, which rewrites files when asked to. A client that
auto-approves read-only tools has been told which ones those are: `peek`,
`outline`, `digest` and `digest_many`.

`sift hook --install` writes into your client's own settings file. It asks
first, shows what it will add, and adds rather than replaces.

## What leaves the machine

One thing: the text of a question — the numbered lines a model is asked to
choose from. Not the file names, not the command, not the environment.

Before it is sent, anything credential-shaped is replaced: tokens with a known
prefix, JWTs, authorization headers, passwords in connection strings, the body
of a PEM block. **This masking is not complete and does not claim to be.** A
bare secret shaped like nothing in particular gets through.

Three switches, and the first is the one that guarantees:

```bash
SIFT_NO_MODEL=1   # nothing is ever sent; the deterministic view is used
SIFT_MASK=0       # send unmasked, if you have decided that is what you want
SIFT_BASE_URL=... # send to your own endpoint instead of a hosted one
```

Captured bytes never leave `$SIFT_HOME` (`~/.cache/sift` by default). Nothing is
uploaded, nothing is logged elsewhere, and removing a capture's directory
removes everything ever kept about it.

## What is kept, and where

Every byte a command wrote, on disk, until you remove it. `sift gc [DAYS]` is
the only thing that deletes a capture and it deletes when you type it.

The captures are files in your home directory with your own permissions on
them. They are not encrypted. A command that printed a secret has that secret
on disk in a file only you can read — the same as a shell that scrolled it past
you and wrote it to `~/.bash_history`, and worth knowing.

An API key is read from `$SIFT_API_KEY`, `$NVIDIA_API_KEY`, or
`~/.config/nvidia/api_key`. It is never written anywhere by this tool and never
appears in a capture, a view or a footer.

## Reporting something

Open a **private** security advisory:
<https://github.com/slymnysr/sift/security/advisories/new>

If that is not available to you, open an ordinary issue that says only that you
have found something and how to reach you — not the details.

What is worth reporting: a way to make masking fail on something it claims to
catch, a path where captured bytes leave the machine, a way for a tool
annotation to be wrong about what a tool does, a way for `hook --install` to
write something other than what it showed.

What is not a vulnerability: `sift run` running the command it was given.

There is no support commitment and no timetable. This is one person's project;
what there is, is a reply.
