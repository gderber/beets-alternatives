import sys
import os
import tempfile
import six
import shutil
from contextlib import contextmanager
from six import StringIO
from concurrent import futures
from unittest import TestCase

from mock import patch

import beets
from beets import logging
from beets import plugins
from beets import ui
from beets.library import Item

from beetsplug import alternatives
from beetsplug import convert


logging.getLogger('beets').propagate = True


class LogCapture(logging.Handler):

    def __init__(self):
        super(LogCapture, self).__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(six.text_type(record.msg))


@contextmanager
def capture_log(logger='beets'):
    capture = LogCapture()
    log = logging.getLogger(logger)
    log.addHandler(capture)
    try:
        yield capture.messages
    finally:
        log.removeHandler(capture)


@contextmanager
def capture_stdout():
    """Save stdout in a StringIO.

    >>> with capture_stdout() as output:
    ...     print('spam')
    ...
    >>> output.getvalue()
    'spam'
    """
    org = sys.stdout
    sys.stdout = capture = StringIO()
    if six.PY2:  # StringIO encoding attr isn't writable in python >= 3
        sys.stdout.encoding = 'utf-8'
    try:
        yield sys.stdout
    finally:
        sys.stdout = org
        print(capture.getvalue())


@contextmanager
def control_stdin(input=None):
    """Sends ``input`` to stdin.

    >>> with control_stdin('yes'):
    ...     input()
    'yes'
    """
    org = sys.stdin
    sys.stdin = StringIO(input)
    if six.PY2:  # StringIO encoding attr isn't writable in python >= 3
        sys.stdin.encoding = 'utf-8'
    try:
        yield sys.stdin
    finally:
        sys.stdin = org


def _convert_args(args):
    """Convert args to bytestrings for Python 2 and convert them to strings
       on Python 3.
    """
    for i, elem in enumerate(args):
        if six.PY2:
            if isinstance(elem, six.text_type):
                args[i] = elem.encode(util.arg_encoding())
        else:
            if isinstance(elem, bytes):
                args[i] = elem.decode(util.arg_encoding())

    return args


class Assertions(object):

    def assertFileTag(self, path, tag):
        self.assertIsFile(path)
        with open(path, 'rb') as f:
            f.seek(-5, os.SEEK_END)
            self.assertEqual(f.read(), tag)

    def assertNotFileTag(self, path, tag):
        self.assertIsFile(path)
        with open(path, 'rb') as f:
            f.seek(-5, os.SEEK_END)
            self.assertNotEqual(f.read(), tag)

    def assertIsFile(self, path):
        if not isinstance(path, unicode):
            path = unicode(path, 'utf8')
        self.assertTrue(os.path.isfile(path.encode('utf8')),
                        msg=u'Path is not a file: {0}'.format(path))

    def assertIsNotFile(self, path):
        if not isinstance(path, unicode):
            path = unicode(path, 'utf8')
        self.assertFalse(os.path.isfile(path.encode('utf8')),
                         msg=u'Path is a file: {0}'.format(path))

    def assertSymlink(self, link, target):
        self.assertTrue(os.path.islink(link),
                        msg=u'Path is not a symbolic link: {0}'.format(link))
        self.assertTrue(os.path.isfile(target),
                        msg=u'Path is not a file: {0}'.format(link))
        link_target = os.readlink(link)
        link_target = os.path.join(os.path.dirname(link), link_target)
        self.assertEqual(target, link_target)


class TestHelper(TestCase, Assertions):

    def setUp(self):
        patcher = patch('beetsplug.alternatives.Worker', new=MockedWorker)
        patcher.start()
        self.addCleanup(patcher.stop)

        self._tempdirs = []
        plugins._classes = set([alternatives.AlternativesPlugin,
                                convert.ConvertPlugin])
        self.setup_beets()

    def tearDown(self):
        self.unload_plugins()
        for tempdir in self._tempdirs:
            shutil.rmtree(tempdir)

    def mkdtemp(self):
        path = tempfile.mkdtemp()
        self._tempdirs.append(path)
        return path

    def setup_beets(self):
        self.addCleanup(self.teardown_beets)
        os.environ['BEETSDIR'] = self.mkdtemp()

        self.config = beets.config
        self.config.clear()
        self.config.read()

        self.config['plugins'] = []
        self.config['verbose'] = True
        self.config['ui']['color'] = False
        self.config['threaded'] = False
        self.config['import']['copy'] = False

        self.libdir = self.mkdtemp()
        self.config['directory'] = self.libdir

        self.lib = beets.library.Library(':memory:', self.libdir)
        self.fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures')

    def teardown_beets(self):
        del self.lib._connections
        if 'BEETSDIR' in os.environ:
            del os.environ['BEETSDIR']
        self.config.clear()
        beets.config.read(user=False, defaults=True)

    def set_paths_config(self, conf):
        self.lib.path_formats = conf.items()

    def unload_plugins(self):
        for plugin in plugins._classes:
            plugin.listeners = None
            plugins._classes = set()
            plugins._instances = {}

    def runcli(self, *args):
        # TODO mock stdin
        with capture_stdout() as out:
            try:
                ui._raw_main(_convert_args(list(args)), self.lib)
            except ui.UserError as u:
                # TODO remove this and handle exceptions in tests
                print(u.args[0])
        return out.getvalue()

    def lib_path(self, path):
        return os.path.join(self.libdir, path.replace('/', os.sep))

    def add_album(self, **kwargs):
        values = {
            'title': 'track 1',
            'artist': 'artist 1',
            'album': 'album 1',
            'format': 'mp3',
        }
        values.update(kwargs)
        ext = values.pop('format').lower()
        item = Item.from_path(os.path.join(self.fixture_dir, 'min.' + ext))
        item.add(self.lib)
        item.update(values)
        item.move(copy=True)
        item.write()
        album = self.lib.add_album([item])
        album.albumartist = item.artist
        album.store()
        return album

    def add_track(self, **kwargs):
        values = {
            'title': 'track 1',
            'artist': 'artist 1',
            'album': 'album 1',
        }
        values.update(kwargs)

        item = Item.from_path(os.path.join(self.fixture_dir, 'min.mp3'))
        item.add(self.lib)
        item.update(values)
        item.move(copy=True)
        item.write()
        return item

    def add_external_track(self, ext_name, **kwargs):
        kwargs[ext_name] = 'true'
        item = self.add_track(**kwargs)
        self.runcli('alt', 'update', ext_name)
        item.load()
        return item

    def add_external_album(self, ext_name, **kwargs):
        album = self.add_album(**kwargs)
        album[ext_name] = 'true'
        album.store()
        self.runcli('alt', 'update', ext_name)
        album.load()
        return album


class MockedWorker(alternatives.Worker):

    def __init__(self, fn, max_workers=None):
        self._tasks = set()
        self._fn = fn

    def submit(self, *args, **kwargs):
        fut = futures.Future()
        res = self._fn(*args, **kwargs)
        fut.set_result(res)
        # try:
        #     res = fn(*args, **kwargs)
        # except Exception as e:
        #     fut.set_exception(e)
        # else:
        #     fut.set_result(res)
        self._tasks.add(fut)
        return fut

    def shutdown(wait=True):
        pass
