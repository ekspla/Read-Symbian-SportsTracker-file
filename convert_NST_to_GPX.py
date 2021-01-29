#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads track log files of SportsTracker.
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


#  Symbiantimes are 64-bit values that represents microsecs since 1 Jan. 0 AD 
#  00:00:00 localtime, nominal Gregorian.  Negative values represent BC dates.
def symbian_to_unix_time(symbiantime):
    return symbiantime / 1e6 - 62168256000

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

def dmm_to_decdeg(dmm):
    """Convert signed int. DDDMM MMMM format to decimal degree.
    
    >>> dmm_to_decdeg(45300000)
    45.5
    >>> dmm_to_decdeg(-135150000)
    -135.25
    """
    sign_dmm = (dmm > 0) - (dmm < 0)
    (decimal_degree, mm_mmmm) = divmod(abs(dmm), 1e6)
    decimal_degree += mm_mmmm / 1e4 / 60
    return sign_dmm * decimal_degree

def store_trackpt(tp):
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

    write_file = False if write_file is None else write_file
    if write_file: # Finally, print or write the gpx.
        gpx_file = Path(str(in_file)[:-3] + 'gpx')
        result = gpx_.to_xml('1.1')
        result_file = open(gpx_file, 'w')
        result_file.write(result)
        result_file.close()
    else:
        print(gpx_.to_xml('1.1'))

def read_pause_data(file_obj):
    (num_pause, ) = read_unpack('<I', file_obj) # 4 bytes, little endian U32.
    #print(f'Number of pause data: {num_pause}')
    #pause_address = file_obj.tell() # START_ADDRESS + 4
    #print(f'Pause address: {hex(pause_address)}')

    def print_raw_data(): # For debugging purposes.
        utctime = f'{format_datetime(unixtime)}' # The old ver. in localtime.
        if NST: utctime += 'Z' # The new version NST in UTC (Z).
        print(f'{unknown}\t{format_timedelta(to_time)}\t{flag}\t{utctime}')

    p_count = 0 # pause_count
    p_list = [] # pause_list

    while p_count < num_pause:
        # Read 14 bytes of data(1+4+1+8).  Symbiantimes of the old version are 
        # in localtime zone, while those of the new version in UTC (Z).
        # The first unknown field (always 0x01) seems to have no meaning.
        (unknown, to_time, flag, symbiantime) = read_unpack('<BIBq', file_obj)

        to_time /= 100 # Totaltime in seconds.
        unixtime = symbian_to_unix_time(symbiantime)
        #print_raw_data() # For debugging purposes.

        # Start: we don't use these data.  Store them for the future purposes.
        if flag == 1:
            starttime = unixtime
            start_t_time = to_time
        # Stop: we don't use these data.  Store them for the future purposes.
        elif flag == 2:
            stoptime = unixtime
            stop_t_time = to_time
        # Suspend: flag = 3 (manually) or 4 (automatically).
        elif flag in {3, 4}:
            suspendtime = unixtime
            to4_time = to_time
        # Resume.  A suspend--resume pair should have a common totaltime.
        elif flag == 5:
            if to4_time != to_time:
                print('Error in pause.')
                sys.exit(1)
            p_time = unixtime - suspendtime # Time between suspend and resume.
            p_list.append((to_time, p_time, unixtime))
        # Flag = 8.  Use it as a correction of time.
        elif flag == 8:
            p_time = 0
            p_list.append((to_time, p_time, unixtime))

        p_count += 1

    del unknown, starttime, start_t_time, stoptime, stop_t_time
    return p_list, p_count

