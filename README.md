# gitly
Lightwight Python wrapper around pygit2

Gitly provides 2 interesting objects:

* An immutable Tree which is a wrapper around a pygit2.Tree, and simplifies the management of a GIT data structure.

* A mutable Branch object which supports dictionary style access and has a commit() method.

These objects make it easy to use GIT to store and fetch data from your application.
