#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""A module for reading Nokia SportsTracker files.
"""
import sys
import struct
import datetime as dt
from collections import namedtuple

import gpxpy
import gpxpy.gpx

try: # Load LXML or fallback to cET or ET.
    import lxml.etree as mod_etree  # type: ignore
except ImportError:
    try:
        import xml.etree.cElementTree as mod_etree # type: ignore
    except ImportError:
        import xml.etree.ElementTree as mod_etree # type: ignore

import scsu


# Initialize variables.
(total_time, total_distance) = (0, ) * 2
(comment, route_name, track_name, TZ_HOURS, start_localtime, description, 
    USER_ID, start_time, OLDNST, OLDNST_ROUTE, NST, FILE_TYPE, gpx_target, 
    in_file) = (None, ) * 14

# Types of activities in (Nokia) Sports Tracker.
ACTIVITIES = ('Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 
              'Other 3', 'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 
              'Hiking', 'Roller skating', 'Downhill skiing', 'Paddling', 
              'Rowing', 'Golf', 'Indoor')

(CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
APP_ID = 0x0e4935e8


def symbian_to_unix_time(symbiantime):
    """Convert a timestamp from symbiantime to unixtime.

    Symbiantimes are 64-bit values that represent microsecs since 1 Jan. 0 AD
    00:00:00 localtime, nominal Gregorian.  Negative values represent BC dates.
    """
    return symbiantime / 1e6 - 62168256000

stop_localtime = symbian_to_unix_time(0)

WORKAROUND = False
def dt_from_timestamp(timestamp, tz_info=None):
    """A workaround of datetime.fromtimestamp() for a few platform after 2038.

    Set WORKAROUND = True, if necessary.
    """
    if WORKAROUND and -62135596800 <= timestamp < 253402300800:
        # From 0001-01-01T00:00:00 to 9999-12-31T23:59:59.
        d_t = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        d_t += dt.timedelta(seconds=1) * timestamp
    elif (not WORKAROUND) and 0 <= timestamp < 32536799999:
        # From 1970-01-01T00:00:00 to 3001-01-19T07:59:59, platform dependent.
        d_t = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
    else:
        return None
    return (d_t.replace(tzinfo=None) if tz_info is None 
            else d_t.astimezone(tz_info))

def format_datetime(timestamp): # ISO-8601 format.
    d_t = dt_from_timestamp(round(timestamp, 3))
    return (d_t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if d_t is not None 
            else f'INVALID({timestamp})')

def format_timedelta(t_delta):
    return str(dt.timedelta(seconds=round(t_delta, 3)))[:-3]

def read_unpack(struct_fmt, file_object): # Helper function to read and unpack.
    size = struct.calcsize(struct_fmt)
    return struct.unpack(struct_fmt, file_object.read(size))

def scsu_reader(file_object, address=None):
    """Reads variable-length SCSU bytes and returns UTF-8 using scsu.py.

    Args:
        file_object: file object to be read.
        address: start address of the SCSU encoded part.  The data is preceded 
            by one/two byte integer which indicates the character length multi-
            plied by four/eight.

    Returns:
        decoded_strings: strings of UTF-8.
    """
    if address is not None: file_object.seek(address, 0)
    (size, ) = read_unpack('B', file_object) # U8, character_length * 4.
    if size & 0x1: # If LSB == 1: char_len >= 64. If LSB == 0: char_len < 64.
        (size, ) = struct.unpack('<H', bytes([size]) + file_object.read(1))
        size >>= 1 # Divide character_length * 8 (U16) by 2.
    start_of_scsu = file_object.tell()
    in_bytes = file_object.read(size) # Character_length * 4 is sufficient.
    size >>= 2 # Divide by 4 to obtain the character_length.
    (out_array, byte_length, character_length) = scsu.decode(in_bytes, size)
    del character_length # This is not in use.
    decoded_strings = out_array.decode('utf-8', 'ignore') # Sanitize.
    if len(decoded_strings) != size: #  Check the length.
        print('SCSU decode failed.', out_array)
        sys.exit(1)
    file_object.seek(start_of_scsu + byte_length, 0) # Go to the next field.
    return decoded_strings

def dmm_to_decdeg(dddmm_mmmm):
    """Convert signed int. DDDMM MMMM format to decimal degree.

    >>> dmm_to_decdeg(45300000)
    45.5
    >>> dmm_to_decdeg(-135150000)
    -135.25
    """
    sign_dddmm_mmmm = (dddmm_mmmm > 0) - (dddmm_mmmm < 0)
    (decimal_degree, mm_mmmm) = divmod(abs(dddmm_mmmm), 1e6)
    decimal_degree += mm_mmmm / 1e4 / 60
    return sign_dddmm_mmmm * decimal_degree

def store_trackpt(tp): # tp: trackpt_store
    """Do whatever with the trackpt data: print, gpx, store in a database, etc.

    Args:
        tp: (unix_time(s), t_time(s), y_degree, x_degree, z_ax(m), v(km/h), 
             d_dist(km), dist(km), track_count(int), file_type(int: 2, 3 or 4))
    """
    # Print delimited text.
    #times = f'{format_timedelta(tp.t_time)}\t{format_datetime(tp.unix_time)}Z'
    #print(f'{times}\t{round(tp.d_dist, 3)}\t{round(tp.dist, 3)}\t'
    #      f'{round(tp.y_degree, 10)}\t{round(tp.x_degree, 10)}\t'
    #      f'{round(tp.z_ax, 1)}\t{round(tp.v, 2)}')

    # Print gpx xml.
    gpx_point_def = (gpxpy.gpx.GPXRoutePoint if tp.file_type == ROUTE 
                     else gpxpy.gpx.GPXTrackPoint)
    gpx_point = gpx_point_def(
        latitude=round(tp.y_degree, 10), 
        longitude=round(tp.x_degree, 10), 
        elevation=round(tp.z_ax, 1), 
        time=dt_from_timestamp(tp.unix_time, dt.timezone.utc), 
        name=str(tp.track_count + 1))
    gpx_target.points.append(gpx_point) # gpx_target = gpx_route or gpx_segment.

    # This part may be informative.  Comment it out, if not necessary.
    gpx_point.description = (
        f'Speed {round(tp.v, 3)} km/h Distance {round(tp.dist, 3)} km')

    # In gpx 1.1, use trackpoint extensions to store speeds in m/s.
    # Not quite sure if the <gpxtpx:TrackPointExtension> tag is valid in rtept.
    speed = round(tp.v / 3.6, 3) # velocity in m/s
    gpx_extension_speed = mod_etree.fromstring(
        '<gpxtpx:TrackPointExtension xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2">'
        f'<gpxtpx:speed>{speed}</gpxtpx:speed>'
        '</gpxtpx:TrackPointExtension>')
    gpx_point.extensions.append(gpx_extension_speed)

def initialize_gpx(file_type):
    gpx = gpxpy.gpx.GPX() # Create a new GPX.

    # Add TrackPointExtension namespaces and schema locations.
    gpx.nsmap['gpxtpx'] = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v2'
    gpx.nsmap['gpxx'] = 'http://www.garmin.com/xmlschemas/GpxExtensions/v3'
    gpx.schema_locations = [
        'http://www.topografix.com/GPX/1/1',
        'http://www.topografix.com/GPX/1/1/gpx.xsd',
        'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
        'http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd',
        'http://www.garmin.com/xmlschemas/TrackPointExtension/v2',
        'http://www8.garmin.com/xmlschemas/TrackPointExtensionv2.xsd']

    if file_type == ROUTE: # Create the first route in the GPX.
        gpx_route = gpxpy.gpx.GPXRoute()
        gpx.routes.append(gpx_route)
        return gpx, gpx_route
    else: # Create the first track in the GPX.
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        # Create the first segment in the GPX track.
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        return gpx, gpx_segment

def add_gpx_summary(gpx, tp_store):
    total_time_ = tp_store.t_time if total_time == 0 else total_time
    total_distance_ = tp_store.dist if total_distance == 0 else total_distance
    net_speed = total_distance_ / (total_time_ / 3600) # km/h.
    descr = ('[' f'Total time: {format_timedelta(total_time_)}' '; '
             f'Total distance: {round(total_distance_, 3)} km' '; '
             f'Net speed: {round(net_speed, 3)} km/h')
    if tp_store.file_type == ROUTE:
        gpx.name = f'[{route_name}]'
        gpx.routes[0].name = gpx.name
        gpx.routes[0].description = (f'{descr}' ']')
    else: # Track files.
        gpx.name = f'[{track_name}]'
        gpx.tracks[0].name = gpx.name
        stop_localtime_ = (
            stop_localtime if stop_localtime != symbian_to_unix_time(0) 
            else tp_store.unix_time + TZ_HOURS * 3600)
        real_time = stop_localtime_ - start_localtime
        gross_speed = total_distance_ / (real_time / 3600) # km/h.
        gpx.tracks[0].description = (
            f'{descr}' '; '
            f'Start localtime: {format_datetime(start_localtime)}' '; '
            f'Stop localtime: {format_datetime(stop_localtime_)}' '; '
            f'Real time: {format_timedelta(real_time)}' '; '
            f'Gross speed: {round(gross_speed, 3)} km/h' ']')
        gpx.description = f'[{description}]' # ACTIVITIES: run, bicycle, etc.
        gpx.author_name = str(USER_ID)
        gpx.time = dt_from_timestamp(
            start_time, dt.timezone(dt.timedelta(hours=TZ_HOURS), ))
        if comment: gpx.tracks[0].comment = comment

def finalize_gpx(gpx, outfile_path=None):
    if outfile_path is not None: # Finally, print or write the gpx.
        result = gpx.to_xml('1.1')
        result_file = open(outfile_path, 'w')
        result_file.write(result)
        result_file.close()
    else:
        print(gpx.to_xml('1.1'))

DEBUG_READ_PAUSE = False
def read_pause_data(file_obj):
    (num_pause, ) = read_unpack('<I', file_obj) # 4 bytes, little endian U32.
    #print(f'Number of pause data: {num_pause}')
    #pause_address = file_obj.tell() # START_ADDRESS + 4
    #print(f'Pause address: {hex(pause_address)}')

    def print_raw_data(): # For debugging purposes.
        utctime = f'{format_datetime(unix_time)}' # The old ver. in localtime.
        if NST: utctime += 'Z' # The new version NST in UTC (Z).
        print(f'{unknown}\t{format_timedelta(t_time)}\t{flag}\t{utctime}')

    pause_count = 0
    pause_list = []

    (start, stop, manual_suspend, automatic_suspend, resume, flag_8) = (
        1, 2, 3, 4, 5, 8)

    while pause_count < num_pause:
        # Read 14 bytes of data(1+4+1+8).  Symbiantimes of the old version are 
        # in localtime zone, while those of the new version in UTC (Z).
        # The first unknown field (always 0x01) seems to have no meaning.
        (unknown, t_time, flag, symbiantime) = read_unpack('<BIBq', file_obj)

        t_time /= 100 # Totaltime in seconds.
        unix_time = symbian_to_unix_time(symbiantime)
        if DEBUG_READ_PAUSE: print_raw_data() # For debugging purposes.

        if flag == start:
            starttime = unix_time
            start_t_time = t_time

        elif flag == stop:
            stoptime = unix_time
            stop_t_time = t_time

        elif flag in {manual_suspend, automatic_suspend}:
            suspendtime = unix_time
            t4_time = t_time

        elif flag == resume:
            if t4_time != t_time: # Suspend-resume pair has a common t_time.
                print('Error in pause.')
                sys.exit(1)
            pause_time = unix_time - suspendtime
            pause_list.append((t_time, pause_time, unix_time))

        elif flag == flag_8: # Use it as a correction of time.
            pause_time = 0
            pause_list.append((t_time, pause_time, unix_time))

        pause_count += 1

    del unknown, starttime, start_t_time, stoptime, stop_t_time
    return pause_list, pause_count

def print_pause_list(pause_list):
    d_t = 'Datetime Z' if NST else 'Datetime local'
    print('Total time', '\t', 'Pause time', '\t', d_t, sep ='')
    for p in pause_list:
        t_time, pause_time, unix_time = p
        print(f'{format_timedelta(t_time)}\t{format_timedelta(pause_time)}\t'
              f'{format_datetime(unix_time)}')
    print()

def prepare_namedtuples(nst=None):
    if nst is None: nst = NST
    # Factory functions for creating named tuples.
    type00 = 't_time, y_ax, x_ax, z_ax, v, d_dist'
    type80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist'
    typec0 = 'dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist'
    if nst: # The fields shown below are added in the new version.
        type00 += ', symbian_time'
        type80, typec0 = (t + ', unknown1, unknown2' for t in (type80, typec0))
    type_store = ('unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, '
                  'dist, track_count, file_type')
    TrackptType00_ = namedtuple('TrackptType00', type00)
    TrackptType80_ = namedtuple('TrackptType80', type80)
    TrackptTypeC0_ = namedtuple('TrackptTypeC0', typec0)
    TrackptStore_ = namedtuple('TrackptStore', type_store)
    TrackptStore_.__new__.__defaults__ = (None,) * len(TrackptStore_._fields)
    return TrackptType00_, TrackptType80_, TrackptTypeC0_, TrackptStore_

def process_trackpt_type00(tp, tp_store, nst=None):
    if nst is None: nst = NST
    t_time = tp.t_time / 100 # Totaltime / second.

    # The lat. and lon. are in I32s (DDDmm mmmm format).
    y = dmm_to_decdeg(tp.y_ax)# Convert to decimal degrees.
    x = dmm_to_decdeg(tp.x_ax)

    z = tp.z_ax / 10 # Altitude / meter.
    v = tp.v / 100 * 3.6 # Velocity: v (m/s) * 3.6 = v (km/h).
    d_dist = tp.d_dist / 1e5 # Delta distance/km.
    dist = tp_store.dist + d_dist # Distance/km.
    # In contrast to the new NST, we have to calculate the timestamps in 
    # all of the trackpts because of no symbiantimes given in the OLDNSTs.
    unix_time = (tp_store.unix_time + (t_time - tp_store.t_time) if not nst
                else symbian_to_unix_time(tp.symbian_time))
    return unix_time, t_time, y, x, z, v, d_dist, dist

def process_trackpt_type80(tp, tp_store, nst=None):
    if nst is None: nst = NST
    t_time = tp_store.t_time + tp.dt_time / 100 # Totaltime/s.

    y = tp_store.y_degree + tp.dy_ax / 1e4 / 60 # Lat.
    x = tp_store.x_degree + tp.dx_ax / 1e4 / 60 # Lon.

    z = tp_store.z_ax + tp.dz_ax / 10 # Altitude / m.
    v = tp_store.v + tp.dv / 100 * 3.6 # Velocity / km/h.
    d_dist = tp.d_dist / 1e5 # Delta distance/km.
    dist = tp_store.dist + d_dist # Distance / km.
    unix_time = tp_store.unix_time + tp.dt_time / 100
    del nst # Not in use.
    return unix_time, t_time, y, x, z, v, d_dist, dist

DEBUG_READ_TRACK = False
def read_trackpoints(file_obj, pause_list=None): # No pause_list in ROUTE & TMP.

    def print_raw(t_time, unix_time, hdr, tp):
        times = f'{t_time} {format_datetime(unix_time)}Z'
        # Remove symbiantime from trackpt if NST and header0x07.
        trackpt_ = tp[1:-1] if NST and hdr == 0x07 else tp[1:]
        print(hex(file_obj.tell()), hex(hdr), times, *trackpt_)

    def print_other_header_error(ptr, hdr): # pointer, header.
        print(f'{hdr:#x} Error in the track point header: {track_count}, '
              f'{num_trackpt}' '\n' f'At address: {ptr:#x}')

    def read_oldnst_trackpt():
        nonlocal trackpt_store
        pointer = file_obj.tell()
        header_fmt = 'B' # 1-byte header.
        (header, ) = read_unpack(header_fmt, file_obj)

        if header in {0x00, 0x02, 0x03}:
            process_trackpt = process_trackpt_type00
            (Trackpt, fmt) = (TrackptType00, '<I3iHI')
            # (t_time, y_ax, x_ax, z_ax, v, d_dist)
            # 22 bytes (4+4+4+4+2+4).  y(+/-): North/South; x(+/-): East/West.

        elif header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B, 
                        0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}:
            process_trackpt = process_trackpt_type80

            if header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B}:
                Trackpt = TrackptType80
                # (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist)

                if header in {0x80, 0x82, 0x83}: # 1-byte dv.
                    fmt = '<B3hbH' # 10 bytes (1+2+2+2+1+2).
                elif header in {0x92, 0x93}: # 2-byte dv.
                    fmt = '<B4hH' # 11 bytes (1+2+2+2+2+2).
                else: # 0x9A, 0x9B; 2-byte dv. 4-byte d_dist.
                    fmt = '<B4hI' # 13 bytes (1+2+2+2+2+4).

            else: # Header in {0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}: Rare cases.
                Trackpt = TrackptTypeC0
                # (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist)
                # Unknown3 & 4 show up in distant jumps.

                if header in {0xC2, 0xC3}: # 1-byte dv.
                    fmt = '<B5hbH' # 14 bytes (1+2+2+2+2+2+1+2).
                elif header in {0xD2, 0xD3}: # 2-byte dv.
                    fmt = '<B6hH' # 15 bytes (1+2+2+2+2+2+2+2).
                else: # 0xDA, 0xDB; 2-byte dv. 4-byte d_dist.
                    fmt = '<B6hI' # 17 bytes (1+2+2+2+2+2+2+4).

        else: # Other headers which I don't know.
            print_other_header_error(pointer, header)
            return 1

        trackpt = Trackpt._make(read_unpack(fmt, file_obj)) # Read and wrap.

        unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, dist = (
           process_trackpt(trackpt, trackpt_store)) # Use tp & the previous.
        if DEBUG_READ_TRACK: print_raw(t_time, unix_time, header, trackpt)

        if pause_list: # Adjust unix_time by using pause_list.
            t4_time, pause_time, resume_time = pause_list[0]

            if t_time + 0.5 >= t4_time: # After the pause, use the pause data.
                del pause_list[0]
                if DEBUG_READ_TRACK: print(f'Pause time: {pause_time}')
                resume_time -= TZ_HOURS * 3600 # Convert from localtime to UTC.

                if unix_time < resume_time:
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time

        trackpt_store = TrackptStore(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=d_dist, 
            dist=dist, track_count=track_count, file_type=FILE_TYPE)

        return 0

    def read_nst_trackpt():
        nonlocal trackpt_store
        pointer = file_obj.tell()
        header_fmt = '2B' # 2-byte header.
        (header, header1) = read_unpack(header_fmt, file_obj)
        del header1 # We don't use header1.

        if header == 0x07: # Typically, 0783 or 0782.
            process_trackpt = process_trackpt_type00
            (Trackpt, fmt) = (TrackptType00, '<I3iHIq')
            # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
            # 30 bytes (4+4+4+4+2+4+8).  y(+/-): North/South; x(+/-): East/West.

        elif header in {0x87, 0x97, 0xC7, 0xD7}:
            process_trackpt = process_trackpt_type80

            if header in {0x87, 0x97}: # Typically 8783, 8782, 9783, 9782.
                Trackpt = TrackptType80
                # (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist, unknown1, unknown2)
                # Unknown1 & 2 might be related to heart rate sensor.
                fmt = '<B3hbH2B' if header == 0x87 else '<B4hH2B' # 0x97
                # 0x87: 12 bytes (1+2+2+2+1+2+1+1).  1-byte dv.
                # 0x97: 13 bytes (1+2+2+2+2+2+1+1).  2-byte dv.

            else: # Header in {0xC7, 0xD7}. C783, C782, D783, D782: Rare cases.
                Trackpt = TrackptTypeC0
                # (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist,
                # unknown1, unknown2); Unknown3 & 4 show up in distant jumps.
                fmt = '<B5hbH2B' if header == 0xC7 else '<B6hH2B' # 0xD7
                # 0xC7: 16 bytes (1+2+2+2+2+2+1+2+1+1).  1-byte dv.
                # 0xD7: 17 bytes (1+2+2+2+2+2+2+2+1+1).  2-byte dv.

        else: # Other headers which I don't know.
            print_other_header_error(pointer, header)
            return 1

        trackpt = Trackpt._make(read_unpack(fmt, file_obj)) # Read and wrap.

        unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, dist = (
           process_trackpt(trackpt, trackpt_store)) # Use tp & the previous.
        if DEBUG_READ_TRACK: print_raw(t_time, unix_time, header, trackpt)

        if pause_list: # Adjust unix_time by using pause_list.
            t4_time, pause_time, resume_time = pause_list[0]

            if t_time + 0.5 >= t4_time: # After the pause, use the pause data.
                del pause_list[0]
                if DEBUG_READ_TRACK: print(f'Pause time: {pause_time}')

                if header != 0x07: # The trackpoint lacks for symbiantime.
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time

        trackpt_store = TrackptStore(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=d_dist, 
            dist=dist, track_count=track_count, file_type=FILE_TYPE)

        return 0


    # Number of track points.
    (num_trackpt, ) = read_unpack('<I', file_obj) # 4 bytes, little endian U32.
    #print(f'Number of track/route pts: {num_trackpt}')
    #track_address = file_obj.tell()
    #print(f'Track address: {hex(track_address)}')

    # Factory functions for creating named tuples.
    TrackptType00, TrackptType80, TrackptTypeC0, TrackptStore = (
        prepare_namedtuples())

    # For oldNST_route, use mtime as start_time because the start/stop times 
    # stored are always 0 which means January 1st 0 AD 00:00:00.
    starttime = in_file.stat().st_mtime if OLDNST_ROUTE else start_time
    trackpt_store = TrackptStore() # Temporal storage for the processed trackpt.
    trackpt_store = trackpt_store._replace(
        unix_time=starttime, t_time=0, dist=0)

    # This is the main loop.
    track_count = 0
    read_trackpt = read_nst_trackpt if NST else read_oldnst_trackpt
    while track_count < num_trackpt:

        exit_code = read_trackpt() # In trackpt_store, after processing.
        if exit_code: break

        store_trackpt(trackpt_store)

        track_count += 1

    # Handling of errors.
    if track_count != num_trackpt:
        print(f'Track point count error: {track_count}, {num_trackpt}')
        print(*trackpt_store)
        sys.exit(1)

    else:
        return track_count, trackpt_store
