import os
import os.path
import unittest
import shutil

import pygit2

from gitly import Tree, empty_tree


TESTER = pygit2.Signature('Ted Tester', 'ted@authors.tld')

TEST_REF_NAME = 'refs/head/test'


class TestTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_dir = os.path.join(os.path.dirname(__file__),
                                    'build', 'test', 'repo')
        if os.path.exists(cls.repo_dir):
            shutil.rmtree(cls.repo_dir)
        os.makedirs(cls.repo_dir)
        cls.repo = pygit2.init_repository(cls.repo_dir, bare=True)

    def setUp(self):
        empty = empty_tree(self.repo)
        if TEST_REF_NAME in self.repo.listall_references():
            self.repo.lookup_reference(TEST_REF_NAME).delete()
        commit = self.repo.create_commit(TEST_REF_NAME,
                                         TESTER, TESTER, 'msg', empty.oid, [])

    def test_init_empty_tree(self):
        tree = Tree(self.repo)
        self.assertEqual('4b825dc642cb6eb9a060e54bf8d69288fbee4904',
                         str(tree.oid))

    def test_tree_set(self):
        tree = Tree(self.repo).set('a', 'b')
        self.assertEqual('00264970afd30838f2a3b17376e05f8ca03b658b',
                         str(tree.oid))


    def test_init_some_tree(self):
        tree = Tree(self.repo).set('a', 'a')
        newtree = Tree(self.repo, tree._tree)
        self.assertEqual('b39954843ff6e09ec3aa2b942938c30c6bd1629e',
                         str(newtree.oid))

    def test_set_subdir(self):
        tree = (Tree(self.repo)
                .set('a/b/c/d', '1')
                .set('a/c/d/e', '2')
                .set('a/c/b/d', '3'))
        self.assertEqual({'a': {'b': {'c': '1'}, 'c': {'b': '3', 'd': '2'}}},
                         dump_tree(tree))


def dump_tree(val):
    if type(val) == Tree:
        return {k: dump_tree(val[k]) for k in sorted(val)}
    return val


if __name__ == '__main__':
    unittest.main()

