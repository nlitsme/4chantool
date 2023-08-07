import urllib.request
import urllib.parse
import http.cookiejar
import re
import json
import sys
import html
import datetime
import os
import os.path

import http.client

from collections import defaultdict
g_stats = defaultdict(int)

def optq(x):
    """ optionally quote a string """
    return repr(x) if type(x) == str and x.find(' ')>=0 else x

def htmlstrip(html):
    """ strip html from 4chan's messages """
    if not html: return html
    html = html.replace('<br>', "\n")
    # wbr, s, a, span
    html = re.sub('<\w+>', '', html)
    html = re.sub('</\w+>', '', html)
    # quote, mu-r, mu-b, mu-s
    html = re.sub(r'<span class="[^"]+">', '', html)
    # quotelink
    html = re.sub(r'<a[^<>]+>', '', html)

    html = html.replace("&gt;", ">")
    html = html.replace("&lt;", "<")
    html = html.replace("&quot;", "\"")
    html = html.replace("&#39;", "\'")
    html = html.replace("&#039;", "\'")
    html = html.replace("&amp;", "&")

    return html

class FileCache:
    """
    create backup of 4chan messages on disk.


    TODO: for the catalog, threads and archive files,
    add a 'once a day' new path, with date in the filename.
    """
    def __init__(self, basepath):
        self.basepath = basepath
    def exists(self, path):
        return os.path.exists(self.makepath(path))
    def retrieve(self, path):
        with open(self.makepath(path), "rb") as fh:
            return fh.read()
    def store(self, path, data):
        path = self.makepath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            return fh.write(data)

    def makepath(self, path):
        if path.find("/thread/") == -1:
            now = datetime.date.today()
            path = path.replace(".json", "-%s.json" % now)
        return os.path.join(self.basepath, path)

def addCookie(cj, name, value, domain):
    """
    helper to add a cookie to the http-cookie-jar
    """
    cj.set_cookie(http.cookiejar.Cookie(
            version=0, name=name, value=value,
            port=None, port_specified=False,
            domain=domain, domain_specified=True, domain_initial_dot=True,
            path="/", path_specified=True,
            secure=False, expires=None, discard=False,
            comment=None, comment_url=None, rest={}))


