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
def fetch(k, table, conn, add=""):
    cursor = conn.cursor()
    fields = []
    names = []
    for name in k:
        if type(name)==tuple:
            fields.append(name[0])
            names.append(name[1])
        else:
            fields.append(name)
            names.append(name)
    cmd = "SELECT %s FROM %s %s" % (",".join(fields), table, add)
    cursor.execute(cmd)
    entries = []
    for row in cursor.fetchall():
        entries.append(stitch(row, names))
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

    @cherrypy.expose
    def bytitle(self, recgroup, title):
        import urllib
        cursor = self.conn.cursor()
        data = fetch(['recgroup','title','subtitle',
                      'description','basename',
                      ("DATE_FORMAT(starttime, '%m/%e')",'starttime')],
                     'recorded', self.conn, "ORDER BY starttime")
        results = []
        for d in data:
            if d['recgroup']==recgroup and d['title']==title:
                results.append(d)
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
        results = {}
        counts = {}
        for d in data:
            if d['recgroup']==name:
                results[d['title']] = urllib.quote(d['title'])
            if not d['title'] in counts:
                counts[d['title']] = 0
            counts[d['title']] = counts[d['title']] + 1
        context = {'name': name,
                   'recgroup': urllib.quote(name),
                   'counts': counts, 
                   'results': results }
        tmpl = self.loader.load('group_contents.html')
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
