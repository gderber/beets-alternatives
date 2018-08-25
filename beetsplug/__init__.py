# This file is part of beets.
# Copyright 2016, Adrian Sampson.
#
# Alternatives Plugin:
# Copyright (c) 2014 Thomas Scholtes
# Updates Copyright 2017-2018 __Fix Me__
#
# SmartAlternatives rewrite Copyright 2018, Geoff S Derber
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

#-----------------------------------------------------------------------
#
# Libraries
#
#-----------------------------------------------------------------------
# System Libraries
#import os.path
#import threading
#from concurrent import futures
import six

# 3rd Party Libraries


# Application Libraries
# System Library Overrides
# Other Application Libraries
#import beets
from beets import plugins
from beets import ui
from beets.library import Item, Album, parse_query_string
#from beets import util
#from beets import art

#from beets.ui import get_path_formats, input_yn, UserError, print_
#from beets.util import syspath, displayable_path, cpu_count, bytestring_path
#from beetsplug import convert

# Conditional Libraries

#-----------------------------------------------------------------------
#
# Global Variables
#
#-----------------------------------------------------------------------

#-----------------------------------------------------------------------
#
# Classes
#
# SmartAlternativesPlugin
# AlternativesCommand
# AlternativeFiles
# FLAC Files
# MP3 Files
# Symlink Files
# AAC Files
#
#-----------------------------------------------------------------------

#-----------------------------------------------------------------------
#
# Class SmartAlternativesPlugin
#
# This creates the actual plugin...
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class SmartAlternativesPlugin(plugins.BeetsPlugin):
    def __init__(self):
        super(SmartAlternativesPlugin, self).__init__()

        # Create the Config Options
        self.config.add({
            'auto': 'True',
            'alt_dir': '.',
            'alternatives': {},
        })

        self._matched_alternatives = None
        self._unmatched_alternatives = None

        # For later ...
        #if self.config['auto']:
        #    self.register_listener('database_change', self.db_change)


    #-------------------------------------------------------------------
    #
    # Function commands
    #
    # Create the subcommand and options for this plugin
    #
    # Inputs
    # ------
    #    @param: self
    #
    # Returns
    # -------
    #    @return: [alt_cmd]- Contains the parser information
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
    def commands(self):
        alt_cmd = ui.Subcommand('alternatives',
                                aliases=['alt'],
                                help='Manage alternative files')
        alt_cmd.parser.add_option(
            '-u', '--update', dest='update',
            action='store_true', default=False,
            help="I don't know what this does."
        )
        alt_cmd.parser.add_option(
            '-f', '--force', dest='force',
            action='store_true', default=False,
            help='re-download genre when already present'
        )
        # How do I allow mandatory 'name'
        #alt_cmd.parser.add_option('--name',
        #                          help="The name of the alt to update...")
        alt_cmd.func = self.update_cmd
        return [alt_cmd]

    #-------------------------------------------------------------------
    #
    # Function update_cmd
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: lib
    #    @param: options
    #
    # Returns
    # -------
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: UserError
    #
    #-------------------------------------------------------------------
    def update_cmd(self, lib, options, unk_option):
        self.build_queries()

        try:
            alt = self.alternative(lib)
        except Exception as e:
             raise Exception("Alternative collection '{0}' not found."
                            .format(e.args[0]))
        #alt.update(create=options.create)

    #-------------------------------------------------------------------
    #
    # Function build_queries
    #
    # Create the search query to identify which songs to make an
    # alternative directory structure for.
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: None (? How does that work ?)
    #
    # Raises
    # ------
    #    @raises: Exception (Pick / Make a better error code)
    #
    #-------------------------------------------------------------------
    def build_queries(self):
        """
        Instanciate queries for the alternatives.

        Each Alternate has 2 queries, one for items and one for albums. 
        We must also remember its name.
        _unmatched_playlists is a set of tuples (name, (q, q_sort), 
        (album_q, album_q_sort)).
        """
        self._unmatched_alternatives = set()
        self._matched_alternatives = set()

        for alternative in self.config['alternatives'].get(list):
            if 'name' not in alternative:
                self._log.warning("Alternative configuration is missing name")
                continue

            alt_data = (alternative['name'],)

            try:
                for key, Model, in (('query', Item),
                                    ('album_query', Album)):
                    qs = alternative.get(key)
                    if qs is None:
                        query_and_sort = None, None
                    elif isinstance(qs, six.string_types):
                        query_and_sort = parse_query_string(qs, Model)
                    elif len(qs) == 1:
                        query_and_sort = parse_query_string(qs[0], Model)
                    else:
                        # multiple queries and sorts
                        queries, sorts = zip(*(parse_query_string(q, Model)
                                               for q in qs))
                        query = OrQuery(queries)
                        final_sorts = []
                        for s in sorts:
                            if s:
                                if isinstance(s, MultipleSort):
                                    final_sorts += s.sorts
                                else:
                                    final_sorts.append(s)
                        if not final_sorts:
                            sort = None
                        elif len(final_sorts) == 1:
                            sort, = final_sorts
                        else:
                            sort = MultipleSort(final_sorts)
                        query_and_sort = query, sort

                    alt_data += (query_and_sort,)

            except Exception as exc:
                self._log.warning("invalid query in alternative {}: {}",
                                  alternative['name'], exc)
                continue

            self._unmatched_alternatives.add(alt_data)

    #-------------------------------------------------------------------
    #
    # Function alternative
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
    def alternative(self, lib):

        for alternative in self.config['alternatives'].get(list):
            if 'name' not in alternative:
                self._log.warning("Alternative configuration is missing name")
                continue

            alt_data = (alternative['name'],)
            for directory_data in alternative['directories']:
                directory = directory_data['directory']
                formats = []
                for format_ in directory_data['formats'].split(' '):
                    formats.append(format_)
                paths = directory_data['paths']
                print("Dir = ", directory)
                print("Formats = ", formats)
                print("Paths = ", paths)


                if 'directory' not in directory_data:
                    self._log.warning("Alternative configuration is missing directory")
                    continue

        return AlternativeFiles(self.config['alt_dir'], directory, formats, paths)


        #if conf['formats'].exists():
        #    fmt = conf['formats'].as_str()
        #    if fmt == u'link':
        #        return SymlinkView(self._log, name, lib, conf)
        #    else:
        #        return ExternalConvert(self._log, name, fmt.split(), lib, conf)
        #else:
        #    return External(self._log, name, lib, conf)


