#!/usr/bin/env python3
import sys
import urllib.parse
import urllib.request
import html.parser
import re
import os.path
import tty
import termios

WIDE = re.compile('[\u1100-\u11ff\u231a-\u231b\u2329-\u232a\u23e9-\u23ec\u23f0\u23f3\u25fd-\u25fe\u2614-\u2615\u2630-\u2637\u2648-\u2653\u267f\u268a-\u268f\u2693\u26a1\u26aa-\u26ab\u26bd-\u26be\u26c4-\u26c5\u26ce\u26d4\u26ea\u26f2-\u26f3\u26f5\u26fa\u26fd\u2705\u270a-\u270b\u2728\u274c\u274e\u2753-\u2755\u2757\u2795-\u2797\u27b0\u27bf\u2b1b-\u2b1c\u2b50\u2b55\u2e80-\u303e\u3041-\ua4cf\ua960-\ua982\uac00-\udfff\uf900-\ufaff\ufe10-\ufe6f\uff01-\uff60\uffe0-\uffe7]')
def iswide(c):
    return WIDE.match(c)

CJK = re.compile('[\u2e80-\u303e\u3041-\ua4cf\ua960-\ua982\uac00-\udfff]')
def iscjk(c):
    return CJK.match(c)

STDIN = sys.stdin.fileno()
def getkey():
    attrs = tty.setcbreak(STDIN)
    try:
        key = os.read(STDIN, 10)
    finally:
        termios.tcsetattr(STDIN, termios.TCSADRAIN, attrs)
    return key


# https://gist.github.com/fnky/458719343aabd01cfb17a3a4f7296797
class Ansi:

    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    INVERT = '\033[7m'

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

    CLEAR = '\033[K'

    @classmethod
    def move(klass, dy=0, col=0):
        if 0 < dy:
            s = f'\033[{dy}E'
        elif dy < 0:
            s = f'\033[{-dy}F'
        else:
            s = ''
        if col:
            s += f'\033[{col+1}G'
        return s


class Tokenizer:

    PAREN_OPEN = frozenset('[({"\'「『［（｛【”’')
    PAREN_CLOSE = frozenset('])}"\'」』］）｝】”’')
    PUNCT = frozenset('-.,:;!?、。．，：；！？')

    def __init__(self):
        return

    def feed(self, seq):
        self.seq = seq
        self.tokens = []
        self.weight = 0
        self.tokenstart = 0
        (i,state) = (0, self.start)
        while i < len(seq):
            (i, state) = state(i, seq[i])
        self.endtoken(len(seq))
        return (self.tokens, self.weight)

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
            self.weight += 1
            if iscjk(c):
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

    def add(self, text, wc=None):
        if text.isspace():
            if 0 < self.w:
                self.blank = True
            return
        if wc is None:
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


class ElementNode:

    def __init__(self, element, children, weight):
        self.tag = element.tag
        self.attrs = element.attrs
        self.children = children
        self.weight = weight
        self.parent = None
        self.siblings = [self]
        self.open = False
        return

    def __repr__(self):
        return f'<ElementNode: {self.tag} ({self.weight})>'

    def path(self):
        seq = []
        node = self
        while node is not None:
            seq.append(node)
            node = node.parent
        return seq

    def scan(self):
        siblings = []
        for c in self.children:
            if isinstance(c, ElementNode):
                c.parent = self
                c.siblings = siblings
                siblings.append(c)
                c.scan()
        return

class StartTag:

    def __init__(self, element):
        self.tag = element.tag
        self.attrs = element.attrs
        return

    def __repr__(self):
        return f'<StartTag: {self.tag} {self.attrs}>'

class EndTag:

    def __init__(self, element):
        self.tag = element.tag
        return

    def __repr__(self):
        return f'<EndTag: {self.tag}>'

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

def filter_content(seq):
    return [ s for s in seq if not isinstance(s, str) or not s.isspace() ]

class Element:

    def __init__(self, tag, attrs, finish=False):
        self.tag = tag
        self.attrs = attrs
        self.finish = finish
        self.children = []
        return

    def __repr__(self):
        return f'<{self.__class__.__name__} tag={self.tag} attrs={self.attrs} children={len(self.children)}>'

    def get(self, name, default=None):
        return self.attrs.get(name, default)

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

    def convert(self):
        if self.tag in TAGS_IGNORE: return ([], 0)
        if self.tag == 'input' and self.get('type') == 'hidden': return ([], 0)
        if self.tag in TAGS_IMMED: return ([self], 0)
        children = []
        weight = 0
        if self.tag in TAGS_INLINE:
            children.append(StartTag(self))
        for c in self.children:
            if isinstance(c, Element):
                (nodes, wc) = c.convert()
                children.extend(nodes)
                weight += wc
            elif isinstance(c, str):
                (tokens, wc) = Tokenizer().feed(c)
                children.extend(tokens)
                weight += wc
        if not children: return ([], 0)
        contents = filter_content(children)
        if self.tag in TAGS_TRANSPARENT and len(contents) == 1:
            return (contents, weight)
        if self.tag in TAGS_INLINE:
            children.append(EndTag(self))
            return (children, weight)
        return ([ElementNode(self, children, weight)], weight)


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


