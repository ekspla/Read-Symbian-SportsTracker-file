#mini_gpx.py
#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""A module for writing gpx xml from Symbian (Nokia) SportsTracker files.
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
        if not 'e' in result:
            return result
        # scientific notation is illegal in GPX 1/1
        return format(s, '.10f').rstrip('0.')
    return str(s)

def format_time(datetime):
    return datetime.isoformat().replace('+00:00', 'Z')


class Gpx(object):
    def __init__(self, is_track=True):
        (self.root, self.trkseg, self.metadata, self.rte, self.summary) = (
            None, ) * 5

        self.is_track = is_track
        self.make_root()

    def __del__(self):
        self.to_xml()

    def make_root(self):
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
        if self.metadata is not None:
            self.root.append(self.metadata)

        if self.is_track:
            trk = mod_etree.Element('trk', nsmap=NSMAP)
            self.root.append(trk)
            for t in list(self.summary):
                trk.append(t)
            if self.trkseg is None: self.make_trkseg() # For empty trkpts.
            trk.append(self.trkseg)

        else:
            rte = mod_etree.Element('rte', nsmap=NSMAP)
            self.root.append(rte)
            for t in list(self.summary):
                rte.append(t)
            for pt in list(self.rte):
                rte.append(pt)

        return mod_etree.tostring(
            self.root, encoding="UTF-8", pretty_print=True, 
            doctype='<?xml version="1.0" encoding="UTF-8"?>')

    def add_metadata(self, name=None, description=None, author=None, time=None):
        if name or description or author or time:
            self.metadata = mod_etree.Element('metadata', nsmap=NSMAP)
            if name is not None:
                _name = mod_etree.SubElement(self.metadata, 'name')
                _name.text = name
            if description is not None:
                _desc = mod_etree.SubElement(self.metadata, 'desc')
                _desc.text = description
            if author is not None:
                _author = mod_etree.SubElement(self.metadata, 'author')
                _author_name = mod_etree.SubElement(_author, 'name')
                _author_name.text = author
            if time is not None:
                _name = mod_etree.SubElement(self.metadata, 'time')
                _name.text = format_time(time)

    def add_summary(self, name='', comment='', description=''):
        if name or comment or description:
            self.summary = mod_etree.Element('summary', nsmap=NSMAP)
            if name:
                _name = mod_etree.SubElement(self.summary, 'name')
                _name.text = name
            if comment:
                _cmt = mod_etree.SubElement(self.summary, 'cmt')
                _cmt.text = comment
            if description:
                _desc = mod_etree.SubElement(self.summary, 'desc')
                _desc.text = description

    def append_trkpt(self, *, lat, lon, ele=None, time=None, name=None, 
                       desc=None, speed=None, hr=None):

        trkpt = mod_etree.Element(
            'trkpt', { 'lat':make_str(lat), 'lon':make_str(lon) })
        if ele is not None:
            trkpt_ele = mod_etree.SubElement(trkpt, 'ele')
            trkpt_ele.text = make_str(ele)
        if time is not None:
            trkpt_time = mod_etree.SubElement(trkpt, 'time')
            trkpt_time.text = format_time(time)
        if name is not None:
            trkpt_name = mod_etree.SubElement(trkpt, 'name')
            trkpt_name.text = name
        if desc is not None:
            trkpt_desc = mod_etree.SubElement(trkpt, 'desc')
            trkpt_desc.text = desc

        if speed is not None or hr is not None:
            extensions = mod_etree.SubElement(trkpt, 'extensions')
            gpxtpx = mod_etree.SubElement(
                extensions, '{' + f'{NS_GPXTPX}' +'}' + 'TrackPointExtension')
            if speed is not None:
                _speed = mod_etree.SubElement(
                    gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'speed')
                _speed.text = make_str(speed)
            if hr is not None:
                _hr = mod_etree.SubElement(
                    gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'hr')
                _hr.text = make_str(hr)

        if self.trkseg is not None:
            self.trkseg.append(trkpt)
        else:
            self.make_trkseg()
            self.trkseg.append(trkpt)

    def append_rtept(self, *, lat, lon, ele=None, time=None, name=None, 
                       desc=None, speed=None, hr=None):

        rtept = mod_etree.Element(
            'rtept', { 'lat':make_str(lat), 'lon':make_str(lon) })

        if ele is not None:
            rtept_ele = mod_etree.SubElement(rtept, 'ele')
            rtept_ele.text = make_str(ele)
        if time is not None:
            rtept_time = mod_etree.SubElement(rtept, 'time')
            rtept_time.text = format_time(time)
        if name is not None:
            rtept_name = mod_etree.SubElement(rtept, 'name')
            rtept_name.text = name
        if desc is not None:
            rtept_desc = mod_etree.SubElement(rtept, 'desc')
            rtept_desc.text = desc

        if speed is not None or hr is not None:
            extensions = mod_etree.SubElement(rtept, 'extensions')
            gpxtpx = mod_etree.SubElement(
                extensions, '{' + f'{NS_GPXTPX}' +'}' + 'TrackPointExtension')
            if speed is not None:
                _speed = mod_etree.SubElement(
                    gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'speed')
                _speed.text = make_str(speed)
            if hr is not None:
                _hr = mod_etree.SubElement(
                    gpxtpx, '{' + f'{NS_GPXTPX}' +'}' + 'hr')
                _hr.text = make_str(hr)

        if self.rte is not None:
            self.rte.append(rtept)
        else:
            self.make_rte()
            self.rte.append(rtept)