#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class AlternativeFiles(object):
    def __init__(self, alt_dir, directory, formats, paths):
        print("Fuck")

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class File(object):
    def __init__(self):
        print("Me")

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class MP3File(File):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class FLACFile(File):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class AACFile(File):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class APEFile(File):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class WAVFile(File):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class Program(object):
    def __init__(self):
        print("WTH")

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class LAMEProgram(Program):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class FFMPEGProgram(Program):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class MACProgram(Program):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class MPG321Program(Program):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class MPG123Program(Program):
    pass

#-----------------------------------------------------------------------
#
# Class AlternativeFiles
#
# Factory Class
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
class SOXProgram(Program):
    pass

#-----------------------------------------------------------------------
#
# Class External
#
# This creates the actual plugin...
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
#class External(object):

#    ADD = 1
#    REMOVE = 2
#    WRITE = 3
#    MOVE = 4
#    NOOP = 5
#    EMBED_ART = 6

#    def __init__(self, log, name, lib, config):
#        self._log = log
#        self.name = name
#        self.lib = lib
#        self.path_key = 'alt.{0}'.format(name)
#        self.parse_config(config)

    #-------------------------------------------------------------------
    #
    # Function parse_config
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def parse_config(self, config):
#        if 'paths' in config:
#            path_config = config['paths']
#        else:
#            path_config = beets.config['paths']
#        self.path_formats = get_path_formats(path_config)
#        query = config['query'].as_str()
#        self.query, _ = parse_query_string(query, Item)
#        self.removable = config.get(dict).get('removable', True)
#        if 'directory' in config:
#            dir = config['directory'].as_str()
#        else:
#            dir = self.name
#        dir = bytestring_path(dir)
#        if not os.path.isabs(syspath(dir)):
#            dir = os.path.join(self.lib.directory, dir)
#        self.directory = dir

    #-------------------------------------------------------------------
    #
    # Function match_item_action
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def matched_item_action(self, item):
#        path = self.get_path(item)
#        actions = []
#        if path and os.path.isfile(syspath(path)):
#            dest = self.destination(item)
#            if not util.samefile(path, dest):
#                actions.extend([self.MOVE, self.WRITE])
#            elif (os.path.getmtime(syspath(dest))
#                    < os.path.getmtime(syspath(item.path))):
#                actions.append(self.WRITE)
#            album = item.get_album()
#            if (album and album.artpath and
#                    (os.path.getmtime(syspath(path))
#                     < os.path.getmtime(syspath(album.artpath)))):
#                actions.append(self.EMBED_ART)
#        else:
#            actions.append(self.ADD)
#        return (item, actions)

    #-------------------------------------------------------------------
    #
    # Function items_action
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def items_actions(self):
#        matched_ids = set()
#        for album in self.lib.albums():
#            if self.query.match(album):
#                matched_items = album.items()
#                matched_ids.update(item.id for item in matched_items)
#
#        for item in self.lib.items():
#            if item.id in matched_ids or self.query.match(item):
#                yield self.matched_item_action(item)
#            elif self.get_path(item):
#                yield (item, [self.REMOVE])

    #-------------------------------------------------------------------
    #
    # Function ask_create
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def ask_create(self, create=None):
#        if not self.removable:
#            return True
#        if create is not None:
#            return create
#
#        msg = u"Collection at '{0}' does not exists. " \
#              "Maybe you forgot to mount it.\n" \
#              "Do you want to create the collection? (y/n)" \
#              .format(displayable_path(self.directory))
#        return input_yn(msg, require=True)

    #-------------------------------------------------------------------
    #
    # Function update
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def update(self, create=None):
#        if (not os.path.isdir(syspath(self.directory))
#                and not self.ask_create(create)):
#            print_(u'Skipping creation of {0}'
#                   .format(displayable_path(self.directory)))
#            return

