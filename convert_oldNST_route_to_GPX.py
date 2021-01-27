#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site
# under LGPL v2.1 license.
# https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads route files of the old-version Nokia SportsTracker.
"""
import sys
from pathlib import Path
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


#  The native Symbian time format is a 64-bit value that represents 
#  microseconds since January 1st 0 AD 00:00:00 local time, nominal Gregorian.
#  BC dates are represented by negative values.
def symbian_to_unix_time(symbiantime):
    return symbiantime / 1e6 - 62168256000

WORKAROUND = False
def dt_from_timestamp(timestamp, tz_info=None):
    """A workaround of datetime.fromtimestamp() for a few platforms after 2038.

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
    (size, ) = read_unpack('B', file_object) # U8.
    if size & 0x1: # If LSB == 1, character_length >= 64.
        (size, ) = struct.unpack('<H', bytes([size]) + file_object.read(1))
        size >>= 1 # Divide character_length * 8 (U16) by 2.
    # Else if LSB == 0, character_length < 64. U8, character_length * 4.
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

def store_trackpt(tp):
    """Do whatever with the trackpt data: print, gpx, store in a database, etc.

    Args:
        tp: (unix_time(s), t_time(s), y_degree, x_degree, z_ax(m), v(km/h), 
             d_dist(km), dist(km), track_count(int), file_type(int: 2, 3 or 4))
    """
    # Print delimited text.
    #utc_time = f'{format_datetime(tp.unix_time)}Z'
    #to_time = format_timedelta(tp.t_time)
    #print(f'{to_time}\t{utc_time}\t{round(tp.d_dist, 3)}\t{round(tp.dist, 3)}'
    #      f'\t{round(tp.y_degree, 10)}\t{round(tp.x_degree, 10)}\t'
    #      f'{round(tp.z_ax, 1)}\t{round(tp.v, 2)}')

    # Print gpx xml.
    gpx_point_def = (gpxpy.gpx.GPXRoutePoint if tp.file_type == 0x3 
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
    # Creating a new GPX:
    gpx = gpxpy.gpx.GPX()

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

    if file_type == 0x3:
        # Create the first route in the GPX:
        gpx_route = gpxpy.gpx.GPXRoute()
        gpx.routes.append(gpx_route)
        return gpx, gpx_route
    else:
        # Create the first track in the GPX:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        # Create the first segment in the GPX track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        return gpx, gpx_segment

def finalize_gpx(gpx, file_type, write_file=None):
    # Add a summary.  This part may be informative.
    total_time_ = t_time if total_time == 0 else total_time
    total_distance_ = dist if total_distance == 0 else total_distance
    net_speed_ = total_distance_ / (total_time_ / 3600) # km/h.
    descr = ('[' f'Total time: {format_timedelta(total_time_)}' '; '
             f'Total distance: {round(total_distance_, 3)} km' '; '
             f'Net speed: {round(net_speed_, 3)} km/h')
    gpx.name = f'[{route_name}]' if file_type == 0x3 else f'[{track_name}]'
    if file_type == 0x3: # Route files.
        gpx.routes[0].name = gpx.name
        gpx.routes[0].description = (f'{descr}' ']')
    else: # Track files.
        gpx.tracks[0].name = gpx.name
        stop_localtime_ = (
            stop_localtime if stop_localtime != symbian_to_unix_time(0) 
            else unix_time + TZ_HOURS * 3600)
        real_time_ = stop_localtime_ - start_localtime
        gross_speed_ = total_distance_ / (real_time_ / 3600) # km/h.
        gpx.tracks[0].description = (
            f'{descr}' '; '
            f'Start localtime: {format_datetime(start_localtime)}' '; '
            f'Stop localtime: {format_datetime(stop_localtime_)}' '; '
            f'Real time: {format_timedelta(real_time_)}' '; '
            f'Gross speed: {round(gross_speed_, 3)} km/h' ']')
        gpx.description = f'[{description}]' # Activity type: run, bicycle, etc.
        gpx.author_name = str(USER_ID)
        gpx.time = dt_from_timestamp(
            start_time, dt.timezone(dt.timedelta(hours=TZ_HOURS), ))
        if 'comment' in globals():
            if comment: gpx.tracks[0].comment = comment

    # Finally, print or write the gpx.
    write_file = False if write_file is None else write_file
    if write_file:
        gpx_file = Path(str(in_file)[:-3] + 'gpx')
        result = gpx.to_xml('1.1')
        result_file = open(gpx_file, 'w')
        result_file.write(result)
        result_file.close()
    else:
        print(gpx.to_xml('1.1'))


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads route files (R*.dat) of the old-version Nokia 
        SportsTracker.""")
    sys.exit(0)
#print(argvs[1])
#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)


with in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    #f.seek(0x00000, 0)
    # 8 (4+4) bytes, little endian U32+U32.
    (APPLICATION_ID, FILE_TYPE) = read_unpack('<2I', f)
    (CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
    if APPLICATION_ID != 0x0e4935e8 or FILE_TYPE != ROUTE:
        print(f'Unexpected file type: {FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Version: {version}')
    (OLDNST, OLDNST_ROUTE, NST) = ( # OldNST track, route and new NST track.
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not OLDNST_ROUTE:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, gpx_target = initialize_gpx(FILE_TYPE)

    # Start address of the main part (pause and trackpoint data).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    (start_address, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    start_address -= 1
    #print(f'Main part address: {hex(start_address)}')

    # Route ID.
    f.seek(0x00014, 0) # Go to 0x00014, this address is fixed.
    (ROUTE_ID, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Route ID: {ROUTE_ID}')

    # Read SCSU encoded name of the route.  Its length is variable.
    #f.seek(0x00018, 0) # Go to 0x00018, this address is fixed.
    route_name = scsu_reader(f)
    #print(f'Route name: {route_name}')

    total_time = 0 # Totaltime is not stored in the route file.

    # Total Distance.
    (total_distance, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    total_distance /= 1e5 # Total distance in km.
    #print(f'Total distance: {round(total_distance, 3)} km')


    # Number of track points.
    #start_address = 0x000ff # Usually 0x000ff.
    f.seek(start_address, 0) # Go to the start address of the main part.
    (NUM_TRACKPT, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Number of track/route pts: {NUM_TRACKPT}')


    # There are no pause data in route files.   
    # Go to the first trackpoint.
    track_count = 0

    # In contrast to the new version, we have to calculate the timestamps in 
    # all of the trackpoints because of no Symbiantimes given in the old one.

    # Factory functions for creating named tuples.
    TYPE00 = 't_time, y_ax, x_ax, z_ax, v, d_dist'
    TYPE80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist'
    TYPEC0 = 'dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist'
    if NST: # The fields shown below are added in the new version.
        TYPE00 += ', symbian_time'
        TYPE80, TYPEC0 = (t + ', unknown1, unknown2' for t in (TYPE80, TYPEC0))
    TYPE_STORE = ('unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, '
                  'dist, track_count, file_type')
    TrackptType00 = namedtuple('TrackptType00', TYPE00)
    TrackptType80 = namedtuple('TrackptType80', TYPE80)
    TrackptTypeC0 = namedtuple('TrackptTypeC0', TYPEC0)
    TrackptStore = namedtuple('TrackptStore', TYPE_STORE)
    TrackptStore.__new__.__defaults__ = (None,) * len(TrackptStore._fields)

    # We will use mtime as start_time, because the start/stop times stored in 
    # the route files are always 0, which means January 1st 0 AD 00:00:00.
    trackpt_store = TrackptStore() # A temporal storage to pass the trackpt.
    trackpt_store = trackpt_store._replace(
        unix_time=in_file.stat().st_mtime, t_time=0, dist=0)

    # The main loop to read the trackpoints.
    while track_count < NUM_TRACKPT:

        pointer = f.tell()
        header_fmt = 'B' # 1-byte header.
        (header, ) = read_unpack(header_fmt, f)

        if header in {0x00, 0x02, 0x03}:

            (Trackpt, fmt) = (TrackptType00, '<I3iHI')
            # (t_time, y_ax, x_ax, z_ax, v, d_dist)
            # 22 bytes (4+4+4+4+2+4).  Negative y (x) means South (West).
            trackpt = Trackpt._make(read_unpack(fmt, f)) # Namedtuple wrapped.

            t_time = trackpt.t_time / 100 # Totaltime / second.

            # The lat. and lon. are in I32s (DDDmm mmmm format).
            (y_degree, y_mm_mmmm) = divmod(trackpt.y_ax, 1e6)
            (x_degree, x_mm_mmmm) = divmod(trackpt.x_ax, 1e6)
            y_degree += y_mm_mmmm / 1e4 / 60 # Convert minutes to degrees.
            x_degree += x_mm_mmmm / 1e4 / 60

            z_ax = trackpt.z_ax / 10 # Altitude / meter.
            v = trackpt.v / 100 * 3.6 # Velocity: v (m/s) * 3.6 = v (km/h).
            dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance/km.
            unix_time = (
                trackpt_store.unix_time + (t_time - trackpt_store.t_time))

            #times = f'{t_time} {format_datetime(unix_time)}Z'
            #print(hex(f.tell()), hex(header), times, *trackpt[1:])

        elif header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B, 
                        0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}:

            if header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B}:

                Trackpt = TrackptType80
                # (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist)

                if header in {0x80, 0x82, 0x83}: # 1-byte dv.
                    fmt = '<B3hbH' # 10 bytes (1+2+2+2+1+2).
                elif header in {0x92, 0x93}: # 2-byte dv.
                    fmt = '<B4hH' # 11 bytes (1+2+2+2+2+2).
                else: # 0x9A, 0x9B; 2-byte dv. 4-byte d_dist.
                    fmt = '<B4hI' # 13 bytes (1+2+2+2+2+4).

            elif header in {0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}: # Rare cases.

                Trackpt = TrackptTypeC0
                # (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist)
                # Unknown3 & 4 show up in distant jumps.

                if header in {0xC2, 0xC3}: # 1-byte dv.
                    fmt = '<B5hbH' # 14 bytes (1+2+2+2+2+2+1+2).
                elif header in {0xD2, 0xD3}: # 2-byte dv.
                    fmt = '<B6hH' # 15 bytes (1+2+2+2+2+2+2+2).
                else: # 0xDA, 0xDB; 2-byte dv. 4-byte d_dist.
                    fmt = '<B6hI' # 17 bytes (1+2+2+2+2+2+2+4).

            trackpt = Trackpt._make(read_unpack(fmt, f)) # Namedtuple wrapped.

            t_time = trackpt_store.t_time + trackpt.dt_time / 100 # Totaltime/s.

            y_degree = trackpt_store.y_degree + trackpt.dy_ax / 1e4 / 60 # Lat.
            x_degree = trackpt_store.x_degree + trackpt.dx_ax / 1e4 / 60 # Lon.

            z_ax = trackpt_store.z_ax + trackpt.dz_ax / 10 # Altitude / m.
            v = trackpt_store.v + trackpt.dv / 100 * 3.6 # Velocity / km/h.
            dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance / km.
            unix_time = trackpt_store.unix_time + trackpt.dt_time / 100

            #times = f'{t_time} {format_datetime(unix_time)}Z'
            #print(hex(f.tell()), hex(header), times, *trackpt[1:])

        else: # Other headers which I don't know.

            print(f'{hex(header)} Error in the track point header: '
                  f'{track_count}, {NUM_TRACKPT}')
            print(f'At address: {hex(pointer)}')
            print(*trackpt)
            print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)
            break

        trackpt_store = TrackptStore(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=trackpt.d_dist / 1e5, 
            dist=dist, track_count=track_count, file_type=FILE_TYPE)
        store_trackpt(trackpt_store)

        track_count += 1


# Handling of errors.
if track_count != NUM_TRACKPT:
    print(f'Track point count error: {track_count}, {NUM_TRACKPT}')
    sys.exit(1)

finalize_gpx(gpx, FILE_TYPE, write_file=False) # True=write file, False=print.
