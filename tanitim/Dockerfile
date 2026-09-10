# This image exists to be looked at, not to be used.
#
# Glama's listing check starts a server in a container and asks it what tools it
# has. That is all it needs, and that is all this does. It is kept here rather
# than at the root of the repository on purpose: a `Dockerfile` sitting beside
# the README reads as an invitation to run `sift` in a container, and running it
# there is the one way to make it answer the wrong question.
#
# `sift run` runs a command *on this machine* and shows you what mattered in its
# output. In a container it runs a command on a machine with none of your code,
# none of your tools and none of your processes -- and hands back a perfectly
# honest view of the wrong thing. Nothing about that is a packaging problem;
# it is what the tool is.
#
# So: introspection here, and installation from PyPI everywhere else.
#
#   uv tool install "sift-cli[mcp]"     # what a person should actually run
#
FROM python:3.13-slim

# `pip` is right here and refused elsewhere. A container's Python is not shared
# with an operating system, so there is no `EXTERNALLY-MANAGED` marker to
# respect and nothing to break by writing into it.
RUN pip install --no-cache-dir "sift-cli[mcp]"

# Nothing may leave this container. A checker's sandbox has no key to ask a
# model with, and this says so rather than letting the server decline tool by
# tool: `tools/list` answers either way, and this way the image cannot reach the
# network even if somebody hands it a key by accident.
ENV SIFT_NO_MODEL=1

ENTRYPOINT ["sift-mcp"]