#        converter = self.converter()
#        for (item, actions) in self.items_actions():
#            dest = self.destination(item)
#            path = self.get_path(item)
#            for action in actions:
#                if action == self.MOVE:
#                    print_(u'>{0} -> {1}'.format(displayable_path(path),
#                                                 displayable_path(dest)))
#                    util.mkdirall(dest)
#                    util.move(path, dest)
#                    util.prune_dirs(os.path.dirname(path), root=self.directory)
#                    self.set_path(item, dest)
#                    item.store()
#                    path = dest
#                elif action == self.WRITE:
#                    print_(u'*{0}'.format(displayable_path(path)))
#                    item.write(path=path)
#                elif action == self.EMBED_ART:
#                    print_(u'~{0}'.format(displayable_path(path)))
#                    self.embed_art(item, path)
#                elif action == self.ADD:
#                    print_(u'+{0}'.format(displayable_path(dest)))
#                    converter.submit(item)
#                elif action == self.REMOVE:
#                    print_(u'-{0}'.format(displayable_path(path)))
#                    self.remove_item(item)
#                    item.store()

#        for item, dest in converter.as_completed():
#            self.set_path(item, dest)
#            item.store()
#        converter.shutdown()

    #-------------------------------------------------------------------
    #
    # Function destination
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def destination(self, item):
#        return item.destination(basedir=self.directory,
#                                path_formats=self.path_formats)

    #-------------------------------------------------------------------
    #
    # Function set_path
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: item
    #    @param: path
    #
    # Returns
    # -------
    #    @return: item
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
#    def set_path(self, item, path):
#        item[self.path_key] = six.text_type(path, 'utf8')

    #-------------------------------------------------------------------
    #
    # Function get_path
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: item
    #
    # Returns
    # -------
    #    @return: item
    #    @return: None
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
 #   def get_path(self, item):
 #       try:
 #           return item[self.path_key].encode('utf8')
 #       except KeyError:
 #           return None

    #-------------------------------------------------------------------
    #
    # Function remove_item
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
 #   def remove_item(self, item):
 #       path = self.get_path(item)
 #       util.remove(path)
 #       util.prune_dirs(path, root=self.directory)
 #       del item[self.path_key]

    #-------------------------------------------------------------------
    #
    # Function converter
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
 #   def converter(self):
 #       def _convert(item):
 #           dest = self.destination(item)
 #           util.mkdirall(dest)
 #           util.copy(item.path, dest, replace=True)
 #           return item, dest
 #       return Worker(_convert)

    #-------------------------------------------------------------------
    #
    # Function embed_art
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: item
    #    @param: patch
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
#    def embed_art(self, item, path):
#        album = item.get_album()
#        if album and album.artpath:
#            self._log.debug("Embedding art from {} into {}".format(
#                displayable_path(album.artpath),
#                displayable_path(path)))
#            art.embed_item(self._log, item, album.artpath,
#                           itempath=path)