def print_pause_list(p_list):
    d_t = 'Datetime Z' if NST else 'Datetime local'
    print('Total time', '\t', 'Pause time', '\t', d_t, sep ='')
    for p in p_list:
        to_time, p_time, unixtime = p
        print(f'{format_timedelta(to_time)}\t{format_timedelta(p_time)}\t'
              f'{format_datetime(unixtime)}')
    print()

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
        This script reads track log files (W*.dat) of symbian SportsTracker.
        Log files with heart-rate sensor were not tested.""")
    sys.exit(0)
#print(argvs[1])
in_file = Path(argvs[1])
#print(in_file)


track_name, route_name, comment = (None for x in range(3))
with in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    #f.seek(0x00000, 0)
    # 8 (4+4) bytes, little endian U32+U32.
    (APPLICATION_ID, FILE_TYPE) = read_unpack('<2I', f)
    (CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
    if APPLICATION_ID != 0x0e4935e8 or FILE_TYPE != TRACK:
        print(f'Unexpected file type: {FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Version: {version}')
    (OLDNST, OLDNST_ROUTE, NST) = ( # OldNST track, route and new NST track.
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not NST:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, gpx_target = initialize_gpx(FILE_TYPE)

    # Start address of the main part (a pause data block and a trackpt block).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    (START_ADDRESS, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    START_ADDRESS -= 1
    #print(f'Main part address: {hex(START_ADDRESS)}')

    # Track ID and Totaltime.
    track_id_addr = 0x00014 # Fixed addresses of oldNST and the new NST track.
    if FILE_TYPE == TMP: track_id_addr += 0x04 # The 4-byte blank (0x18).
    f.seek(track_id_addr, 0) # 8 (4+4) bytes, little endian U32+U32.
    (TRACK_ID, total_time) = read_unpack('<2I', f)
    #print(f'Track ID: {TRACK_ID}')

    total_time /= 100 # Totaltime in seconds.
    #print(f'Total time: {format_timedelta(total_time)}')

    # Total Distance.
    if NST: f.seek(0x00004, 1) # Skip.  4-byte offset to oldNST due to this.
    (total_distance, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    total_distance /= 1e5 # Total distance in km.
    #print(f'Total distance: {round(total_distance, 3)} km')

    # Calculate Net speed in km/h.
    net_speed = total_distance / (total_time / 3600) # km/h
    #print(f'Net speed: {round(net_speed, 3)} km/h')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    stop_localtime = symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    #print(f'Start: {format_datetime(start_localtime)}+09:00')
    #print(f'Stop : {format_datetime(stop_localtime)}+09:00')

    # Calculate Realtime, which is greater than totaltime if pause is used.
    real_time = stop_localtime - start_localtime # Realtime in seconds.
    #print(f'Realtime: {format_timedelta(real_time)}')

    # Calculate Gross speed in km/h.
    gross_speed = total_distance / (real_time / 3600) # km/h
    #print(f'Gross speed: {round(gross_speed, 3)} km/h')

    # User ID, please see config.dat.
    (USER_ID, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'User id: {USER_ID}')

    # Type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = read_unpack('<H', f) # 2 bytes, little endian U16.
    a_list = ['Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 
        'Other 3', 'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 
        'Hiking', 'Roller skating', 'Downhill skiing', 'Paddling', 'Rowing', 
        'Golf', 'Indoor']
    description = a_list[activity] if activity < len(a_list) else str(activity)
    #print(f'Activity: {description}')

    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases the name consists of 16-byte ASCII characters, e.g. 
    # '24/12/2019 12:34'.  They are not fully compatible with utf-8 in 
    # principle because they can be SCSU-encoded non-ASCII characters.
    track_name_addr = 0x00046 # This is the fixed address of the oldNST track.
    if NST: track_name_addr += 0x04 # Offset at total_distance (-> 0x4a).
    if FILE_TYPE == TMP: track_name_addr += 0x04 # The 4-byte blank (-> 0x4e).
    track_name = scsu_reader(f, track_name_addr)
    #print(f'Track name: {track_name}')

    # Starttime & Stoptime in UTC.
    start_stop_z_addr = 0x0018e # This is the fixed address of oldNST track.
    if NST: start_stop_z_addr += 0x04 # Offset at total_distance (0x192).
    if FILE_TYPE == TMP: start_stop_z_addr += 0x04 # The 4-byte blank (0x196).
    f.seek(start_stop_z_addr, 0) # 16 (8+8) bytes, little endian I64+I64.
    (start_time, stop_time) = read_unpack('<2q', f)
    start_time = symbian_to_unix_time(start_time)
    stop_time = symbian_to_unix_time(stop_time)
    #print(f'Start Z: {format_datetime(start_time)}Z')
    #print(f'Stop Z : {format_datetime(stop_time)}Z')

    # Timezone can be calculated with the starttimes in Z and in localtime.
    TZ_HOURS = int(start_localtime - start_time) / 3600

    # This will overwrite the realtime shown above.
    real_time = stop_time - start_time # Realtime in seconds.
    #print(f'Realtime Z: {format_timedelta(real_time)}')

    # Read SCSU encoded user comment of variable length.
    comment_addr = 0x00222 # Fixed address of NST tracks.
    if FILE_TYPE == TMP: comment_addr += 0x4 # The 4-byte blank (0x226).
    comment = scsu_reader(f, comment_addr) # This address is fixed.
    #if comment: print(f'Comment: {comment}')


    f.seek(START_ADDRESS, 0) # Go to the start address of the main part.

    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if FILE_TYPE in {ROUTE, TMP} else read_pause_data(f))
    #print_pause_list(pause_list) # For debugging purposes.
    #sys.exit(0)

    # Number of track points.
    (NUM_TRACKPT, ) = read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Number of track/route pts: {NUM_TRACKPT}')
    #TRACK_ADDRESS = f.tell()
    #print(f'Track address: {hex(TRACK_ADDRESS)}')
    #f.seek(TRACK_ADDRESS, 0) # Go to the first trackpoint.

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

    # For oldNST_route, use mtime as start_time because the start/stop times 
    # stored are always 0 which means January 1st 0 AD 00:00:00.
    if OLDNST_ROUTE: start_time = in_file.stat().st_mtime
    trackpt_store = TrackptStore() # A temporal storage to pass the trackpt.
    trackpt_store = trackpt_store._replace(
        unix_time=start_time, t_time=0, dist=0)

    # The main loop to read the trackpoints.
    while track_count < NUM_TRACKPT:
        pointer = f.tell()
        header_fmt = '2B' # 2-byte header.
        (header, header1) = read_unpack(header_fmt, f)

        if header == 0x07: # Typically, 0783 or 0782.
            (Trackpt, fmt) = (TrackptType00, '<I3iHIq')
            # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
            # 30 bytes (4+4+4+4+2+4+8).  y(+/-): N/S; x(+/-): E/W.
            trackpt = Trackpt._make(read_unpack(fmt, f)) # Namedtuple wrapped.

            t_time = trackpt.t_time / 100 # Totaltime / second.

            # The lat. and lon. are in I32s (DDDmm mmmm format).
            y_degree = dmm_to_decdeg(trackpt.y_ax)# Convert to decimal degrees.
            x_degree = dmm_to_decdeg(trackpt.x_ax)

            z_ax = trackpt.z_ax / 10 # Altitude / meter.
            v = trackpt.v / 100 * 3.6 # Velocity: v (m/s) * 3.6 = v (km/h).
            dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance/km.
            unix_time = symbian_to_unix_time(trackpt.symbian_time)
            #print_raw_track() # For debugging purposes.

        elif header in {0x87, 0x97, 0xC7, 0xD7}:

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

            trackpt = Trackpt._make(read_unpack(fmt, f)) # Namedtuple wrapped.

            t_time = trackpt_store.t_time + trackpt.dt_time / 100 # Totaltime/s.

            y_degree = trackpt_store.y_degree + trackpt.dy_ax / 1e4 / 60 # Lat.
            x_degree = trackpt_store.x_degree + trackpt.dx_ax / 1e4 / 60 # Lon.

            z_ax = trackpt_store.z_ax + trackpt.dz_ax / 10 # Altitude / m.
            v = trackpt_store.v + trackpt.dv / 100 * 3.6 # Velocity / km/h.
            dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance / km.
            unix_time = trackpt_store.unix_time + trackpt.dt_time / 100
            #print_raw_track() # For debugging purposes.

        else: # Other headers which I don't know.
            print_other_header_error()
            break

        if pause_list:
            t4_time, pause_time, resume_time = pause_list[0]

            # Just after the pause, use the pause data.
            if t_time + 0.5 >= t4_time:

                if header != 0x07: # The trackpoint lacks for symbiantime.
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time

                del pause_list[0]

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
