#!/usr/bin/env python

import cherrypy
import os, sys
from genshi.template import TemplateLoader
import MySQLdb

loader = TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'templates'),
    auto_reload=True)

def fetch(k, table, conn):
    cursor = conn.cursor()
    cmd = "SELECT %s FROM %s" % (",".join(k), table)
    cursor.execute(cmd)
    entries = []
    for row in cursor.fetchall():
        entries.append(stitch(row, k))
    cursor.close()
    return entries
    
def stitch(t, k):
    ret = {}
    for e in zip(t,k):
        ret[e[1]] = e[0]
    return ret
    

class Root(object):
    def __init__(self, user, password):
        conn = MySQLdb.connect('127.0.0.1',
                               user=user,
                               passwd=password,
                               db='mythconverg')
        entries = fetch(['title','subtitle','description',
                         'recgroup','basename'], 'recorded', conn)
        conn.close()
        self.entries = entries
        self.groups = {}
        for e in entries:
            # First, make sure we have a group
            # for each recording group
            recgroup = e['recgroup']
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
            imgname = e['basename']+".png"
            if os.path.exists(os.path.join(path, imgname)):
                e['imgname'] = imgname
            else:
                e['imgname'] = None
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
        tmpl = loader.load('group_contents.html')
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
        tmpl = loader.load('subgroup_contents.html')
        context = {'id': id, 'sid': sid,
                   'gname': key,
                   'group': group,
                   'shows': shows,
                   'title': title,
                   'media': "file:///opt/sybhttpd/localhost.drives/NETWORK_SHARE/library/",
                   'root': self }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def index(self):
        tmpl = loader.load('index.html')
        context = {'title': "MythTV Groups",
                   'root': self }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

path = '/video/library'
def main():
    import ConfigParser
    data = {}

    options = ConfigParser.ConfigParser()
    options.readfp(open('mythpch.cfg'))
    user = options.get("global", "user")
    password = options.get("global", "password")

    print "Using MySQL user '%s'." % (user,)

    base_config = {
            'tools.encode.on': True,
            'tools.decode.on': True,
            'tools.trailing_slash.on': True,
            'log.screen': True,
            'log.error_file': 'server.log',
            'tools.staticdir.root': '/video'
    }

    conf = {'/': { 'tools.staticdir.root': '/video'},
            '/media': { 'tools.staticdir.on': True,
                        'tools.staticdir.dir': 'library' }}


    cherrypy.config.update(base_config)

    cherrypy.quickstart(Root(user, password), '/', config=conf)

if __name__ == '__main__':
    main()
