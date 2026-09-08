"""sift -- runs your command, then gives the model only the lines that matter.

Three rules hold this package up, and every module below is written to keep them:

Nothing shown is invented. A judge is only ever asked which line numbers matter;
the text is printed from the local capture, byte for byte. A judge that makes up
a line cannot get it into the output, because its words are never used.

Nothing is thrown away. The raw capture stays on disk and `peek` hands it back
unchanged. What you read is a selection, not a summary, and every gap says how
many lines stood there.

Nothing here can break your command. No key, no network, an overloaded model, a
reply that makes no sense -- each of these falls back to rules that need none of
them. A tool that drops output to save context has cost more than it saved.
"""

__version__ = "1.0.0"