class FourChan:
    """
"https://a.4cdn.org/boards.json"
"https://a.4cdn.org/{board}/catalog.json"
"https://a.4cdn.org/{board}/threads.json"
"https://a.4cdn.org/{board}/archive.json"

"https://a.4cdn.org/{board}/thread/{no}.json"
"https://a.4cdn.org/{board}/thread/{no}{tail?"-tail":""}.json"

"https://i.4cdn.org/{tim}{ext}"
    """
    def __init__(self, args):
        self.args = args
        self.cache = FileCache(self.args.cachedir)
        cj = http.cookiejar.CookieJar()
        addCookie(cj, '4chan_disclaimer', '1', '4chan.com')
        addCookie(cj, 'cf_clearance', args.cfclearance, 'find.4channel.org')

        handlers = [urllib.request.HTTPCookieProcessor(cj)]
        if args.debug:
            handlers.append(urllib.request.HTTPSHandler(debuglevel=1))
        self.opener = urllib.request.build_opener(*handlers)

    def httpreq(self, url, data=None):
        """
        Does GET or POST request to youtube.
        """
        hdrs = {
            "User-Agent": self.args.cfuseragent,
        }
        req = urllib.request.Request(url, headers=hdrs)

        kwargs = dict(timeout=30)
        if data:
            kwargs["data"] = data

        response = self.opener.open(req, **kwargs)
        return response.read()

    def getjson(self, path):
        if not self.cache.exists(path):
            try:
                jstext = self.httpreq("https://a.4cdn.org/" + path)
            except Exception as e:
                print("ERROR: %s : %s" % (path, e))
                return

            self.cache.store(path, jstext)
        else:
            jstext = self.cache.retrieve(path)

        return json.loads(jstext)

    def list_boards(self):
        js = self.getjson("boards.json")

        boardbools = {
            "code_tags":"code",
            "country_flags":"flags",
            "forced_anon":"anon",
            "is_archived":"arch",
            "math_tags":"math",
            "oekaki":"oe",
            "require_subject":"subject",
            "sjis_tags":"sjis",
            "spoilers":"spoil",
            "text_only":"txt",
            "troll_flags":"troll",
            "user_ids":"uid",
            "webm_audio":"webm",
        }

        boardints = [
            ("pages", "pages", 3),
            ("per_page", "perpage", 3),
            ("bump_limit", "bumps", 4),
            ("image_limit", "image", 4),
            ("max_comment_chars", "cmtsize", 5),
            ("max_filesize", "filesize", 9),
            ("max_webm_duration", "webmtime", 4),
            ("max_webm_filesize", "webmsize", 8),
            ("custom_spoilers", "spoil", 2),
            ("min_image_height", "imgh", 5),
            ("min_image_width", "imgw", 5),
        ]
        def boardflags(b):
            l = []
            for k, v in boardbools.items():
                if b.get(k):
                    l.append(v)
            return ",".join(l)
        def boardquota(b):
            l = []
            for k, a, w in boardints:
                q = b.get(k, 0)
                l.append(str(q).rjust(w))
            return "".join(l)

        for b in js.get("boards"):
            # board, title, meta_description
            # cooldowns: { threads replies images }

            print("%-5s %-30s %-55s %s" % (b["board"], boardflags(b), boardquota(b), b["title"]))


    def print_post(self, p, indent=""):
        print("--")
        print("%sFrom: %s" % (indent, htmlstrip(p.get("name", "??"))))
        print("%sDate: %s" % (indent, datetime.datetime.fromtimestamp(p["time"])))
        sub = p.get("sub")
        if sub:
            print("%sSubject: %s" % (indent, htmlstrip(sub),))
        filename = p.get("filename")
        if filename:
            wh = ""
            if p.get("w"):
                wh = "  %dx%d" % (p["w"], p["h"])
            print("%sFilename: (%d%s) <%s> %s" % (indent, p.get("fsize", 0), wh, p.get("tim"), optq(htmlstrip(filename)+p.get("ext", ""))))

        info = []
        infoitems = [
            ("unique_ips",  "#IP"),
            ("omitted_images", "skippedimgs"),
            ("omitted_posts", "skippedposts"),
            ("bumplimit", "maxbump"),
            ("imagelimit", "maximg"),
            ("images", "imgs"),
            ("replies", "replies"),
            ("resto", "resto"),
            ("tag", "tag"),
        ]
        known = [
            "name", "time", "sub", "fsize", "tim", "ext", "filename", "w", "h", "com",
            "last_replies", "unique_ips", "omitted_images", "omitted_posts", "bumplimit",
            "imagelimit", "images", "replies", "resto", "tag"
        ]
        for k, v in infoitems:
            x = p.get(k)
            if x is not None:
                info.append("%s=%s" % (v, x))
        for k, v in p.items():
            if k not in known:
                info.append("%s=%s" % (k, optq(v)))

        if info:
            print("Info: %s" % (", ".join(info)))

        print()
        com = htmlstrip(p.get("com"))
        if com:
            if indent:
                com = indent + com.replace("\n", "\n" + indent)
            print(com)
            print()
        last_replies = p.get("last_replies")
        if last_replies :
            # for catalog only
            for r in last_replies:
                print("--------")
                self.print_post(r, indent="    ")

        global g_stats
        for k in p.keys():
            g_stats[k] += 1


    def list_catalog(self, board):
        js = self.getjson("%s/catalog.json" % board)
        if not js:
            return

        for page in js:
            # page, threads
            for t in page["threads"]:
                # no, last_modified, replies, now, name, com, filename, ext, ..., last_replies
                self.print_post(t)

    def list_thread(self, board, no):
        first = True
        js = self.getjson("%s/thread/%d.json" % (board, no))
        if not js:
            return

        for p in js.get("posts"):
            if first:
                self.print_post(p)
            else:
                self.print_post(p, "    ")
            first = False
            print("--------")

    def list_threads(self, board):
        js = self.getjson("%s/threads.json" % board)
        if not js:
            return
        for page in js:
            # page, threads
            for t in page["threads"]:
                # no, last_modified, replies
                self.list_thread(board, t["no"])

    def list_archive(self, board):
        js = self.getjson("%s/archive.json" % board)
        if not js:
            return
        for tid in js:
            self.list_thread(board, tid)

    def find(self, keywords, args):
        q = { 'q':keywords }
        if args.board:
            q['b'] = args.board
        o = 0
        while o<=100:
            jsontext = self.httpreq("https://find.4channel.org/api?" + urllib.parse.urlencode(q))
            js = json.loads(jsontext)
            if extra := ", ".join(f"{k}={optq(v)}" for k, v in js.items() if k not in ('threads',)):
                print("---- query:", extra)

            for t in js.get('threads'):
                yield t

            o += 10
            q['o'] = o

    def print_thread(self, thd):
        print(f"-- /{thd.get('board')}/ -- {thd.get('thread')}")
        if extra := ", ".join(f"{k}={optq(v)}" for k, v in thd.items() if k not in ('board', 'thread', 'posts')):
            print("--", extra)
        for post in thd.get('posts'):
            self.print_post(post)


