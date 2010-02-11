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
def fetch(k, table, root, add=""):
    cursor = root.cursor()
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
                                    db='mythconverg',
                                    use_unicode=True)

        # Create the template loader
        self.loader = TemplateLoader(
            os.path.join(os.path.dirname(__file__), 'templates'),
            auto_reload=True)

    def cursor(self):
        try:
            cursor = self.conn.cursor()
        except OperationalError:
            self.conn = MySQLdb.connect(host,
                                    user=user,
                                    passwd=password,
                                    db='mythconverg',
                                    use_unicode=True)
            cursor = self.conn.cursor()
        return cursor
            
    @cherrypy.expose
    def rss(self, recgroup, title):
        import urllib
        import os
        cursor = self.cursor()
        data = fetch(['recgroup','title','subtitle',
                      'description','basename', 'chanid',
                      'starttime',
                      ("DATE_FORMAT(endtime, '%m/%e')",'endtime')],
                     'recorded', self, "ORDER BY starttime")
        results = []
        for d in data:
            if d['recgroup']==recgroup and d['title']==title:
		if d['subtitle']==None or len(d['subtitle'])==0:
			d['subtitle'] = "<No Sub-Title Given>"
                fname = "/data/video/library/"+d['basename']
                d['length'] = os.stat(fname).st_size
                results.append(d)
        media_url = "file:///data/video/library/"+\
            self.share
        context = {'name': "name",
                   'recgroup': recgroup,
                   'title': title,
                   'media': media_url,
                   'results': results }
        tmpl = self.loader.load('subgroup_rss.xml')
        gen = tmpl.generate(**context)
        return gen.render('xml', doctype='xhtml')

    @cherrypy.expose
    def bytitle(self, recgroup, title):
        import urllib
        cursor = self.cursor()
        data = fetch(['recgroup','title','subtitle',
                      'description','basename', 'chanid',
                      'starttime',
                      ("DATE_FORMAT(endtime, '%m/%e')",'endtime')],
                     'recorded', self, "ORDER BY starttime")
        results = []
        for d in data:
            if d['recgroup']==recgroup and d['title']==title:
		if d['subtitle']==None or len(d['subtitle'])==0:
			d['subtitle'] = "<No Sub-Title Given>"
                results.append(d)
        media_url = "file:///opt/sybhttpd/localhost.drives/NETWORK_SHARE/"+\
            self.share
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
        cursor = self.cursor()
        data = fetch(['recgroup','title'], 'recorded', self)
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

    def _findshow(self, chanid, year, month, day, hour, minute):
        import MythTV
        import sys

        sys.argv = ["fake", "--host", "localhost"]
        con = MythTV.MythTV()
        rs = con.getRecordings()
        for r in rs:
            st = r.starttime
            if r.chanid==int(chanid) and st.year==int(year) and \
               st.month==int(month) and st.day==int(day) and \
               st.hour==int(hour) and st.minute==int(minute):
               return (con, r)
        return (None, None)
        
    @cherrypy.expose
    def prompt(self, chanid, year, month, day, hour, minute):
        (con, r) = self._findshow(chanid, year, month, day, hour, minute)
        tmpl = self.loader.load('delete_show.html')
        context = {'year': year, 'month': month, 'day': day,
                   'hour': hour, 'minute': minute,
                   'chanid': chanid, 'title': r.title}
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

    @cherrypy.expose
    def delete(self, chanid, year, month, day, hour, minute):
        (con, r) = self._findshow(chanid, year, month, day, hour, minute)
        con.deleteRecording(r)
        raise cherrypy.HTTPRedirect( "/" )


    @cherrypy.expose
    def index(self):
        import urllib
        tmpl = self.loader.load('index.html')
        cursor = self.cursor()
        data = fetch(['recgroup'], 'recorded', self)
        namemap = {}
        for d in data:
            namemap[d['recgroup']] = urllib.quote(d['recgroup'])
        
        context = {'title': "MythTV Groups",
                   'namemap': namemap }
        gen = tmpl.generate(**context)
        return gen.render('html', doctype='html')

def config_server():
    data = {}

    # This is all to configure the CherryPy server
    static_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), 'static'))
    print "static dir = ", static_dir
    base_config = {
            'tools.encode.on': True,
            'cherrypy.engine.SIGHUP': None,
            'cherrypy.engine.SIGTERM': None,
            'tools.decode.on': True,
            'tools.trailing_slash.on': True,
            'log.screen': True,
            'log.error_file': 'server.log',
            'tools.staticdir.root': static_dir,
            '/media': { 'tools.staticdir.on': True,
                        'tools.staticdir.dir': 'media' },
            'global': { 'server.socket_host': '0.0.0.0',
		        'server.socket_port': 8080 }
    }

    conf = {'/': { 'tools.staticdir.root': static_dir},
            '/media': { 'tools.staticdir.on': True,
                        'tools.staticdir.dir': 'media' }}

    cherrypy.config.update(base_config)

    return conf
    
# This function gets called from Apache
def setup_server():
    config_server()

    cherrypy.engine.SIGHUP = None
    cherrypy.engine.SIGTERM = None

    cherrypy.tree.mount(Root())

# This function gets invoked if you run this from the command line
# and CherryPy supplies the server handling
def main():
    conf = config_server()

    # Create the root application object
    root = Root()

    cherrypy.quickstart(root, '/', config=conf)

if __name__ == '__main__':
    main()
