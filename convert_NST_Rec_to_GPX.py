#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site
# under LGPL v2.1 license.
# https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads temporal track log files of SportsTracker.
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
    gpx_ = gpxpy.gpx.GPX()

    # Add TrackPointExtension namespaces and schema locations.
    gpx_.nsmap['gpxtpx'] = 'http://www.garmin.com/xmlschemas/TrackPointExtension/v2'
    gpx_.nsmap['gpxx'] = 'http://www.garmin.com/xmlschemas/GpxExtensions/v3'
    gpx_.schema_locations = [
        'http://www.topografix.com/GPX/1/1',
        'http://www.topografix.com/GPX/1/1/gpx.xsd',
        'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
        'http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd',
        'http://www.garmin.com/xmlschemas/TrackPointExtension/v2',
        'http://www8.garmin.com/xmlschemas/TrackPointExtensionv2.xsd']

    if file_type == 0x3:
        # Create the first route in the GPX:
        gpx_route = gpxpy.gpx.GPXRoute()
        gpx_.routes.append(gpx_route)
        return gpx_, gpx_route
    else:
        # Create the first track in the GPX:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx_.tracks.append(gpx_track)
        # Create the first segment in the GPX track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        return gpx_, gpx_segment

def finalize_gpx(gpx_, file_type, write_file=None):
    # Add a summary.  This part may be informative.
    total_time_ = t_time if total_time == 0 else total_time
    total_distance_ = dist if total_distance == 0 else total_distance
    net_speed_ = total_distance_ / (total_time_ / 3600) # km/h.
    descr = ('[' f'Total time: {format_timedelta(total_time_)}' '; '
             f'Total distance: {round(total_distance_, 3)} km' '; '
             f'Net speed: {round(net_speed_, 3)} km/h')
    gpx_.name = f'[{route_name}]' if file_type == 0x3 else f'[{track_name}]'
    if file_type == 0x3: # Route files.
        gpx_.routes[0].name = gpx_.name
        gpx_.routes[0].description = (f'{descr}' ']')
    else: # Track files.
        gpx_.tracks[0].name = gpx_.name
        stop_localtime_ = (
            stop_localtime if stop_localtime != symbian_to_unix_time(0) 
            else unix_time + TZ_HOURS * 3600)
        real_time_ = stop_localtime_ - start_localtime
        gross_speed_ = total_distance_ / (real_time_ / 3600) # km/h.
        gpx_.tracks[0].description = (
            f'{descr}' '; '
            f'Start localtime: {format_datetime(start_localtime)}' '; '
            f'Stop localtime: {format_datetime(stop_localtime_)}' '; '
            f'Real time: {format_timedelta(real_time_)}' '; '
            f'Gross speed: {round(gross_speed_, 3)} km/h' ']')
        gpx_.description = f'[{description}]' # Activity: run, bicycle, etc.
        gpx_.author_name = str(USER_ID)
        gpx_.time = dt_from_timestamp(
            start_time, dt.timezone(dt.timedelta(hours=TZ_HOURS), ))
        if comment: gpx_.tracks[0].comment = comment

    # Finally, print or write the gpx.
    write_file = False if write_file is None else write_file
    if write_file:
        gpx_file = Path(str(in_file)[:-3] + 'gpx')
        result = gpx_.to_xml('1.1')
        result_file = open(gpx_file, 'w')
        result_file.write(result)
        result_file.close()
    else:
        print(gpx_.to_xml('1.1'))

def print_raw_track(): # Remove symbiantime from trackpt if NST and header0x07.
    times = f'{t_time} {format_datetime(unix_time)}Z'
    trackpt_ = trackpt[1:-1] if NST and header == 0x07 else trackpt[1:]
    print(hex(f.tell()), hex(header), times, *trackpt_)