def loadconfig(cfgfile):
    """
    Load config from .4chanrc
    """
    with open(cfgfile, 'r') as fh:
        txt = fh.read()
    txt = "[root]\n" + txt
    import configparser
    config = configparser.ConfigParser()
    config.read_string(txt)

    return config


def applyconfig(cfg, args):
    """
    Apply the configuration read from .4chanrc to the `args` dictionary,
    which is used to configure everything.
    """
    def add(argname, cfgname):
        if not getattr(args, argname) and cfg.has_option('cloudfare', cfgname):
            setattr(args, argname, cfg.get('cloudfare', cfgname))
    add("cfuseragent", "useragent")
    add("cfclearance", "clearance")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='List 4chan comments')
    parser.add_argument('--debug', '-d', action='store_true', help=argparse.SUPPRESS) # 'print all intermediate steps'
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--boards', '-l', action='store_true', help='list boards')
    parser.add_argument('--board', '-b', type=str, help='specify board')
    parser.add_argument('--cachedir', '-c', type=str, help='Specify a different cache directory', default='a.4cdn.org')

    parser.add_argument('--threads', action='store_true', help='list threads for board')
    parser.add_argument('--catalog', action='store_true', help='list threads from catalog for board')
    parser.add_argument('--archive', action='store_true', help='list threads from archive for board')
    parser.add_argument('--stats', action='store_true', help='show post keyword stats')
    parser.add_argument('--search', type=str, help='forum search')
    parser.add_argument('--config', default='~/.4chanrc', help=argparse.SUPPRESS)
    parser.add_argument('--cfuseragent', type=str, help=argparse.SUPPRESS)
    parser.add_argument('--cfclearance', type=str, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.config.startswith("~/"):
        import os
        homedir = os.environ['HOME']
        args.config = args.config.replace("~", homedir)

    try:
        cfg = loadconfig(args.config)

        applyconfig(cfg, args)
    except Exception as e:
        print("Error in config: %s" % e)


    fc = FourChan(args)
    if args.boards:
        fc.list_boards()
    if args.catalog:
        if not args.board:
            print("Must specify a board with --threads")
            return
        print("======== all cataloged threads ========")
        fc.list_catalog(args.board)

    if args.archive:
        if not args.board:
            print("Must specify a board with --threads")
            return
        print("======== all archived threads ========")
        fc.list_archive(args.board)

    if args.threads:
        if not args.board:
            print("Must specify a board with --threads")
            return
        print("======== all current threads ========")
        fc.list_threads(args.board)

    if args.stats:
        print("== stats")
        for k, v in g_stats.items():
            print("%6d - %s" % (v, k))

    if args.search:
        print("== search", args.search)
        for thd in fc.find(args.search, args):
            fc.print_thread(thd)

if __name__ == '__main__':
    main()


