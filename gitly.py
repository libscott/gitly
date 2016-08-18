import pygit2


class Commit(object):
    def __init__(self, repo, pygit2_commit):
        self._commit = pygit2_commit
        self.oid = pygit2_commit.oid
        self.repo = repo

    @property
    def tree(self):
        return Tree(self.repo, self._commit.tree)

    def log(self):
        log_ = self.repo.walk(self._commit.oid, pygit2.GIT_SORT_TIME)
        return (Commit(self.repo, c) for c in log_)

    def branch(self, name, force=False):
        branch = self.repo.create_branch(name, self._commit, force)
        return Branch(self.repo, branch.name)


def empty_tree(repo):
    empty = repo.TreeBuilder()
    return repo.get(empty.write())


EMPTY = object()


class Tree(object):
    def __init__(self, repo, pygit2_tree=None):
        self.repo = repo
        if pygit2_tree is None:
            pygit2_tree = empty_tree(repo)
        self._tree = pygit2_tree
        self.oid = pygit2_tree.oid.hex

    _ERROR = object()

    def get(self, path, default=_ERROR):
        out = self
        for part in path.strip('/').split('/'):
            out = out._get(part)
            if out == Tree._ERROR:
                if default == Tree._ERROR:
                    raise KeyError(path)
                return default
        return out

    def _get(self, path):
        if path in self._tree:
            entry = self._tree[path]
            if entry.filemode == pygit2.GIT_FILEMODE_BLOB:
                blob = self.repo.get(entry.oid)
                return blob.read_raw()
            elif entry.filemode == pygit2.GIT_FILEMODE_TREE:
                tree = self.repo.get(entry.oid)
                return Tree(self.repo, tree)
        return Tree._ERROR

    __getitem__ = get

    def object_id(self, path):
        tree = self._tree
        parts = path.rsplit('/', 2)
        basename = parts.pop()
        if parts:
            tree = self.get(parts[0])._tree
        return tree[basename].oid

    def subtree(self, path):
        entry = self._tree[path]
        if entry.filemode == pygit2.GIT_FILEMODE_TREE:
            tree = self.repo.get(entry.oid)
            return Tree(self.repo, tree)
        raise KeyError(path)

    def subtree_or_empty(self, path):
        try:
            return self.subtree(path)
        except KeyError:
            return Tree(self.repo)

    def set(self, path, data):
        """
        Return a new tree inheriting from this tree, setting or updating
        a given path.
        """
        parts = path.strip('/').split('/', 1)
        key = parts.pop(0)

        if parts:
            data = self.subtree_or_empty(key).set(parts[0], data)

        if data == EMPTY:
            data = empty_tree(self.repo)

        builder = self.repo.TreeBuilder(self.oid)

        if data is None:
            builder.remove(path)
        elif type(data) in (Tree, pygit2.Tree):
            builder.insert(key, data.oid, pygit2.GIT_FILEMODE_TREE)
        else:
            blob_id = self.repo.create_blob(data)
            builder.insert(key, blob_id, pygit2.GIT_FILEMODE_BLOB)

        tree = self.repo.get(builder.write())
        return Tree(self.repo, tree)

    def __contains__(self, path):
        return self.get(path, self) is not self

    def __iter__(self):
        return (e.name for e in self._tree)

    def keys(self):
        return list(self)

    def values(self):
        return [self[k] for k in self]

    def __len__(self):
        return sum(1 for _ in iter(self))

    def __eq__(self, other):
        if type(other) == type(self):
            return self.oid == other.oid
        return False

    def __repr__(self):
        return '<gitly.Tree @ %s>' % self.oid


def flatten_tree(tree, prefix=()):
    """ Flatten a tree into name -> entry pairs """
    for entry in tree._tree:
        name = prefix + (entry.name,)
        if entry.filemode == pygit2.GIT_FILEMODE_TREE:
            subtree = tree.subtree(entry.name)
            for item in flatten_tree(subtree, name):
                yield item
        else:
            yield (name, entry)


def dict_diff(dict1, dict2):
    """
    Combine a dictionary, discarding entries that are the same
    in both left and right
    """
    for key in set(dict1.keys() + dict2.keys()):
        item1 = dict1.get(key)
        item2 = dict2.get(key)
        if (item1 and item2 and item1.oid == item2.oid
           or item1 == item2):
            yield (key, (item1, item2))


def tree_changes(tree1, tree2):
    """ Iterate changes between 2 trees """
    return dict_diff(dict(flatten_tree(tree1)), dict(flatten_tree(tree2)))


def discover_head():
    repodir = pygit2.discover_repository('.')
    repo = pygit2.Repository(repodir)
    return Commit(repo, repo.head.peel())


class Branch(object):
    """ Mutable branch object """
    alice = pygit2.Signature('Alice Author', 'alice@authors.tld')
    cecil = pygit2.Signature('Cecil Committer', 'cecil@committers.tld')

    def __init__(self, repo, branch_name):
        self.ref_name = 'refs/heads/' + branch_name
        self.repo = repo
        try:
            ref = repo.lookup_reference(self.ref_name)
            _tree = ref.get_object().tree
        except (ValueError, KeyError):
            # The empty tree
            _tree = empty_tree(repo)
        self.tree = Tree(repo, _tree)

    @classmethod
    def discover(cls):
        repodir = pygit2.discover_repository('.')
        repo = pygit2.Repository(repodir)
        return cls(repo, repo.head.name)

    def __contains__(self, path):
        return path in self.tree

    def __getitem__(self, name):
        out = self.tree
        for part in name.split('/'):
            out = out.get(part)
        return out

    def get(self, path, default=Tree._ERROR):
        return self.tree.get(path, default)

    def __setitem__(self, path, value):
        self.tree = self.tree.set(path, value)

    def __delitem__(self, path):
        self[path] = None

    def commit(self, msg, author=alice, committer=cecil):
        try:
            ref = self.repo.lookup_reference(self.ref_name)
            parents = [ref.get_object().oid]
        except KeyError:
            parents = []
        self.repo.create_commit(self.ref_name, author, committer, msg,
                                self.tree._tree.oid, parents)

    def __repr__(self):
        return '<gitly.Branch @ %s>' % self.ref_name


# class LensedBranch(Branch):
#     def __init__(self, prefix, branch):
#         self.branch = branch
#         self.prefix = prefix
#         self.tree = branch[prefix]
#
#     def commit(self, *args, **kwargs):
#         self.branch[self.prefix] = self.tree
#         self.branch.commit(*args, **kwargs)
