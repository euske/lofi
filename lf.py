#!/usr/bin/env python
import sys
import urllib.request
import html.parser
import re

USER_AGENT = 'bw browser'

RMSP = re.compile(r'\s+')

IMMED_TAGS = {
    'meta', 'hr',
}

def rmsp(s):
    return RMSP.sub(' ', s)

class Element:

    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        return

    def __repr__(self):
        return f'<{self.__class__.__name__} tag={self.tag} attrs={self.attrs} children={len(self.children)}>'

    def append(self, element):
        if isinstance(element, str) and self.children and isinstance(self.children[-1], str):
            self.children[-1] += element
        else:
            self.children.append(element)
        return

    def str(self):
        attrs = ''.join( f' {k}={v!r}' for (k,v) in self.attrs.items() )
        children = ''.join( e.str() if isinstance(e, Element) else repr(e) for e in self.children )
        return f'<{self.tag}{attrs}>{children}</{self.tag}>'


class DOMParser(html.parser.HTMLParser):

    def __init__(self):
        html.parser.HTMLParser.__init__(self)
        self._cur = Element('root', {})
        self._stack = []
        return

    def close(self):
        html.parser.HTMLParser.close(self)
        while self._stack:
            self._cur = self._stack.pop()
        return self._cur

    def handle_data(self, data):
        #print(f'data: {data!r}')
        self._cur.append(data)
        return

    def handle_starttag(self, tag, attrs):
        #print(f'start: {tag} {attrs}')
        cur = Element(tag, dict(attrs))
        self._cur.append(cur)
        if tag not in IMMED_TAGS:
            self._stack.append(self._cur)
            self._cur = cur
        return

    def handle_endtag(self, tag):
        #print(f'end: {tag}')
        if tag in IMMED_TAGS: return
        while self._stack:
            cur = self._cur
            self._cur = self._stack.pop()
            if cur.tag == tag: break
        return

    def handle_startendtag(self, tag, attrs):
        #print(f'startend: {tag} {attrs}')
        self._cur.append(Element(tag, dict(attrs)))
        return

def main(argv):
    args = argv[1:]
    url = args.pop(0)
    opener = urllib.request.FancyURLopener()
    opener.addheader('User-Agent', USER_AGENT)
    fp = opener.open(url)
    parser = DOMParser()
    for line in fp:
        parser.feed(line.decode('utf-8'))
    root = parser.close()
    def walk(e, indent=''):
        assert isinstance(e, Element)
        print(indent+f'{e.tag}:')
        indent += ' '
        for c in e.children:
            if isinstance(c, Element):
                walk(c, indent)
            else:
                c = c.strip()
                if c:
                    print(indent+rmsp(c))
    walk(root)
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv))
