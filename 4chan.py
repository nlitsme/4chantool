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

class FileCache:
    """
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
        cj.set_cookie(http.cookiejar.Cookie(version=0, name='4chan_disclaimer', value='1', port='80', port_specified='80', domain='4chan.com', domain_specified=None, domain_initial_dot=None, path='/', path_specified=None, secure=False, expires=False, discard='', comment=None, comment_url=None, rest=None))
        handlers = [urllib.request.HTTPCookieProcessor(cj)]
        if args.debug:
            handlers.append(urllib.request.HTTPSHandler(debuglevel=1))
        self.opener = urllib.request.build_opener(*handlers)

    def httpreq(self, url, data=None):
        """
        Does GET or POST request to youtube.
        """
        req = urllib.request.Request(url)

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
        print("%sFrom: %s" % (indent, p.get("name", "??")))
        print("%sDate: %s" % (indent, datetime.datetime.fromtimestamp(p["time"])))
        sub = p.get("sub")
        if sub:
            print("%sSubject: %s" % (indent, sub,))
        filename = p.get("filename")
        if filename:
            wh = ""
            if p.get("w"):
                wh = "  %dx%d" % (p["w"], p["h"])
            print("%sFilename: (%d%s) <%s> %s%s" % (indent, p.get("fsize", 0), wh, p.get("tim"), filename, p.get("ext", "")))

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
        for k, v in infoitems:
            x = p.get(k)
            if x is not None:
                info.append("%s=%s" % (v, x))

        print("Info: %s" % (", ".join(info)))

        print()
        com = p.get("com")
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

def main():
    import argparse
    parser = argparse.ArgumentParser(description='List 4chan comments')
    parser.add_argument('--debug', '-d', action='store_true', help='print all intermediate steps')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--boards', '-l', action='store_true', help='list boards')
    parser.add_argument('--board', '-b', type=str, help='specify board')
    parser.add_argument('--cachedir', '-c', type=str, help='Specify a different cache directory', default='a.4cdn.org')

    parser.add_argument('--threads', action='store_true', help='list threads for board')
    parser.add_argument('--catalog', action='store_true', help='list threads from catalog for board')
    parser.add_argument('--archive', action='store_true', help='list threads from archive for board')
    parser.add_argument('--stats', action='store_true', help='show post keyword stats')
    args = parser.parse_args()

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

if __name__ == '__main__':
    main()