class Canvas:

    def __init__(self, fp, max_width):
        self.fp = fp
        self.max_width = max_width
        self.lineno = 0
        self.maxline = 0
        self.nodepos = {}
        return

    def moveto(self, node):
        if node in self.nodepos:
            (lineno, col) = self.nodepos[node]
            self.fp.write(Ansi.move(lineno - self.lineno, col))
            self.fp.flush()
            self.lineno = lineno
        return

    def print(self, text):
        assert '\n' not in text
        self.fp.write(text)
        return

    def newline(self):
        self.fp.write(Ansi.CLEAR + '\n')
        self.lineno += 1
        self.maxline = max(self.maxline, self.lineno)
        return

    def flush(self):
        for i in range(self.lineno, self.maxline):
            self.fp.write(Ansi.CLEAR + '\n')
        (self.lineno, self.maxline) = (self.maxline, self.lineno)
        return

    def render_texts(self, nodes, indent=0):
        layouter = TextLayouter(self.max_width - indent)
        for node in nodes:
            if isinstance(node, StartTag):
                if node.tag == 'a':
                    layouter.add(Ansi.UNDERLINE, 0)
                    layouter.add('[')
                elif node.tag in ('b', 'strong'):
                    layouter.add(Ansi.BOLD, 0)
            elif isinstance(node, EndTag):
                if node.tag == 'a':
                    layouter.add(']')
                    layouter.add(Ansi.RESET, 0)
                elif node.tag in ('b', 'strong'):
                    layouter.add(Ansi.RESET, 0)
            elif isinstance(node, Element):
                if node.tag == 'br':
                    layouter.flush(force=True)
                elif node.tag == 'img':
                    alt = node.get('alt', 'IMG')
                    layouter.add(f'<{alt}>')
                else:
                    layouter.add(f'<{node.tag}>')
            else:
                assert isinstance(node, str), node
                layouter.add(node)
        layouter.flush()

        for tokens in layouter.rows:
            self.print(' '*indent + ''.join(tokens))
            self.newline()
        return

    def render(self, node, path=(), indent=0, bol=True):
        assert isinstance(node, ElementNode)
        open = node.open or (node in path)
        if bol:
            self.nodepos[node] = (self.lineno, indent)
            self.print(' '*indent)
            if open:
                self.print('+ ')
            else:
                self.print('- ')
        indent += 1
        # contents = filter_content(node.children)
        # if len(contents) == 1 and isinstance(contents[0], ElementNode):
        #     self.print(f'<{node.tag}>: ')
        #     self.render(contents[0], indent, False)
        #     return
        self.print(f'<{node.tag}>:')
        self.newline()
        if open:
            texts = []
            for n in node.children:
                if isinstance(n, ElementNode):
                    if texts:
                        self.render_texts(texts, indent=indent)
                    self.render(n, path, indent, True)
                    texts = []
                else:
                    texts.append(n)
            if texts:
                self.render_texts(texts, indent=indent)
        return

KEYMAP = {
    b'q': 'quit',
    b'\033': 'quit',
    b' ': 'open',
    b'\n': 'open',
    b'\r': 'open',
    b'k': 'up',
    b'\x1b[A': 'up',
    b'j': 'down',
    b'\x1b[B': 'down',
    b'l': 'right',
    b'\x1b[C': 'right',
    b'h': 'left',
    b'\x1b[D': 'left',
}

def main(argv):
    user_agent = 'lofi browser'
    max_width = 80
    args = argv[1:]
    url = args.pop(0)
    if os.path.exists(url):
        url = f'file://{os.path.abspath(url)}'
    else:
        res = urllib.parse.urlparse(url)
        if not res.scheme:
            url = f'http://{url}'
    canvas = Canvas(sys.stdout, max_width)
    # open url
    req = urllib.request.Request(url)
    req.add_header('User-Agent', user_agent)
    fp = urllib.request.urlopen(req)
    # parse html
    parser = DOMParser()
    for line in fp:
        parser.feed(line.decode('utf-8'))
    root = parser.close()
    # convert html -> elements
    (content, _) = root.convert()
    assert len(content) == 1
    root = content[0]
    root.scan()
    # event loop
    current = root
    while True:
        canvas.moveto(root)
        canvas.render(root, path=current.path())
        canvas.flush()
        canvas.moveto(current)
        key = getkey()
        cmd = KEYMAP.get(key)
        if cmd == 'quit':
            break
        elif cmd == 'open':
            current.open = not current.open
        elif cmd == 'down':
            siblings = current.siblings
            i = siblings.index(current)
            i = (i+1) % len(siblings)
            current = siblings[i]
        elif cmd == 'up':
            siblings = current.siblings
            i = siblings.index(current)
            i = (i+len(siblings)-1) % len(siblings)
            current = siblings[i]
        elif cmd == 'left':
            if current.parent is not None:
                current = current.parent
        elif cmd == 'right':
            children = [ c for c in current.children if isinstance(c, ElementNode) ]
            if children:
                current = children[0]
        else:
            print(key)
    return 0

if __name__ == '__main__': sys.exit(main(sys.argv))
