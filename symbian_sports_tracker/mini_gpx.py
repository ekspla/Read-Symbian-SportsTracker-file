#mini_gpx.py
#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""A minimal module for writing gpx of Symbian (Nokia) SportsTracker file.
"""
import lxml.etree as mod_etree

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
NSMAP = {None:NS_GPX, 'gpxtpx':NS_GPXTPX, 'gpxx':NS_GPXX, 'xsi':NS_XSI}


def make_str(s): # A function copied from https://github.com/tkrajina/gpxpy.
    """ Convert a str, unicode or float object into a str type. """
    if isinstance(s, float):
        result = str(s)
        if 'e' not in result:
            return result
        # scientific notation is illegal in GPX 1/1
        return format(s, '.10f').rstrip('0.')
    return str(s)

def format_time(datetime):
    return datetime.isoformat().replace('+00:00', 'Z')


class Gpx(object):
    """GPX related stuff.  Topografix trkpt/rtept & Garmin gpxtpx are supported.
    
       A complex gpx consisting of multiple trkseg/rte is not supported.
    """
    def __init__(self, is_track=True):
        (self.trkseg, self.metadata, self.rte, self.summary) = (None, ) * 4
        self.is_track = is_track
        self.make_root()
        self.make_trkseg() if is_track else self.make_rte()

    def __del__(self):
        self.to_xml()

    def make_root(self):
        """Supported version of GPX is 1.1.
        """
        self.root = mod_etree.Element('gpx', nsmap=NSMAP)
        self.root.set('{' + NS_XSI + '}schemaLocation', SCHEMALOCATION)
        self.root.set('version', '1.1')
        self.root.set(
            'creator', 'mini_gpx.py -- '
            'https://github.com/ekspla/Read-Symbian-SportsTracker-file')

    def make_trkseg(self):
        self.trkseg = mod_etree.Element('trkseg', nsmap=NSMAP)

    def make_rte(self):
        self.rte = mod_etree.Element('rte', nsmap=NSMAP)

    def to_xml(self):
        """Serialize the root after appending trkseg, rte, metadata, etc.
        
        Returns:
            utf-8 bytes (gpx xml).
        """
        if self.metadata is not None:
            self.root.append(self.metadata)

        if self.is_track:
            trk = mod_etree.SubElement(self.root, 'trk')
            for child in self.summary:
                trk.append(child)
            if self.trkseg is None: self.make_trkseg() # For empty trkpts.
            trk.append(self.trkseg)

        else: # Route.  The other type, e.g. waypoints, is not supported.
            rte = mod_etree.SubElement(self.root, 'rte')
            for child in self.summary:
                rte.append(child)
            for rtept in self.rte:
                rte.append(rtept)

        return mod_etree.tostring(
            self.root, encoding='UTF-8', pretty_print=True, 
            doctype='<?xml version="1.0" encoding="UTF-8"?>')

    def add_metadata(self, name='', description='', author='', time=None):
        """Adds a few field in metadata as a short reference of the track/route. 
        """
        if name or description or author or time:
            self.metadata = mod_etree.Element('metadata', nsmap=NSMAP)
            if name:
                mod_etree.SubElement(self.metadata, 'name').text = name
            if description:
                mod_etree.SubElement(self.metadata, 'desc').text = description
            if author:
                author_ = mod_etree.SubElement(self.metadata, 'author')
                mod_etree.SubElement(author_, 'name').text = author
            if time is not None:
                mod_etree.SubElement(self.metadata, 
                                     'time').text = format_time(time)

    def add_summary(self, name='', comment='', description=''):
        """Adds track/route name in name , comment in cmt and a summary in desc.
        """
        if name or comment or description:
            self.summary = mod_etree.Element('summary', nsmap=NSMAP)
            if name:
                mod_etree.SubElement(self.summary, 'name').text = name
            if comment:
                mod_etree.SubElement(self.summary, 'cmt').text = comment
            if description:
                mod_etree.SubElement(self.summary, 'desc').text = description

    def append_trkpt(self, *, lat, lon, ele=None, time=None, name='', desc='', 
                       speed=None, hr=None):
        """Appends trkpt to trkseg.
        """
        trkpt = mod_etree.SubElement(
            self.trkseg, 'trkpt', { 'lat':make_str(lat), 'lon':make_str(lon) })

        self.add_subelements(trkpt, ele=ele, time=time, name=name, desc=desc, 
                             speed=speed, hr=hr)

    def append_rtept(self, *, lat, lon, ele=None, time=None, name='', desc='', 
                       speed=None, hr=None):
        """Appends rtept to rte.
        """
        rtept = mod_etree.SubElement(
            self.rte, 'rtept', { 'lat':make_str(lat), 'lon':make_str(lon) })

        self.add_subelements(rtept, ele=ele, time=time, name=name, desc=desc, 
                             speed=speed, hr=hr)

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
                extensions, '{' + f'{NS_GPXTPX}' +'}' + 'TrackPointExtension')
            if speed is not None:
                mod_etree.SubElement(gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'speed'
                                     ).text = make_str(speed)
            if hr is not None:
                mod_etree.SubElement(gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'hr'
                                     ).text = make_str(hr)
