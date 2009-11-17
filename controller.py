#!/usr/bin/env python

# Import required modules
import cherrypy
import os, sys
from genshi.template import TemplateLoader
import MySQLdb

# This is just a little utility function
# that queries the DB for specific
# fields and then returns the result
# in a dictionary
def fetch(k, table, conn):
    cursor = conn.cursor()
    cmd = "SELECT %s FROM %s" % (",".join(k), table)
    cursor.execute(cmd)
    entries = []
    for row in cursor.fetchall():
        entries.append(stitch(row, k))
    cursor.close()
    return entries

# This is just a utility routine used by the
# fetch function    
def stitch(t, k):
    ret = {}
    for e in zip(t,k):
        ret[e[1]] = e[0]
    return ret
    
# This is a class to represent the web site.
class Root(object):
    def __init__(self):
        import ConfigParser
        import urllib

        # Open configuration file
        conf_file = os.path.join(os.path.dirname(__file__), 'mythpch.cfg')
        options = ConfigParser.ConfigParser()
        options.readfp(open(conf_file))

        # Extract out select options
        host = options.get("mysql", "host")
        user = options.get("mysql", "user")
        password = options.get("mysql", "password")
        self.share = options.get("samba", "share")

        # Connect to the SQL database
        self.conn = MySQLdb.connect(host,
                                    user=user,
                                    passwd=password,
                                    db='mythconverg')

        # Create the template loader
        self.loader = TemplateLoader(
            os.path.join(os.path.dirname(__file__), 'templates'),
            auto_reload=True)

        # Load MySQL data.  This is a serious limitation in this
        # version since the data is then static from that point
        # on.  :-(
        entries = fetch(['title','subtitle','description',
                         'recgroup','basename'], 'recorded', self.conn)
        self.entries = entries
        self.groups = {}
        for e in entries:
            # First, make sure we have a group
            # for each recording group
            recgroup = urllib.quote(e['recgroup'])
            if not recgroup in self.groups:
                self.groups[recgroup] = {'id': str(len(self.groups)+1),
                                         'titles': {}}
            group = self.groups[recgroup]
            titles = group['titles']
            # Get the subgroup of shows
            title = e['title']
            # Check to see if there is already a list of shows
            # with a given title
            if not title in titles:
                titles[title] = {'id': str(len(titles)+1),
                                 'showlist': []}
            show = titles[title]
            showlist = show['showlist']
            showlist.append(e)

    def _getgroup(self, id):
        group = None
        key = None
        for g in self.groups:
            if self.groups[g]['id']==id:
                key = g
                group = self.groups[g]
        return (key, group)

    def _getshows(self, sid, group):
        shows = None
        title = None
        titles = group['titles']
        for show in titles:
            if titles[show]['id']==sid:
                shows = titles[show]['showlist']
                title = show
        return (title, shows)

    @cherrypy.expose
    def group(self, id):
        (key, group) = self._getgroup(id)
        tmpl = self.loader.load('group_contents.html')
        context = {'id': id,
                   'name': key,
                   'group': group,
                   'root': self }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def subgroup(self, id, sid):
        (key, group) = self._getgroup(id)
        (title, shows) = self._getshows(sid, group)
        tmpl = self.loader.load('subgroup_contents.html')
        media_url = "file:///opt/sybhttpd/localhost.drives/NETWORK_SHARE/%s" % (self.share,)
        context = {'id': id, 'sid': sid,
                   'gname': key,
                   'group': group,
                   'shows': shows,
                   'title': title,
                   'media': media_url,
                   'root': self }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def bytitle(self, recgroup, title):
        import urllib
        cursor = self.conn.cursor()
        data = fetch(['recgroup','title','subtitle','description','basename'],
                     'recorded', self.conn)
        print "data = ", data
        results = []
        for d in data:
            if d['recgroup']==recgroup and d['title']==title:
                results.append(d)
        print "results = ", results
        media_url = "file:///opt/sybhttpd/localhost.drives/NETWORK_SHARE/%s" % (self.share,)
        context = {'name': "name",
                   'recgroup': recgroup,
                   'title': title,
                   'media': media_url,
                   'results': results }
        tmpl = self.loader.load('subgroup_contents.html')
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def recgroup(self, name):
        import urllib
        cursor = self.conn.cursor()
        data = fetch(['recgroup','title'], 'recorded', self.conn)
        print "data = ", data
        results = {}
        for d in data:
            if d['recgroup']==name:
                results[d['title']] = urllib.quote(d['title'])
        print "results = ", results
        context = {'name': "name",
                   'recgroup': urllib.quote(name),
                   'results': results }
        tmpl = self.loader.load('group_contents.html')
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def index2(self):
        tmpl = self.loader.load('index.html')
        context = {'title': "MythTV Groups",
                   'root': self }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def index(self):
        import urllib
        tmpl = self.loader.load('index.html')
        cursor = self.conn.cursor()
        data = fetch(['recgroup'], 'recorded', self.conn)
        namemap = {}
        for d in data:
            namemap[d['recgroup']] = urllib.quote(d['recgroup'])
        
        context = {'title': "MythTV Groups",
                   'namemap': namemap }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

def main():
    data = {}

    # This is all to configure the CherryPy server
    static_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'static'))
    base_config = {
            'tools.encode.on': True,
            'tools.decode.on': True,
            'tools.trailing_slash.on': True,
            'log.screen': True,
            'log.error_file': 'server.log',
            'tools.staticdir.root': static_dir
    }

    conf = {'/': { 'tools.staticdir.root': static_dir},
            '/media': { 'tools.staticdir.on': True,
                        'tools.staticdir.dir': 'media' }}

    # Create the root application object
    root = Root()

    cherrypy.config.update(base_config)

    cherrypy.quickstart(root, '/', config=conf)

if __name__ == '__main__':
    main()
