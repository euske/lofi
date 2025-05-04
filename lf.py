#!/usr/bin/env python
import sys
import urllib.request
import html.parser
import re
import ctypes

LIBC = ctypes.cdll.LoadLibrary('libc.so.6')
def wcwidth(c):
    return LIBC.wcwidth(ord(c))

RMSP = re.compile(r'\s+')

def rmsp(s):
    return RMSP.sub(' ', s)

TAGS_IMMED = {
    'meta', 'link', 'hr', 'br', 'input',
    'img', 'object',
}

TAGS_AUTOCLOSE = {
    'p', 'li', 'dt', 'dd', 'th', 'td',
}

TAGS_IGNORE = {
    'script', 'style',
}

TAGS_VISUAL = {
    'div', 'span',
}

class Element:

    def __init__(self, tag, attrs, finish=False):
        self.tag = tag
        self.attrs = attrs
        self.finish = finish
        self.children = []
        return

    def __repr__(self):
        return f'<{self.__class__.__name__} tag={self.tag} attrs={self.attrs} children={len(self.children)}>'

    def get(self, name):
        return self.attrs.get(name)

    def append(self, element):
        assert not self.finish
        if isinstance(element, str) and self.children and isinstance(self.children[-1], str):
            self.children[-1] += element
        else:
            self.children.append(element)
        return

    def str(self):
        attrs = ''.join( f' {k}={v!r}' for (k,v) in self.attrs.items() )
        children = ''.join( e.str() if isinstance(e, Element) else repr(e) for e in self.children )
        return f'<{self.tag}{attrs}>{children}</{self.tag}>'

class Content:

    def __init__(self, element, children):
        self.element = element
        self.children = children
        return


class DOMParser(html.parser.HTMLParser):

    def __init__(self):
        html.parser.HTMLParser.__init__(self)
        self._stack = [ Element('root', {}) ]
        return

    def close(self):
        html.parser.HTMLParser.close(self)
        while self._stack:
            cur = self._stack.pop()
        return cur

    def close_tag(self, tag):
        #print('close_tag', tag, [ e.tag for e in self._stack ])
        i = len(self._stack)
        while 0 < i:
            i -= 1
            if self._stack[i].tag == tag: break
        else:
            return
        for e in self._stack[i:]:
            e.finish = True
        self._stack = self._stack[:i]
        return

    def handle_data(self, data):
        #print(f'data: {data!r}')
        self._stack[-1].append(data)
        return

    def handle_starttag(self, tag, attrs):
        #print(f'start: {tag} {attrs}')
        if tag in TAGS_AUTOCLOSE:
            self.close_tag(tag)
        cur = Element(tag, dict(attrs))
        self._stack[-1].append(cur)
        if tag not in TAGS_IMMED:
            self._stack.append(cur)
        return

    def handle_endtag(self, tag):
        #print(f'end: {tag}')
        if tag in TAGS_IMMED: return
        self.close_tag(tag)
        return

    def handle_startendtag(self, tag, attrs):
        #print(f'startend: {tag} {attrs}')
        self._stack[-1].append(Element(tag, dict(attrs), finish=True))
        return

def main(argv):
    user_agent = 'lofi browser'
    max_width = 80
    args = argv[1:]
    url = args.pop(0)
    opener = urllib.request.FancyURLopener()
    opener.addheader('User-Agent', user_agent)
    fp = opener.open(url)
    parser = DOMParser()
    for line in fp:
        parser.feed(line.decode('utf-8'))
    root = parser.close()

    def convert(e):
        assert isinstance(e, Element)
        if e.tag in TAGS_IGNORE: return None
        if e.tag == 'input' and e.get('type') == 'hidden': return None
        children = []
        for c in e.children:
            if isinstance(c, Element):
                content = convert(c)
                if content is not None:
                    children.append(content)
            else:
                text = c.strip()
                if text:
                    children.append(rmsp(text))
        if not children: return None
        if e.tag in TAGS_VISUAL and len(children) == 1:
            return children[0]
        if e.tag == 'br':
            return '\n'
        return Content(e, children)

    def print_fold(lines, indent, width):
        rows = []
        for line in lines:
            w = 0
            i0 = 0
            for (i,c) in enumerate(line):
                wc = wcwidth(c)
                if width < w+wc:
                    rows.append(line[i0:i])
                    w = 0
                    i0 = i
                w += wc
            rows.append(line[i0:])
        for row in rows:
            print(' '*indent + row)
        return

    def display(e, indent=0, bol=True):
        if isinstance(e, Content):
            if bol:
                print(' '*indent, end='')
            indent += 1
            if len(e.children) == 1 and isinstance(e.children[0], Content):
                print(f'<{e.element.tag}>:', end=' ')
                display(e.children[0], indent, False)
            else:
                print(f'<{e.element.tag}>:')
                for c in e.children:
                    display(c, indent, True)
        else:
            lines = e.split('\n')
            print_fold(lines, indent, max_width - indent)
        return

    content = convert(root)
    display(content)
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv))
