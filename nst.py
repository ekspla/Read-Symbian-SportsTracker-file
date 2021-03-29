#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""A module for reading Symbian (Nokia) SportsTracker files.

Constants depend on versions and file types (see scripts how to determine):
              NEW_FORMAT  FILE_TYPE     START_LOCALTIME, START_TIME and TZ_HOURS
--------------------------------------------------------------------------------
Ver0 TRACK:            0          2         required.
Ver1 ROUTE:            0          3         None (not available).
Ver1 TRACK:            1          2         required.
Ver2 TRACK:            1          2         required.
Ver2 TMP:              1          4         required.

A track (or route) is parsed as follows:
1) Read and store START_LOCALTIME and START_TIME (in UTC); None in route files.
   Store TZ_HOURS, which means timezone as a difference in hours from UTC.
2) Move the pointer of file_obj to start_address of the main part that contain
   pause (not in route) and track.  Use read_pause_data() to make a pause_list.
3) Track data part is succeeding the pause part.  Use read_trackpoints() to
   read / process / adjust timestamp of trackpoints.  The pause_list described
   above is used in adjusting timestamps.  While reading the trackpoints, each
   trackpoint after processing is temporally stored in trackpt_store which is
   handed to store_trackpt() for recording.
"""
import sys
import struct
import datetime as dt
from collections import namedtuple
from pathlib import Path

import scsu
from mini_gpx import Gpx

# Initialize variables.
(total_time, total_distance) = (0, ) * 2
(comment, route_name, track_name, TZ_HOURS, START_LOCALTIME, activity_type, 
    USER_ID, START_TIME, NEW_FORMAT, FILE_TYPE, gpx_target) = (None, ) * 11

# Constants.
ACTIVITIES = ('Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 
              'Other 3', 'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 
              'Hiking', 'Roller skating', 'Downhill skiing', 'Paddling', 
              'Rowing', 'Golf', 'Indoor') # Types of activities.
(CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
APP_ID = 0x0e4935e8

def symbian_to_unix_time(symbiantime):
    """Convert a timestamp from symbiantime to unixtime.

    Symbiantimes are 64-bit values that represent microsecs since 1 Jan. 0 AD
    00:00:00 localtime, nominal Gregorian.  Negative values represent BC dates.
    """
    return (symbiantime - 62168256000 * 10**6) / 10**6 # Integer in parentheses.

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

def format_datetime(timestamp):
    """Returns ISO-8601 strings of millisec. precision from unixtime (sec)."""
    d_t = dt_from_timestamp(round(timestamp, 3))
    return (d_t.isoformat(timespec='milliseconds') if d_t is not None 
            else f'INVALID({timestamp})')

def format_timedelta(t_delta):
    """Returns formatted strings of ms precision from positive timedelta (sec).

    >>> format_timedelta(93825.6789)
    '1 day, 2:03:45.679'
    >>> format_timedelta(3723)
    '1:02:03.000'
    """
    (int_td, frac_td) = divmod(round(t_delta, 3), 1)
    return f'{dt.timedelta(seconds=int_td)}.' + f'{frac_td:.3f}'.split('.')[1]

def read_unpack(struct_fmt, file_object):
    """A helper function comprising file_object.read() and struct.unpack()."""
    size = struct.calcsize(struct_fmt)
    return struct.unpack(struct_fmt, file_object.read(size))

def scsu_reader(file_object, address=None):
    """Reads variable-length SCSU bytes and returns UTF-8 using scsu.py.

    Args:
        file_object: the file object to be read.
        address (optional): start address of the SCSU encoded part.  The data 
            is preceded by one/two byte integer which indicates the character 
            length multiplied by four/eight.

    Returns:
        decoded_strings: strings of UTF-8.
    """
    if address is not None: file_object.seek(address, 0)
    (size, ) = read_unpack('B', file_object) # U8, character_length * 4.
    if size & 0x1: # If LSB == 1: char_len >= 64. If LSB == 0: char_len < 64.
        (size, ) = struct.unpack('<H', bytes([size]) + file_object.read(1))
        size >>= 1 # Divide character_length * 8 (U16) by 2 to get length * 4.

    start_of_scsu = file_object.tell()
    in_bytes = file_object.read(size) # Character_length * 4 is sufficient.
    size >>= 2 # Divide by 4 to obtain the character_length.
    (out_array, byte_length, character_length) = scsu.decode(in_bytes, size)
    del character_length # Not in use.  We will check the length as shown below.

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

def store_trackpt(tp, file_type=None):
    """Do whatever with the trackpt data: print, gpx, store in a database, etc.

    Args:
        tp (a namedtuple of trackpt_store):
            (unix_time(s), t_time(s), y_degree, x_degree, z_ax(m), v(cm/s), 
             d_dist(cm), dist(cm), track_count(int), file_type(int: 2, 3 or 4))
        target (optional): gpx_route or gpx_segment. Defaults to gpx_target.
    """
    # Print delimited text.
    #times = f'{format_timedelta(tp.t_time)}\t{format_datetime(tp.unix_time)}Z'
    #print(f'{times}\t{tp.d_dist / 10**5:.3f}\t{tp.dist / 10**5:.3f}\t'
    #      f'{tp.y_degree:.6f}\t{tp.x_degree:.6f}\t{tp.z_ax:.1f}\t'
    #      f'{tp.v / 100 * 3.6:.3f}')
    if file_type is None: file_type = FILE_TYPE
    append_pt = gpx.append_trkpt if file_type in {TRACK, TMP} else gpx.append_rtept
    speed = round(tp.v / 100, 3) # velocity in m/s
    append_pt(
        lat=round(tp.y_degree, 6), # 1e-6 ~ 10 cm precision.
        lon=round(tp.x_degree, 6), 
        ele=round(tp.z_ax, 1), 
        time=dt_from_timestamp(tp.unix_time, dt.timezone.utc), 
        name=str(tp.track_count + 1),
        desc = (f'Speed {round(tp.v / 100 * 3.6, 3)} km/h '
                f'Distance {round(tp.dist / 10**5, 3)} km'),
        speed = f'{speed}')

def initialize_gpx(file_type=None):
    """Initialize a route or a track segment (determined by the file_type).

    Args:
        file_type (optional): int. 2, 3 or 4.  Defaults to FILE_TYPE.

    Returns:
        gpx
    """
    if file_type is None: file_type = FILE_TYPE
    gpx = Gpx(is_track=False) if file_type == ROUTE else Gpx()
    return gpx

def add_gpx_summary(gpx, tp_store):
    """Add a short summary (time, distance, speed, etc.) to gpx route/track.

    Args:
        gpx
        tp_store (namedtuple): the last trackpt_store in the route/track.

    Requires (in tracks):
        START_LOCALTIME, START_TIME, TZ_HOURS.  See module-level docstring.
    """
    total_time_ = total_time or tp_store.t_time
    total_distance_ = total_distance or tp_store.dist / 10**5
    net_speed = total_distance_ / (total_time_ / 3600) # km/h.
    description = ('[' f'Total time: {format_timedelta(total_time_)}' '; '
                   f'Total distance: {round(total_distance_, 3)} km' '; '
                   f'Net speed: {round(net_speed, 3)} km/h')

    if tp_store.file_type == ROUTE:
        name = f'[{route_name}]'
        description = f'{description}' ']'
        (gpx_description, author) = ('', ) * 2
        time = None

    else: # Track files.
        name = f'[{track_name}]'
        stop_localtime_ = (
            stop_localtime if stop_localtime > START_LOCALTIME
            else tp_store.unix_time + TZ_HOURS * 3600)
        real_time = stop_localtime_ - START_LOCALTIME
        gross_speed = total_distance_ / (real_time / 3600) # km/h.
        description = (
            f'{description}' '; '
            f'Start localtime: {format_datetime(START_LOCALTIME)}' '; '
            f'Stop localtime: {format_datetime(stop_localtime_)}' '; '
            f'Real time: {format_timedelta(real_time)}' '; '
            f'Gross speed: {round(gross_speed, 3)} km/h' ']')
        gpx_description = f'[{activity_type}]' # See ACTIVITIES.
        author = str(USER_ID)
        time = dt_from_timestamp(
            START_TIME, dt.timezone(dt.timedelta(hours=TZ_HOURS), ))
    gpx.add_metadata(name=name, description=gpx_description, author=author, time=time)
    gpx.add_summary(name=name, comment=comment, description=description)


def finalize_gpx(gpx, outfile_path=None):
    """Output gpx xml to the outfile_path (or print if not specified).

    Args:
        gpx
        outfile_path (optional): write gpx xml to the file or print (if None).
    """
    result = gpx.to_xml() # bytes
    if outfile_path is not None:
        with outfile_path.open(mode='wb') as f:
            f.write(result)
    else:
        print(result.decode())

DEBUG_READ_PAUSE = False
def read_pause_data(file_obj, new_format=None):
    """Make a list of t_time, pause_time and unix_time from the file_object.

    Args:
        file_object: the pointer should be at start_address prior to read.
        new_format (optional, bool):  True/False = new/old format trackpoint.
            Defaults to module-level NEW_FORMAT.

    Returns:
        pause_list: the list of tuples of (t_time, pause_time, unix_time).
        pause_count: number of pause data read.
    """
    if new_format is None: new_format = NEW_FORMAT
    (num_pause, ) = read_unpack('<I', file_obj) # 4 bytes, little endian U32.
    if DEBUG_READ_PAUSE:
        print(f'Number of pause data: {num_pause}')
        print(f'Pause address: {hex(file_obj.tell())}') # START_ADDRESS + 4

    def print_raw_data(): # For debugging purposes.
        utctime = f'{format_datetime(unix_time)}' # The old ver. in localtime.
        if new_format: utctime += 'Z' # The new version NST in UTC (Z).
        print(f'{unknown}\t{format_timedelta(t_time)}\t{flag}\t{utctime}')

    (pause_list, pause_count) = ([], 0)
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
            if t4_time != t_time: # A suspend-resume pair has a common t_time.
                print('Error in pause.')
                sys.exit(1)
            pause_time = unix_time - suspendtime
            pause_list.append((t_time, pause_time, unix_time))

        elif flag == flag_8: # Use it as a correction of time.
            pause_time = 0
            pause_list.append((t_time, pause_time, unix_time))

        else: # Other flags which I don't know.
            print(f'Unknown flag in pause: {flag:#x}')
            sys.exit(1)

        pause_count += 1

    del unknown, starttime, start_t_time
    if 'stoptime' in locals(): del stoptime, stop_t_time # For files w/o stop.
    return pause_list, pause_count

def print_pause_list(pause_list, new_format=None):
    """Print formatted pause_list, maybe useful in analyzing track files."""
    if new_format is None: new_format = NEW_FORMAT
    d_t = 'Datetime Z' if new_format else 'Datetime local'
    print('Total time', '\t', 'Pause time', '\t', d_t, sep ='')
    for (t_time, pause_time, unix_time) in pause_list:
        print(f'{format_timedelta(t_time)}\t{format_timedelta(pause_time)}\t'
              f'{format_datetime(unix_time)}')
    print()

def prepare_namedtuples(new_format=None):
    """Factory functions of namedtuples used in reading/processing trackpoints.

    Args:
        new_format (optional, bool):  True/False = new/old format trackpoint.
            Defaults to module-level NEW_FORMAT.

    Returns:
        TrackptType00, TrackptType80, TrackptTypeC0: used to wrap after reading.
        TrackptStore: used to wrap a trackpoint after processing.
    """
    if new_format is None: new_format = NEW_FORMAT
    type00 = 't_time, y_ax, x_ax, z_ax, v, d_dist'
    type80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist'
    typec0 = 'dt_time, unknown1, dy_ax, dx_ax, unknown2, dz_ax, dv, d_dist'
    if new_format: # The fields shown below are added in the new version format.
        type00 += ', symbian_time'
        type80, typec0 = (t + ', dunix_time' for t in (type80, typec0))
    type_store = ('unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, '
                  'dist, track_count, file_type')
    TrackptType00_ = namedtuple('TrackptType00', type00)
    TrackptType80_ = namedtuple('TrackptType80', type80)
    TrackptTypeC0_ = namedtuple('TrackptTypeC0', typec0)
    TrackptStore_ = namedtuple('TrackptStore', type_store)
    TrackptStore_.__new__.__defaults__ = (None,) * len(TrackptStore_._fields)
    return TrackptType00_, TrackptType80_, TrackptTypeC0_, TrackptStore_

def process_trackpt_type00(tp, tp_store, new_format=None):
    """Process a trackpoint (tp) of the type with the previous one (tp_store).

    Args:
        tp: namedtuple of a trackpoint data after read, to be processed.
        tp_store: namedtuple of a processed data of the previous trackpoint.
        new_format (optional, bool):  True/False = new/old format trackpoint.
            Defaults to module-level NEW_FORMAT.

    Returns:
        unix_time, t_time, y, x, z, v, d_dist, dist
    """
    if new_format is None: new_format = NEW_FORMAT
    t_time = tp.t_time / 100 # Totaltime / second.
    # In contrast to the new format, we have to calculate the timestamps in 
    # all of the trackpts because of no symbiantimes given in the old format.
    unix_time = (symbian_to_unix_time(tp.symbian_time) if new_format
                 else tp_store.unix_time + (t_time - tp_store.t_time))

    # The lat. and lon. (DDDmm mmmm format, I32) are converted to dec. degrees.
    (y, x) = (dmm_to_decdeg(tp.y_ax), dmm_to_decdeg(tp.x_ax))
    z = tp.z_ax / 10 # Altitude (meter).
    # Don't change the units here. Resolutions never decrease by int. additions.
    v = tp.v # Int. velocity (cm/s).
    d_dist = tp.d_dist # Int. delta distance (cm).
    dist = tp_store.dist + d_dist # Int. distance (cm).

    return unix_time, t_time, y, x, z, v, d_dist, dist

def process_trackpt_type80(tp, tp_store, new_format=None):
    """Process a trackpoint (tp) of the type with the previous one (tp_store).

    Args:
        tp: namedtuple of a trackpoint data after read, to be processed.
        tp_store: namedtuple of a processed data of the previous trackpoint.
        new_format (optional, bool):  True/False = new/old format trackpoint.
            Defaults to module-level NEW_FORMAT.

    Returns:
        unix_time, t_time, y, x, z, v, d_dist, dist
    """
    if new_format is None: new_format = NEW_FORMAT
    t_time = tp_store.t_time + tp.dt_time / 100 # Totaltime/s.
    unix_time = tp_store.unix_time + (tp.dunix_time if new_format 
                                      else tp.dt_time) / 100

    y = tp_store.y_degree + tp.dy_ax / 10**4 / 60 # Lat.
    x = tp_store.x_degree + tp.dx_ax / 10**4 / 60 # Lon.
    z = tp_store.z_ax + tp.dz_ax / 10 # Altitude (m).
    # Don't change the units here. Resolutions never decrease by int. additions.
    v = tp_store.v + tp.dv # Int. velocity (cm/s).
    d_dist = tp.d_dist # Int. delta distance (cm).
    dist = tp_store.dist + d_dist # Int. distance (cm).

    return unix_time, t_time, y, x, z, v, d_dist, dist

(DEBUG_READ_TRACK, PRINT_NUM_TRACKPT_ADDRESS) = (False, False)
def read_trackpoints(file_obj, pause_list=None): # No pause_list if ROUTE.
    """Read/process/store trackpoints.  Uses a few global constant (see below).

    Args:
        file_obj: the pointer must be at an appropriate position prior to read.
        pause_list (optional): a list obtained from read_pause_data().

    Returns:
        track_count: number of trackpoints read.
        trackpt_store: a namedtuple of the last trackpoint after processing.

    Requires:
        FILE_TYPE (int), NEW_FORMAT (bool), TZ_HOURS (old tracks),
        START_TIME (tracks).  See module-level docstrings for details.
    """
    def print_raw(t_time, unix_time, hdr, tp):
        times = f'{t_time} {format_datetime(unix_time)}Z'
        # Remove symbiantime from trackpt if new format and header == 0x07.
        trackpt_ = tp[1:-1] if NEW_FORMAT and hdr == 0x07 else tp[1:]
        print(hex(file_obj.tell()), hex(hdr), times, *trackpt_)

    def print_other_header_error(ptr, hdr): # pointer, header.
        print(f'{hdr:#x} Error in the track point header: {track_count}, '
              f'{num_trackpt}' '\n' f'At address: {ptr:#x}')

    def read_old_fmt_trackpt():
        """Read/process/time-adjust old-format trackpt, store in trackpt_store.

        Returns:
            1 (error) or 0 (success).
        """
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
                # (dt_time, unknown1, dy_ax, dx_ax, unknown2, dz_ax, dv, d_dist)
                # Unknown1 & 2 show up in distant jumps.

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
            process_trackpt(trackpt, trackpt_store)) # Using tp & the previous.
        if DEBUG_READ_TRACK: print_raw(t_time, unix_time, header, trackpt)

        if pause_list: # Adjust unix_time by using pause_list.
            t4_time, pause_time, resume_time = pause_list[0]

            if t_time + 0.5 >= t4_time: # After a pause, use the pause data.
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

    def read_new_fmt_trackpt():
        """Read/process/time-adjust new-format trackpt, store in trackpt_store.

        Returns:
            1 (error) or 0 (success).
        """
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

        elif header in {0x87, 0x97, 0x9F, 0xC7, 0xD7, 0xDF}:
            process_trackpt = process_trackpt_type80

            if header in {0x87, 0x97, 0x9F}: # Typically 8783, 8782, 9783, 9782.
                Trackpt = TrackptType80
                # (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist, dunix_time)
                if header == 0x87: # 1-byte dv.
                    fmt = '<B3hb2H' # 12 bytes (1+2+2+2+1+2+2).
                elif header == 0x97: # 2-byte dv.
                    fmt = '<B4h2H' # 13 bytes (1+2+2+2+2+2+2).
                else: # header == 0x9F # 2-byte dv, 4-byte d_dist.
                    fmt = '<B4hiH' # 15 bytes (1+2+2+2+2+4+2).

            else: # {0xC7, 0xD7, 0xDF}. C783, C782, D783, D782: Rare cases.
                Trackpt = TrackptTypeC0
                # (dt_time, unknown1, dy_ax, dx_ax, unknown2, dz_ax, dv, d_dist,
                # dunix_time); Unknown1 & 2 show up in distant jumps.
                if header == 0xC7: # 1-byte dv.
                    fmt = '<B5hb2H' # 16 bytes (1+2+2+2+2+2+1+2+2).
                elif header == 0xD7: # 2-byte dv.
                    fmt = '<B6h2H' # 17 bytes (1+2+2+2+2+2+2+2+2).
                else: # 0xDF # 2-byte dv, 4-byte d_dist.
                    fmt = '<B6hiH' # 19 bytes (1+2+2+2+2+2+2+4+2).

        else: # Other headers which I don't know.
            print_other_header_error(pointer, header)
            return 1

        trackpt = Trackpt._make(read_unpack(fmt, file_obj)) # Read and wrap.

        unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, dist = (
            process_trackpt(trackpt, trackpt_store)) # Using tp & the previous.
        if DEBUG_READ_TRACK: print_raw(t_time, unix_time, header, trackpt)

        if pause_list: # Adjust unix_time by using pause_list.
            t4_time, pause_time, resume_time = pause_list[0]

            if t_time + 0.5 >= t4_time: # After a pause, use the pause data.
                del pause_list[0]
                if DEBUG_READ_TRACK: print(f'Pause time: {pause_time}')

                if header != 0x07 and unix_time < resume_time: # No symbiantime.
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time

        trackpt_store = TrackptStore(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=d_dist, 
            dist=dist, track_count=track_count, file_type=FILE_TYPE)

        return 0


    # Number of track points.
    (num_trackpt, ) = read_unpack('<I', file_obj) # 4 bytes, little endian U32.
    if PRINT_NUM_TRACKPT_ADDRESS:
        print(f'Number of track/route pts: {num_trackpt}')
        print(f'Track address: {hex(file_obj.tell())}')

    # Factory functions for creating named tuples.
    TrackptType00, TrackptType80, TrackptTypeC0, TrackptStore = (
        prepare_namedtuples())

    # For ROUTE, use mtime as starttime because no start/stop times are given.
    starttime = (Path(file_obj.name).stat().st_mtime if FILE_TYPE == ROUTE 
                 else START_TIME)
    # A temporal storage for the processed trackpt.
    trackpt_store = TrackptStore(unix_time=starttime, t_time=0, dist=0)

    # This is the main loop.
    track_count = 0
    read_trackpt = read_new_fmt_trackpt if NEW_FORMAT else read_old_fmt_trackpt
    while track_count < num_trackpt:

        exit_code = read_trackpt() # In trackpt_store, after processing.
        if exit_code: break

        store_trackpt(trackpt_store)

        track_count += 1

    # Handling of errors.
    if track_count != num_trackpt:
        print(f'Trackpoint count error: {track_count}, {num_trackpt}')
        print(*trackpt_store)
        sys.exit(1)

    else:
        return track_count, trackpt_store

