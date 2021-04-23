#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""A minimal module for writing gpx of Symbian (Nokia) SportsTracker file.

   Use of lxml is recommended, though a fallback to ElementTree is implemented.
"""
import sys
try:
    import lxml.etree as mod_etree
    USE_LXML = True
except ImportError: # Fallback to built-in ElementTree.
    USE_LXML = False
    from io import BytesIO
    try:
        import xml.etree.cElementTree as mod_etree
    except ImportError:
        try:
            import xml.etree.ElementTree as mod_etree
        except ImportError:
            print('Failed to import ElementTree.')
            sys.exit(1)


NS_GPX = 'http://www.topografix.com/GPX/1/1'
NS_GPXTPX = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v2'
NS_GPXX = 'http://www.garmin.com/xmlschemas/GpxExtensions/v3'
NS_XSI = 'http://www.w3.org/2001/XMLSchema-instance'
SCHEMALOCATION = (
    'http://www.topografix.com/GPX/1/1' ' '
    'http://www.topografix.com/GPX/1/1/gpx.xsd' ' '
    'http://www.garmin.com/xmlschemas/GpxExtensions/v3' ' '
    'http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd' ' '
    'http://www.garmin.com/xmlschemas/TrackPointExtension/v2' ' '
    'http://www8.garmin.com/xmlschemas/TrackPointExtensionv2.xsd')
if USE_LXML:
    NSMAP = {None:NS_GPX, 'gpxtpx':NS_GPXTPX, 'gpxx':NS_GPXX, 'xsi':NS_XSI}
else:
    mod_etree.register_namespace('', NS_GPX)
    mod_etree.register_namespace('gpxtpx', NS_GPXTPX)
    mod_etree.register_namespace('gpxx', NS_GPXX)
    mod_etree.register_namespace('xsi', NS_XSI)


def make_str(s): # A modified function of https://github.com/tkrajina/gpxpy.
    """Converts a str, unicode or float object into a str type."""
    if isinstance(s, float):
        result = str(s)
        if 'e' not in result:
            return result
        # Scientific notation is illegal in GPX 1.1.
        result = format(s, '.10f').rstrip('0')
        return result + '0' if result.endswith('.', -1) else result
    return str(s)

def format_time(datetime):
    return datetime.isoformat().replace('+00:00', 'Z')

def _pretty_print(current, parent=None, index=-1, depth=0):
    """Pretty print for built-in ElementTree, copied from Stack Overflow.

       https://stackoverflow.com/questions/28813876/
    """
    for i, node in enumerate(current):
        _pretty_print(node, current, i, depth + 1)
    if parent is not None:
        if index == 0:
            parent.text = '\n' + ('  ' * depth)
        else:
            parent[index - 1].tail = '\n' + ('  ' * depth)
        if index == len(parent) - 1:
            current.tail = '\n' + ('  ' * (depth - 1))

class Gpx(object):
    """GPX related stuff.  Topografix trkpt/rtept & Garmin gpxtpx are supported.

       A complex gpx consisting of multiple trkseg/rte is not supported.
    """
    def __init__(self, is_track=True):
        (self.metadata, self.summary) = (None, ) * 2
        self.is_track = is_track
        self.make_root()
        if is_track:
            self.make_trkseg()
        else:
            self.make_rte()

    def make_root(self):
        """Supported version of GPX is 1.1."""
        if USE_LXML:
            self.root = mod_etree.Element('gpx', nsmap=NSMAP)
        else:
            self.root = mod_etree.Element('{' f'{NS_GPX}' '}' 'gpx')
        self.root.set('{' f'{NS_XSI}' '}' 'schemaLocation', SCHEMALOCATION)
        self.root.set('version', '1.1')
        self.root.set(
            'creator', 'mini_gpx.py -- '
            'https://github.com/ekspla/Read-Symbian-SportsTracker-file')

    def make_trkseg(self):
        """Makes a trkseg to append trkpt."""
        if USE_LXML:
            self.trkseg = mod_etree.Element('trkseg', nsmap=NSMAP)
        else:
            self.trkseg = mod_etree.Element('{' f'{NS_GPX}' '}' 'trkseg')

    def make_rte(self):
        """Makes a rte to append rtept."""
        if USE_LXML:
            self.rte = mod_etree.Element('rte', nsmap=NSMAP)
        else:
            self.rte = mod_etree.Element('{' f'{NS_GPX}' '}' 'rte')

    def to_xml(self):
        """Serializes the root after appending trkseg, rte, metadata, etc.

        Returns:
            utf-8 bytes (gpx xml).
        """
        if self.metadata is not None:
            self.root.append(self.metadata)

        if self.is_track:
            trk = mod_etree.SubElement(self.root, 'trk')
            for child in self.summary:
                trk.append(child)
            trk.append(self.trkseg)

        else: # Route.  The other type, e.g. waypoint, is not supported.
            rte = mod_etree.SubElement(self.root, 'rte')
            for child in self.summary:
                rte.append(child)
            for rtept in self.rte:
                rte.append(rtept)

        if USE_LXML:
            return mod_etree.tostring(
                self.root, encoding='UTF-8', pretty_print=True, 
                doctype='<?xml version="1.0" encoding="UTF-8"?>')
        else:
            _pretty_print(self.root)
            f = BytesIO()
            tree = mod_etree.ElementTree(self.root)
            tree.write(f, encoding='UTF-8', xml_declaration=True) 
            return f.getvalue()

    def add_metadata(self, name='', description='', author='', time=None):
        """Adds a few field in metadata as a short reference of the track/route.
        """
        if name or description or author or time:
            self.metadata = mod_etree.Element('metadata')
            if name:
                mod_etree.SubElement(self.metadata, 'name').text = name
            if description:
                mod_etree.SubElement(self.metadata, 'desc').text = description
            if author:
                author_ = mod_etree.SubElement(self.metadata, 'author')
                mod_etree.SubElement(author_, 'name').text = author
            if time is not None:
                mod_etree.SubElement(
                    self.metadata, 'time').text = format_time(time)

    def add_summary(self, name='', comment='', description=''):
        """Adds track/route name in name , comment in cmt and a summary in desc.
        """
        if name or comment or description:
            self.summary = mod_etree.Element('summary')
            if name:
                mod_etree.SubElement(self.summary, 'name').text = name
            if comment:
                mod_etree.SubElement(self.summary, 'cmt').text = comment
            if description:
                mod_etree.SubElement(self.summary, 'desc').text = description

    def append_trkpt(self, *, lat, lon, ele=None, time=None, name='', desc='', 
                       speed=None, hr=None):
        """Appends a trkpt in trkseg."""
        trkpt = mod_etree.SubElement(
            self.trkseg, 'trkpt', { 'lat':make_str(lat), 'lon':make_str(lon) })

        self.add_subelements(
            trkpt, ele=ele, time=time, name=name, desc=desc, speed=speed, hr=hr)

    def append_rtept(self, *, lat, lon, ele=None, time=None, name='', desc='', 
                       speed=None, hr=None):
        """Appends a rtept in rte."""
        rtept = mod_etree.SubElement(
            self.rte, 'rtept', { 'lat':make_str(lat), 'lon':make_str(lon) })

        self.add_subelements(
            rtept, ele=ele, time=time, name=name, desc=desc, speed=speed, hr=hr)

    def add_subelements(self, element, *, ele, time, name, desc, speed, hr):
        """Adds ele, time, name, desc and gpxtpx as subelements of trkpt/rtept.
        """
        if ele is not None:
            mod_etree.SubElement(element, 'ele').text = make_str(ele)
        if time is not None:
            mod_etree.SubElement(element, 'time').text = format_time(time)
        if name:
            mod_etree.SubElement(element, 'name').text = name
        if desc:
            mod_etree.SubElement(element, 'desc').text = desc
        if speed is not None or hr is not None:
            extensions = mod_etree.SubElement(element, 'extensions')
            gpxtpx = mod_etree.SubElement(
                extensions, '{' f'{NS_GPXTPX}' '}' 'TrackPointExtension')
            if speed is not None:
                mod_etree.SubElement(gpxtpx, '{' f'{NS_GPXTPX}' '}' 'speed'
                                     ).text = make_str(speed)
            if hr is not None:
                mod_etree.SubElement(gpxtpx, '{' f'{NS_GPXTPX}' '}' 'hr'
                                     ).text = make_str(hr)

