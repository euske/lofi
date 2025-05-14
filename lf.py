#!/usr/bin/env python
import sys
import urllib.request
import html.parser
import re

WIDE = re.compile('[\u1100-\u11ff\u231a-\u231b\u2329-\u232a\u23e9-\u23ec\u23f0\u23f3\u25fd-\u25fe\u2614-\u2615\u2630-\u2637\u2648-\u2653\u267f\u268a-\u268f\u2693\u26a1\u26aa-\u26ab\u26bd-\u26be\u26c4-\u26c5\u26ce\u26d4\u26ea\u26f2-\u26f3\u26f5\u26fa\u26fd\u2705\u270a-\u270b\u2728\u274c\u274e\u2753-\u2755\u2757\u2795-\u2797\u27b0\u27bf\u2b1b-\u2b1c\u2b50\u2b55\u2e80-\u303e\u3041-\ua4cf\ua960-\ua982\uac00-\udfff\uf900-\ufaff\ufe10-\ufe6f\uff01-\uff60\uffe0-\uffe7]')
def iswide(c):
    return WIDE.match(c)

class Tokenizer:

    PAREN_OPEN = '[({"\'「『［（｛【”’'
    PAREN_CLOSE = '])}"\'」』］）｝】”’'
    PUNCT = '-.,:;!?、。：；！？'

    def __init__(self):
        return

    def feed(self, s):
        self.seq = s
        self.tokens = []
        self.tokenstart = 0
        (i,state) = (0, self.start)
        while i < len(s):
            (i, state) = state(i, s[i])
        self.endtoken(len(s))
        return self.tokens

    def endtoken(self, i):
        if self.tokenstart < i:
            token = self.seq[self.tokenstart:i]
            if isinstance(token, list):
                self.tokens.extend(token)
            else:
                self.tokens.append(token)
            self.tokenstart = i
        return

    def start(self, i, c):
        if isinstance(c, str) and c in self.PAREN_OPEN:
            return (i, self.token_start)
        elif isinstance(c, str) and c.isspace():
            return (i, self.blank)
        elif isinstance(c, str) and c.isalnum():
            return (i, self.word)
        else:
            self.endtoken(i)
            self.endtoken(i+1)
            return (i+1, self.start)

    def token_start(self, i, c):
        if isinstance(c, str) and c in self.PAREN_OPEN:
            return (i+1, self.token_start)
        else:
            return (i, self.word)

    def word(self, i, c):
        if isinstance(c, str) and c.isalnum():
            if iswide(c):
                self.endtoken(i+1)
                return (i+1, self.token_end)
            else:
                return (i+1, self.word)
        else:
            return (i, self.token_end)

    def token_end(self, i, c):
        if isinstance(c, str) and (c in self.PAREN_CLOSE or c in self.PUNCT):
            return (i+1, self.token_end)
        else:
            self.endtoken(i)
            return (i, self.start)

    def blank(self, i, c):
        if isinstance(c, str) and c.isspace():
            return (i+1, self.blank)
        else:
            self.endtoken(i)
            return (i, self.start)

class TextLayouter:

    def __init__(self, width):
        self.width = width
        self.rows = []
        self.tokens = []
        self.w = 0
        self.blank = False
        return

    def flush(self, force=False):
        if force or self.tokens:
            self.rows.append(self.tokens)
        self.blank = False
        self.w = 0
        self.tokens = []
        return

    def add(self, text):
        if text.isspace():
            if 0 < self.w:
                self.blank = True
            return
        wc = sum( 2 if iswide(c) else 1 for c in text )
        if self.width < self.w+wc:
            if self.tokens:
                self.rows.append(self.tokens)
            self.tokens = []
            self.w = 0
        elif self.blank:
            if 0 < self.w:
                self.tokens.append(' ')
        self.blank = False
        self.tokens.append(text)
        self.w += wc
        return


TAGS_IMMED = {
    'meta', 'link', 'hr', 'br', 'input',
    'img', 'object',
}

TAGS_PARAGRAPH = {
    'p', 'li', 'dt', 'dd', 'th', 'td',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
}

TAGS_IGNORE = {
    'script', 'style',
}

TAGS_INLINE = {
    'a', 'abbr', 'b', 'bdi', 'bdo',
    'cite', 'code', 'em', 'i', 'kbd',
    'mark', 'q', 'ruby', 's', 'small',
    'strong', 'sub', 'sup', 'tt', 'u',
}

TAGS_TRANSPARENT = {
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

class ElementNode:

    def __init__(self, element, children):
        self.tag = element.tag
        self.attrs = element.attrs
        self.children = children
        return

class StartTag:

    def __init__(self, element):
        self.tag = element.tag
        self.attrs = element.attrs
        return

class EndTag:

    def __init__(self, element):
        self.tag = element.tag
        self.attrs = element.attrs
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

    def close_tag(self, tags):
        #print('close_tag', tag, [ e.tag for e in self._stack ])
        i = len(self._stack)
        while 0 < i:
            i -= 1
            if self._stack[i].tag in tags: break
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
        if tag in TAGS_PARAGRAPH:
            self.close_tag(TAGS_PARAGRAPH)
        cur = Element(tag, dict(attrs))
        self._stack[-1].append(cur)
        if tag not in TAGS_IMMED:
            self._stack.append(cur)
        return

    def handle_endtag(self, tag):
        #print(f'end: {tag}')
        if tag in TAGS_IMMED: return
        self.close_tag({tag})
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
        if e.tag in TAGS_IGNORE: return []
        if e.tag == 'input' and e.get('type') == 'hidden': return []
        if e.tag == 'br': return [e]
        children = []
        if e.tag in TAGS_INLINE:
            children.append(StartTag(e))
        for c in e.children:
            if isinstance(c, Element):
                nodes = convert(c)
                children.extend(nodes)
            elif isinstance(c, str):
                children.append(c)
        if not children: return []
        if e.tag in TAGS_TRANSPARENT and len(children) == 1:
            return children[:1]
        if e.tag in TAGS_INLINE:
            children.append(EndTag(e))
            return children
        return [ElementNode(e, children)]

    def display_texts(nodes, indent=0):
        layouter = TextLayouter(max_width - indent)
        for node in nodes:
            if isinstance(node, StartTag):
                layouter.add('[')
            elif isinstance(node, EndTag):
                layouter.add(']')
            elif isinstance(node, Element):
                layouter.flush(force=True)
            else:
                for token in Tokenizer().feed(node):
                    assert isinstance(token, str), token
                    layouter.add(token)
        layouter.flush()
        for tokens in layouter.rows:
            print(' '*indent, ''.join(tokens))
        return

    def display(node, indent=0, bol=True):
        assert isinstance(node, ElementNode)
        if bol:
            print(' '*indent, end='')
        indent += 1
        if len(node.children) == 1 and isinstance(node.children[0], ElementNode):
            print(f'<{node.tag}>:', end=' ')
            display(node.children[0], indent, False)
        else:
            print(f'<{node.tag}>:')
            texts = []
            for n in node.children:
                if isinstance(n, ElementNode):
                    if texts:
                        display_texts(texts, indent=indent)
                    display(n, indent, True)
                    texts = []
                else:
                    texts.append(n)
            if texts:
                display_texts(texts, indent=indent)
        return

    content = convert(root)
    assert len(content) == 1
    display(content[0])
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv))