def print_other_header_error():
    print(f'{header:#x} Error in the track point header: {track_count}, '
          f'{NUM_TRACKPT}' '\n' f'At address: {pointer:#x}')
    print(*trackpt)
    print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads temporal track log files (Rec*.tmp) of symbian 
        SportsTracker.  Log files with heart-rate sensor were not tested.""")
    sys.exit(0)
#print(argvs[1])
#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)


track_name, route_name, comment = (None for x in range(3))
with in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    # Chunks in the temporal file always start with b'\x00\x00\x00\x00' blank.
    # Due to this blank, there is a 4-byte offset to the addresses shown below.
    #f.seek(0x00000, 0)
    # 12 (4+4+4) bytes, little endian U32+U32+U32.
    (APPLICATION_ID, FILE_TYPE, blank) = read_unpack('<3I', f)
    (CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
    if APPLICATION_ID != 0x0e4935e8 or FILE_TYPE != TMP or blank != 0x0:
        print(f'Unexpected file type: {FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008 + 0x4, 0) # Go to 0x00008 + 0x4, this address is fixed.
    (version, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'Version: {version}')
    (OLDNST, OLDNST_ROUTE, NST) = ( # OldNST track, route and new NST track.
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not NST:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, gpx_target = initialize_gpx(FILE_TYPE)

    # Start address of the main part (mixed pause and trackpoint data).
    # We don't read the address from the file because it is useless.
    START_ADDRESS = 0x250 # Not quite sure if this is the best starting point.

    # Track ID and Totaltime.
    f.seek(0x00014 + 0x4, 0) # Go to 0x00014 + 0x4, this address is fixed.
    # 8 (4+4) bytes, little endian U32+U32.
    (TRACK_ID, total_time) = read_unpack('<2I', f)
    print(f'Track ID: {TRACK_ID}')

    total_time /= 100 # Totaltime in seconds.
    print(f'Total time: {format_timedelta(total_time)}')

    # Total Distance.
    f.seek(0x00004, 1) # Skip 4 bytes.  4-byte offset to oldNST due to this.
    (total_distance, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    total_distance /= 1e5 # Total distance in km.
    print(f'Total distance: {round(total_distance, 3)} km')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    stop_localtime = symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    print(f'Start: {format_datetime(start_localtime)}+07:00')
    #print(f'Stop : {format_datetime(stop_localtime)}+07:00')

    # User ID, please see config.dat.
    (USER_ID, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'User id: {USER_ID}')

    # Type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = read_unpack('<H', f) # 2 bytes, little endian U16.
    activities = [
        'Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 
        'Other 3', 'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 
        'Hiking', 'Roller skating', 'Downhill skiing', 'Paddling', 'Rowing', 
        'Golf', 'Indoor']
    description = (activities[activity] if activity < len(activities) 
                   else str(activity))
    print(f'Activity: {description}')

    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases the name consists of 16-byte ASCII characters, e.g. 
    # '24/12/2019 12:34'.  They are not fully compatible with utf-8 in 
    # principle because they can be SCSU-encoded non-ASCII characters.
    track_name = scsu_reader(f, 0x0004a + 0x4) # This address is fixed.
    print(f'Track name: {track_name}')

    # Starttime & Stoptime in UTC.
    f.seek(0x00192 + 0x4, 0) # Go to 0x00192 + 0x4, this address is fixed.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_time, stop_time) = read_unpack('<2q', f)
    start_time = symbian_to_unix_time(start_time)
    stop_time = symbian_to_unix_time(stop_time)
    #print(f'Start Z: {format_datetime(start_time)}Z')
    #print(f'Stop Z : {format_datetime(stop_time)}Z')

    # Timezone can be calculated with the starttimes in Z and in localtime.
    TZ_HOURS = int(start_localtime - start_time) / 3600

    # Read SCSU encoded user comment of variable length.
    comment = scsu_reader(f, 0x00222 + 0x4) # This address is fixed.
    if comment: print(f'Comment: {comment}')


    f.seek(START_ADDRESS, 0) # Go to the start address of the main part.

    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if FILE_TYPE in {ROUTE, TMP} else read_pause_data(f))
    #print_pause_list(pause_list) # For debugging purposes.
    #sys.exit(0)

    # Number of track points.
    NUM_TRACKPT = None # The number in the Rec*.tmp file is useless.
    # Go to the first data.

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

    # For oldNST_route, use mtime as start_time, because the start/stop times 
    # stored are always 0, which means January 1st 0 AD 00:00:00.
    if OLDNST_ROUTE: start_time = in_file.stat().st_mtime
    trackpt_store = TrackptStore() # A temporal storage to pass the trackpt.
    trackpt_store = trackpt_store._replace(
        unix_time=start_time, t_time=0, dist=0)

    # For removing spikes.
    suspect_pause = None # A flag to handle the trackpoints after a pause.

    # Trackpoint and pause data are labeled differently.  Each trackpoint 
    # following this label is always starting with 0x07 header, which means 
    # data with symbian_time. Read the trackpoint data exclusively because we 
    # don't have to use pause data to see the symbian_time.
    (pause_label, track_label) = (b'\x01\x00\x00\x00', b'\x02\x00\x00\x00')

    # The main loop to read the trackpoints.
    while True: # We don't know how many trackpoints exist in the temporal file.

        preceding_label = f.read(len(track_label))
        if len(preceding_label) < len(track_label): # Check end of file.
            break
        elif preceding_label == track_label:
            pointer = f.tell()
            header_fmt = '2B' # 2-byte header.
            num_bytes = struct.calcsize(header_fmt)
            headers = f.read(num_bytes)
            if len(headers) < num_bytes: # Check end of file.
                break
            (header, header1) = struct.unpack(header_fmt, headers)

            if header == 0x07 and header1 in {0x83, 0x82}:
                (Trackpt, fmt) = (TrackptType00, '<I3iHIq')
                # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
                # 30 bytes (4+4+4+4+2+4+8).  Negative y (x) means South (West).
                num_bytes = struct.calcsize(fmt)
                track_data = f.read(num_bytes)
                if len(track_data) < num_bytes: # Check end of file.
                    break
                # Namedtuple wrapped.
                trackpt = Trackpt._make(struct.unpack(fmt, track_data))
                t_time = trackpt.t_time / 100 # Totaltime / seconds.

                # The lat. and lon. are in I32s (DDDmm mmmm format).
                (y_degree, y_mm_mmmm) = divmod(trackpt.y_ax, 1e6)
                (x_degree, x_mm_mmmm) = divmod(trackpt.x_ax, 1e6)
                y_degree += y_mm_mmmm / 1e4 / 60 # Convert minutes to degrees.
                x_degree += x_mm_mmmm / 1e4 / 60

                z_ax = trackpt.z_ax / 10 # Altitude / meter.
                v = trackpt.v / 100 * 3.6 # Velocity: v (m/s) * 3.6 = v (km/h).
                dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance/km.
                unix_time = symbian_to_unix_time(trackpt.symbian_time)
                print_raw_track() # For debugging purposes.

                # Remove spikes: there are lots of errors in the tmp file.
                # TODO: It is better to read and use both the trackpt and pause 
                #       data to correct bad timestamps in the temporal file.
                # In most cases, the two delta_s (~1 s) are equal each other.
                delta_unix_time = unix_time - trackpt_store.unix_time
                delta_t_time = t_time - trackpt_store.t_time
                good_unix_time = 0 < delta_unix_time < 1 * 3600 # Up to 1 hr.
                good_t_time = 0 <= delta_t_time < 5 * 60 # Up to 5 min.

                if track_count == 0 or suspect_pause == True:
                    suspect_pause = False # No time correction; reset the flag.

                # There are four cases due to the two boolean conditions.
                elif good_unix_time and good_t_time:
                    # Set the max of usual pause (suppose traffic signal).
                    # Out of this range is most likely caused by a very long 
                    # pause (e.g. lunch), but might be by an error.
                    if not -0.5 < delta_unix_time - delta_t_time <= 130:
                        (unix_time, t_time) = (
                            t + min(delta_unix_time, delta_t_time) for t in 
                            (trackpt_store.unix_time, trackpt_store.t_time))
                        # Set the flag to see if this is because of a pause.
                        suspect_pause = True
                        print(f'Bad.  Two distinct delta_s at: {hex(pointer)}')
                elif (not good_unix_time) and good_t_time:
                    # Correct unixtime by using totaltime.
                    unix_time = trackpt_store.unix_time + delta_t_time
                    print(f'Bad unixtime at: {hex(pointer)}')
                elif (not good_unix_time) and (not good_t_time):
                    # Add 0.2 s (should be < 1.0 s) to both, as a compromise.
                    (unix_time, t_time) = (
                        t + 0.2 for t in
                        (trackpt_store.unix_time, trackpt_store.t_time))
                    print(f'Bad unixtime and totaltime at: {hex(pointer)}')
                else: # good_unix_time and (not good_t_time)
                    # Correct totaltime by using unixtime.
                    t_time = trackpt_store.t_time + delta_unix_time
                    print(f'Bad totaltime at: {hex(pointer)}')

                if track_count > 0: # Use previous values for spikes in y, x, z 
                    # and total_distance.  Interpolation would be better choice.
                    if abs(trackpt_store.y_degree - y_degree) >= 0.001: # deg.
                        y_degree = trackpt_store.y_degree
                        print(f'Bad y at: {hex(pointer)}')
                    if abs(trackpt_store.x_degree - x_degree) >= 0.001:
                        x_degree = trackpt_store.x_degree
                        print(f'Bad x at: {hex(pointer)}')
                    if abs(trackpt_store.z_ax - z_ax) >= 500: # Meter.
                        z_ax = trackpt_store.z_ax
                if not 0 <= dist - trackpt_store.dist < 1: # Up to 1 km.
                    dist = trackpt_store.dist

            else: # Other headers which I don't know.
                if not (header == 0x00 and header1 == 0x00):
                    print_other_header_error()
                continue
                #break

            trackpt_store = TrackptStore(
                unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
                x_degree=x_degree, z_ax=z_ax, v=v, d_dist=trackpt.d_dist / 1e5, 
                dist=dist, track_count=track_count, file_type=FILE_TYPE)
            store_trackpt(trackpt_store)

            track_count += 1


        else:
            f.seek(-3, 1) # Seek forward (4 - 3 = +1 byte).

finalize_gpx(gpx, FILE_TYPE, write_file=True) # True=write file, False=print.
