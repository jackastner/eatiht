"""
eatiht - Extract Article Text In HyperText documents

Written by Rodrigo Palacios

Note: for those unfamiliar with xpaths, think of them as file/folder
paths, where each "file/folder" is really just some HTML element.

Algorithm, dammit!:
Using a clever xpath expression that targets the immediate parents of
text nodes of a certain length N, one can get a list of parent nodes
which have, what we can consider as "ideal," text nodes (nodes that
have sentences).

For each text node, we "partition" the text node so that instead of the
parent node having the original text node as its lone child, the parent
now has P children; the partitioning method used is a REGEX sentence
split.

Finally, using now the *parents* of the the above mentioned parent
nodes as our sample, we create a frequency distribution measuring
the number of text node descendants of each parent. In other words,
We can find the xpath with the most number of text node descendants.
This output has shown to lead us to the main article in a webpage.
"""

import re
from collections import Counter
try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

from lxml import html
import requests


# This xpath expression effectively queries html text
# nodes that have a string-length greater than 20
TEXT_FINDER_XPATH = '//body//*[not(self::script or self::style or self::i or self::b or self::strong or self::span or self::a)]/text()[string-length(normalize-space()) > 20]/.. '
LEADING_XPATH = '//body//*[not(self::script or self::style or self::i or self::b or self::strong or self::span or self::a)]/text()[string-length(normalize-space()) > '
TO_PARENT = "]/.."

# REGEX patterns for catching bracketted numbers - as seen in wiki articles -
# and sentence splitters
bracket_pattern = re.compile('(\[\d*\])')

# http://stackoverflow.com/questions/8465335/a-regex-for-extracting-sentence-from-a-paragraph-in-python
sentence_token_pattern = re.compile(r"""
        # Split sentences on whitespace between them.
        (?:               # Group for two positive lookbehinds.
          (?<=[.!?])      # Either an end of sentence punct,
        | (?<=[.!?]['"])  # or end of sentence punct and quote.
        )                 # End group of two positive lookbehinds.
        (?<!  Mr\.   )    # Don't end sentence on "Mr."
        (?<!  Mrs\.  )    # Don't end sentence on "Mrs."
        (?<!  Jr\.   )    # Don't end sentence on "Jr."
        (?<!  Dr\.   )    # Don't end sentence on "Dr."
        (?<!  Prof\. )    # Don't end sentence on "Prof."
        (?<!  Sr\.   )    # Don't end sentence on "Sr."
        \s+               # Split on whitespace between sentences.
        """,
        re.IGNORECASE | re.VERBOSE)

sentence_ending = ['.', '"', '?', '!', "'"]


# TODO(?): turn to decorator
def build_text_finder(leading_xpath=TEXT_FINDER_XPATH,min_str_length=False):
    """ takes optional text-finding xpath (WARNING, only for those
    experienced with xpath expressions!) and min. string-length of text
    nodes. This returns the construction of default or custom xpath.
    """
    # this path is here for support older release
    if leading_xpath is TEXT_FINDER_XPATH and min_str_length is False:
        return leading_xpath

    # logically, one would like to experiment with only changing the
    # mininum string length param in original xpath, this allows that
    elif (leading_xpath is TEXT_FINDER_XPATH and
          isinstance(min_str_length,int)):
        return LEADING_XPATH + str(min_str_length) + TO_PARENT

    # if user supplied a full-on custom xpath, will likely break..
    elif leading_xpath and min_str_length is False:
        return leading_xpath

    # this path should only reach if user is VERY sure of the xpath,
    # will likely break..
    else:
        return leading_xpath + str(min_str_length) + TO_PARENT


def get_xpath_frequency_distribution(paths):
    """ Build and return a frequency distribution over xpath occurrences."""
    # "html/body/div/div/text" -> [ "html", "body", "div", "div", "text" ]
    splitpaths = [p.split('/') for p in paths]

    # get list of "parentpaths" by right-stripping off the last xpath-node, effectively
    # getting the parent path
    parentpaths = ['/'.join(p[:-1]) for p in splitpaths]

    # build frequency distribution
    parentpathsCounter = Counter(parentpaths)
    return parentpathsCounter.most_common()


def get_sentence_xpath_tuples(filename_url_or_filelike, xpath_to_text=TEXT_FINDER_XPATH):
    """Given a url, file, or filelike object and xpath, this function will
    download, parse, then iterate though queried text-nodes. From the
    resulting text-nodes, extract a list of (text, exact-xpath) tuples.
    """
    try:
        parsed_html = html.parse(filename_url_or_filelike, html.HTMLParser())

    except IOError as e:
        # use requests as a workaround for problems in some
        # sites requiring cookies like nytimes.com
        # http://stackoverflow.com/questions/15148376/urllib2-returning-no-html
        try:
            #if isinstance(filename_url_or_filelike,basestring):
            page = requests.get(filename_url_or_filelike)
        except Exception as e:
            raise e
        # http://lxml.de/parsing.html
        parsed_html = html.parse(BytesIO(page.content), html.HTMLParser())

    xpath_finder = parsed_html.getroot().getroottree().getpath

    nodes_with_text = parsed_html.xpath(xpath_to_text)

    sent_xpath_pairs = [
        ('\n\n' + s, xpath_finder(n)) if e == 0     # hard-code paragraph breaks (there has to be a better way)
        else (s, xpath_finder(n))
        for n in nodes_with_text
        for e, s in enumerate(sentence_token_pattern.split(bracket_pattern.sub('', ''.join(n.xpath('.//text()')))))
        if s.endswith(tuple(sentence_ending))
        ]

    return sent_xpath_pairs


def extract(filename_url_or_filelike, xpath_to_text = TEXT_FINDER_XPATH,
            min_str_length=False):
    """Wrapper function for extracting the main article from html document.

    A crappy flowchart/state-diagram:
    start: url[,xpath[,min_str_len] -> xpaths of text-nodes ->
    -> frequency distribution -> argmax( freq. dist. ) =
    = likely xpath leading to article's content
    """

    # adding new feature for xpath building
    xpath_to_text = build_text_finder(xpath_to_text,min_str_length)

    sent_xpath_pairs = get_sentence_xpath_tuples(filename_url_or_filelike,
                                                 xpath_to_text)

    # The following comprehension was moved to its own variable from
    # get_xpath_freq... argument for readability
    xpaths = [x for (s, x) in sent_xpath_pairs]
    max_path = get_xpath_frequency_distribution(xpaths)[0]

    article_text = ' '.join([s for (s, x) in sent_xpath_pairs if max_path[0] in x])

    # starting from index 2 because of the two extra newlines in front
    return article_text[2:]