#-----------------------------------------------------------------------
#
# Class ExternalConvert
#
# This ...
#
# It is a sublcass of the ... class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
#class ExternalConvert(External):
#    def __init__(self, log, name, formats, lib, config):
#        super(ExternalConvert, self).__init__(log, name, lib, config)
#        convert_plugin = convert.ConvertPlugin()
#        self._encode = convert_plugin.encode
#        self._embed = convert_plugin.config['embed'].get(bool)
#        self.formats = [f.lower() for f in formats]
#        self.formats = [convert.ALIASES.get(f, f) for f in formats]
#        self.convert_cmd, self.ext = convert.get_format(self.formats[0])

    #-------------------------------------------------------------------
    #
    # Function converter
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def converter(self):
#        fs_lock = threading.Lock()

        #-------------------------------------------------------------------
        #
        # Function _convert
        #
        # ...
        #
        # Inputs
        # ------
        #    @param: self
        #    @param: name
        #    @param: lib
        #
        # Returns
        # -------
        #    @return: ...
        #    @return: ...
        #
        # Raises
        # ------
        #    @raises: KeyError
        #
        #-------------------------------------------------------------------
#        def _convert(item):
#            dest = self.destination(item)
#            with fs_lock:
#                util.mkdirall(dest)

#            if self.should_transcode(item):
#                self._encode(self.convert_cmd, item.path, dest)
#            else:
#                self._log.debug(u'copying {0}'.format(displayable_path(dest)))
#                util.copy(item.path, dest, replace=True)
#            if self._embed:
#                self.embed_art(item, dest)
#            return item, dest
#        return Worker(_convert)

    #-------------------------------------------------------------------
    #
    # Function destination
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def destination(self, item):
#        dest = super(ExternalConvert, self).destination(item)
#        if self.should_transcode(item):
#            return os.path.splitext(dest)[0] + b'.' + self.ext
#        else:
#            return dest

    #-------------------------------------------------------------------
    #
    # Function should_transcode
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: item
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def should_transcode(self, item):
#        return item.format.lower() not in self.formats


#-----------------------------------------------------------------------
#
# Class SymlinkView
#
# This creates the actual plugin...
#
# It is a sublcass of the BeetsPlugin class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
#class SymlinkView(External):
    #-------------------------------------------------------------------
    #
    # Function parse_config
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
#    def parse_config(self, config):
#        if 'query' not in config:
#            config['query'] = u''  # This is a TrueQuery()
#        super(SymlinkView, self).parse_config(config)

    #-------------------------------------------------------------------
    #
    # Function update
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: name
    #    @param: lib
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: KeyError
    #
    #-------------------------------------------------------------------
 #   def update(self, create=None):
 #       for (item, actions) in self.items_actions():
 #           dest = self.destination(item)
 #           path = self.get_path(item)
 #           for action in actions:
 #               if action == self.MOVE:
 #                   print_(u'>{0} -> {1}'.format(displayable_path(path),
 #                                                displayable_path(dest)))
 #                   self.remove_item(item)
 #                   self.create_symlink(item)
 #                   self.set_path(item, dest)
 #               elif action == self.ADD:
 #                   print_(u'+{0}'.format(displayable_path(dest)))
 #                   self.create_symlink(item)
 #                   self.set_path(item, dest)
 #               elif action == self.REMOVE:
 #                   print_(u'-{0}'.format(displayable_path(path)))
 #                   self.remove_item(item)
 #               else:
 #                   continue
 #               item.store()

    #-------------------------------------------------------------------
    #
    # Function create_symlink
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: item
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
#    def create_symlink(self, item):
#        dest = self.destination(item)
#        util.mkdirall(dest)
#        util.link(item.path, dest)

#-----------------------------------------------------------------------
#
# Class Worker
#
# This ...
#
# It is a sublcass of the ... class.
#
# Inputs
# ------
#    @param: ...
#
# Returns
# -------
#    @return: ...
#
# Raises
# ------
#    @raises: ...
#
#-----------------------------------------------------------------------
#class Worker(futures.ThreadPoolExecutor):
#    def __init__(self, fn, max_workers=None):
#        super(Worker, self).__init__(max_workers or cpu_count())
#        self._tasks = set()
#        self._fn = fn

    #-------------------------------------------------------------------
    #
    # Function submit
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #    @param: *args
    #    @param: **kwargs
    #
    # Returns
    # -------
    #    @return: fut
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
#    def submit(self, *args, **kwargs):
#        fut = super(Worker, self).submit(self._fn, *args, **kwargs)
#        self._tasks.add(fut)
#        return fut

    #-------------------------------------------------------------------
    #
    # Function as_completed
    #
    # ...
    #
    # Inputs
    # ------
    #    @param: self
    #
    # Returns
    # -------
    #    @return: ...
    #    @return: ...
    #
    # Raises
    # ------
    #    @raises: ...
    #
    #-------------------------------------------------------------------
#    def as_completed(self):
#        for f in futures.as_completed(self._tasks):
#            self._tasks.remove(f)
#            yield f.result()
