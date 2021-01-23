#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site
# under LGPL v2.1 license.
# https://github.com/ekspla/Read-Symbian-SportsTracker-file
#
import sys
from pathlib import Path
import struct
import datetime as dt
from collections import namedtuple

import gpxpy
import gpxpy.gpx

try:
    # Load LXML or fallback to cET or ET 
    import lxml.etree as mod_etree  # type: ignore
except:
    try:
        import xml.etree.cElementTree as mod_etree # type: ignore
    except:
        import xml.etree.ElementTree as mod_etree # type: ignore

import scsu


#  The native Symbian time format is a 64-bit value that represents 
#  microseconds since January 1st 0 AD 00:00:00 local time, nominal Gregorian.
#  BC dates are represented by negative values.
def symbian_to_unix_time(symbian_time):
    unix_time = symbian_time / 1e6 - 62168256000
    return unix_time

# A workaround of dt.datetime.fromtimestamp() for handling the full range of datetimes in a few platforms after the year 2038.
def dt_from_timestamp(timestamp, tz_info=None):
    workaround = False # True: use the workaround.  False: use dt.datetime.fromtimestamp().
    if workaround and -62135596800 <= timestamp < 253402300800: # From 0001-01-01T00:00:00 to 9999-12-31T23:59:59.
        d_t = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
        d_t += dt.timedelta(seconds=1) * timestamp
        return (d_t.replace(tzinfo=None) if tz_info is None 
                else d_t.astimezone(tz_info))
    elif (not workaround) and 0 <= timestamp < 32536799999: # From 1970-01-01T00:00:00 to 3001-01-19T07:59:59.  The range depends on your platform.
        d_t = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
        return (d_t.replace(tzinfo=None) if tz_info is None 
                else d_t.astimezone(tz_info))
    else:
        return None

def format_datetime(timestamp):
    d_t = dt_from_timestamp(round(timestamp, 3))
    return (d_t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if d_t != None # ISO-8601 format.
            else f'INVALID({timestamp})')

def format_timedelta(t_delta):
    return str(dt.timedelta(seconds = round(t_delta, 3)))[:-3]

# Helper function to read and unpack.
def read_unpack(fmt, file_object):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, file_object.read(size))

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
    if address:
        file_object.seek(address, 0)
    (size, ) = read_unpack('B', file_object) # U8.  Read the size * 4 in bytes.
    if size & 0x1: # If LSB == 1, character_length >= 64.
        (size, ) = struct.unpack('<H', bytes([size]) + file_object.read(1)) # U16.  Read the size * 8 in bytes.
        size >>= 1 # Divide by 2.
    # Else if LSB == 0, character_length < 64.
    start_of_scsu = file_object.tell()
    in_bytes = file_object.read(size)
    size >>= 2 # Divide by 4 to obtain the character_length.
    (out_array, byte_length, character_length) = scsu.decode(in_bytes, size)
    decoded_strings = out_array.decode('utf-8', 'ignore') # Sanitize and check the length.
    if len(decoded_strings) != size:
        print('SCSU decode failed.', out_array)
        quit()
    file_object.seek(start_of_scsu + byte_length, 0) # Go to the next field.
    return decoded_strings

def store_trackpt(tp): # Do whatever with the trackpoint data: print, write gpx or store it in a database, etc. 
    # tp: 'unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, dist, track_count, file_type'
    # in:        sec,    sec,    deg.,     deg.,   m, km/h,  km,   km,   int. number, (track=2, route=3, tmp=4)
    
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
        latitude = round(tp.y_degree, 10), 
        longitude = round(tp.x_degree, 10), 
        elevation = round(tp.z_ax, 1), 
        time = dt_from_timestamp(tp.unix_time, dt.timezone.utc), 
        name = str(tp.track_count + 1))
    gpx_append = (gpx_route.points.append if tp.file_type == 0x3 
                  else gpx_segment.points.append)
    gpx_append(gpx_point)

    # This part may be informative.  Comment it out, if not necessary. 
    gpx_point.description = (
        f'Speed {round(tp.v, 3)} km/h Distance {round(tp.dist, 3)} km')

    # In gpx 1.1, use trackpoint extensions to store speeds in m/s.
    # Not quite sure if the <gpxtpx:TrackPointExtension> tag is valid in rtept.  Should it be gpxx?
    speed = round(tp.v / 3.6, 3) # velocity in m/s
    gpx_extension_speed = mod_etree.fromstring(
        '<gpxtpx:TrackPointExtension xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2">'
        f'<gpxtpx:speed>{speed}</gpxtpx:speed>'
        '</gpxtpx:TrackPointExtension>')
    gpx_point.extensions.append(gpx_extension_speed)

def finalize_gpx(gpx, write_file=None):
    write_file = False if write_file is None else write_file

    # Add a summary.  This part may be informative.
    to_time = t_time if total_time == 0 else total_time
    to_dist = dist if total_distance == 0 else total_distance
    n_speed = to_dist / (to_time / 3600) # Calculate net speed in km/h.
    descr = ('[' f'Total time: {format_timedelta(to_time)}' '; ' 
             f'Total distance: {round(to_dist, 3)} km' '; '
             f'Net speed: {round(n_speed, 3)} km/h')
    if file_type == 0x3:
        gpx.routes[0].description = (f'{descr}' ']')
    else:
        stop_t = (stop_localtime if stop_localtime != symbian_to_unix_time(0) 
                  else unix_time + TZ_hours * 3600)
        real_t = stop_t - start_localtime
        g_speed = to_dist / (real_t / 3600) # Calculate gross speed in km/h.
        gpx.tracks[0].description = (
            f'{descr}' '; ' 
            f'Start localtime: {format_datetime(start_localtime)}' '; '
            f'Stop localtime: {format_datetime(stop_t)}' '; '
            f'Real time: {format_timedelta(real_t)}' '; '
            f'Gross speed: {round(g_speed, 3)} km/h' ']')

    # Finally, print or write the gpx. 
    if not write_file:
        print(gpx.to_xml('1.1'))
    else:
        gpx_file = Path(argvs[1][:-3] + 'gpx')
        result = gpx.to_xml('1.1')
        result_file = open(gpx_file, 'w')
        result_file.write(result)
        result_file.close()


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads temporal track log files (Rec*.tmp) of symbian 
        SportsTracker.  Log files with heart-rate sensor were not tested.""")
    quit()
#print(argc)
#print(argvs[1])

#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)


# Creating a new GPX:
gpx = gpxpy.gpx.GPX()

# Create the first track in the GPX:
gpx_track = gpxpy.gpx.GPXTrack()
gpx.tracks.append(gpx_track)

# Create the first segment in the GPX track:
gpx_segment = gpxpy.gpx.GPXTrackSegment()
gpx_track.segments.append(gpx_segment)

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


with in_file.open(mode='rb') as f:
    
    # Check if this is a temporal track log file.
    # 0x0E4935E8 ; Application ID.
    # File type: 0x1 = config, 0x2 = Track, 0x3 = Route, 0x4 = tmp.
    #
    # Chunks of data in the temporal file always start with b'\x00\x00\x00\x00' blank.
    # Because of this blank, there is a 4-byte offset to the addresses shown below.
    #f.seek(0x00000, 0)
    # Read 12 (4+4+4) bytes, little endian U32+U32+U32, returns tuple.
    (app_id, file_type, blank) = read_unpack('<3I', f)
    if not (app_id == 0x0e4935e8 and file_type == 0x4 and blank == 0x0):
        print(f'Unexpected file type: {file_type}')
        quit()
        
    # Preliminary version check.
    #f.seek(0x00008 + 0x4, 0) # Go to 0x00008 + 0x4, this address is fixed.
    (version, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    print(f'Version: {version}')
    # Track log files of the old Nokia SportsTracker:          version < 10000.
    # Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
    # Track log files of Symbian SportsTracker:       20000 <= version.
    if version < 20000:
        print(f'Version number less than expected: {version}')
        quit()
        
    # Start address of the main part (pause and trackpoint data).
    # We don't read the address from the file because it is useless.
    start_address = 0x250 # Not quite sure if this is the best starting point to read.
    
    # Track ID and Totaltime.
    f.seek(0x00014 + 0x4, 0) # Go to 0x00014 + 0x4, this address is fixed.
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (track_id, total_time) = read_unpack('<2I', f)
    print(f'Track ID: {track_id}')
    
    total_time /= 100 # Totaltime in seconds.
    print(f'Total time: {format_timedelta(total_time)}')
    
    # Total Distance.
    f.seek(0x00004, 1) # Skip 4 bytes.  Because of this, there is a 4-byte offset to oldNST.
    (total_distance, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    total_distance /= 1e5 # Total distance in km.
    print(f'Total distance: {round(total_distance, 3)} km')
    
    # Starttime and Stoptime in localtime.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    stop_localtime = symbian_to_unix_time(stop_localtime)
    
    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    print(f'Start: {format_datetime(start_localtime)}+07:00')
    #print(f'Stop : {format_datetime(stop_localtime)}+07:00')
    
    # User ID, please see config.dat.
    (user_id, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    print(f'User id: {user_id}')
    gpx.author_name = str(user_id)
    
    # Type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = read_unpack('<H', f) # Read 2 bytes, little endian U16, returns tuple.
    activities = [
        'Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 
        'Other 3', 'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 
        'Hiking', 'Roller skating', 'Downhill skiing', 'Paddling', 'Rowing', 
        'Golf', 'Indoor']
    description = (activities[activity] if activity < len(activities) 
                   else str(activity))
    print(f'Activity: {description}')
    gpx.description = f'[{description}]'
    
    # Read SCSU encoded name of the track, which is usually the datetime.
    # 
    # In most cases, the name consists of ASCII characters, strings of 16 bytes, such as 
    # '24/12/2019 12:34'.  The strings are, in principle, not fully compatible with utf-8 but 
    # can be non-ASCII characters encoded with SCSU (simple compression scheme for unicode).
    #
    track_name = scsu_reader(f, 0x0004a + 0x4) # This address is fixed.
    print(f'Track name: {track_name}')
    gpx.name = f'[{track_name}]'
    gpx.tracks[0].name = gpx.name
    
    # Starttime & Stoptime in UTC.
    f.seek(0x00192 + 0x4, 0) # Go to 0x00192 + 0x4, this address is fixed.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_time, stop_time) = read_unpack('<2q', f)
    start_time = symbian_to_unix_time(start_time)
    stop_time = symbian_to_unix_time(stop_time)
    #print(f'Start Z: {format_datetime(start_time)}Z')
    #print(f'Stop Z : {format_datetime(stop_time)}Z')
    
    # We can calculate the timezone by using the starttimes in Z and in localtime.
    TZ_hours = int(start_localtime - start_time) / 3600
    gpx.time = dt_from_timestamp(
        start_time, dt.timezone(dt.timedelta(hours = TZ_hours), ))
    
    # Read SCSU encoded user comment of variable length.
    comment = scsu_reader(f, 0x00222 + 0x4) # This address is fixed.
    if comment:
        print(f'Comment: {comment}')
        gpx.tracks[0].comment = comment
    
    
    # Number of track points.
    num_trackpt = None # The number in the file is useless.
    
    
    # Go to the first data.
    f.seek(start_address, 0)
    track_count = 0
    
    # Factory functions for creating named tuples.
    type00 = 't_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time'
    type80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist, unknown1, unknown2'
    typeC0 = ('dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist, '
              'unknown1, unknown2')
    type_store = ('unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, '
                  'dist, track_count, file_type')
    Trackpt_type00 = namedtuple('Trackpt_type00', type00)
    Trackpt_type80 = namedtuple('Trackpt_type80', type80)
    Trackpt_typeC0 = namedtuple('Trackpt_typeC0', typeC0)
    Trackpt_store = namedtuple('Trackpt_store', type_store)
    Trackpt_store.__new__.__defaults__ = (None,) * len(Trackpt_store._fields)

    trackpt_store = Trackpt_store() # A temporal storage to pass the trackpt.
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
            header_fmt = '2B' # Read the 2-byte header.
            size = struct.calcsize(header_fmt)
            headers = f.read(size)
            if len(headers) < size: # Check end of file.
                break
            (header, header1) = struct.unpack(header_fmt, headers)
            
            if header == 0x07 and header1 in {0x83, 0x82}: # Typically, 0783 or 0782.
                (Trackpt, fmt) = (Trackpt_type00, '<I3iHIq')
                # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
                # Read 30 bytes of data(4+4+4+4+2+4+8).  Negative y and x mean South and West, respectively.
                size = struct.calcsize(fmt)
                track_data = f.read(size)
                if len(track_data) < size: # Check end of file.
                    break
                trackpt = Trackpt._make(struct.unpack(fmt, track_data)) # Wrap it with named tuple.
                t_time = trackpt.t_time / 100 # Totaltime in seconds.
                
                # The latitudes and longitudes are stored in I32s as popular DDDmm mmmm format.
                (y_degree, y_mm_mmmm) = divmod(trackpt.y_ax, 1e6)
                (x_degree, x_mm_mmmm) = divmod(trackpt.x_ax, 1e6)
                y_degree += y_mm_mmmm / 1e4 / 60 # Convert minutes to degrees.
                x_degree += x_mm_mmmm / 1e4 / 60
                
                z_ax = trackpt.z_ax / 10 # Altitude in meter.
                v = trackpt.v / 100 * 3.6 # Multiply (m/s) by 3.6 to get velocity in km/h.
                dist = trackpt_store.dist + trackpt.d_dist / 100 / 1e3 # Divide (m) by 1e3 to get distance in km.
                unix_time = symbian_to_unix_time(trackpt.symbian_time)
                
                utc_time = f'{format_datetime(unix_time)}Z'
                print(hex(f.tell()), hex(header), t_time, utc_time, *trackpt[1:-1])
                
                # Remove spikes, because there is a lot of error in the temporal file.  This is an adhoc method, though.
                # TODO: It is better to read and use both the trackpt and pause data to correct bad timestamps in the temporal file.
                delta_unix_time = unix_time - trackpt_store.unix_time # In most cases, the two delta_s (~1 s) are equal each other.
                delta_t_time = t_time - trackpt_store.t_time
                good_unix_time = 0 < delta_unix_time < 1 * 3600 # Up to 1 hr.
                good_t_time = 0 <= delta_t_time < 5 * 60 # Up to 5 min.
                
                if track_count == 0 or suspect_pause == True:
                    suspect_pause = False # Do nothing in time correction, but reset the flag.
                
                # There are four cases due to the two boolean conditions.
                elif good_unix_time and good_t_time:
                    # Out of this range is most likely caused by a very long pause (e.g. lunch), but might be by an error. 
                    if not -0.5 < delta_unix_time - delta_t_time <= 130: # Set the max of usual pause (suppose traffic signal).
                        (unix_time, t_time) = (
                            t + min(delta_unix_time, delta_t_time) for t in 
                            (trackpt_store.unix_time, trackpt_store.t_time))
                        suspect_pause = True # Set the flag to see if this is because of a pause.
                        print(f'Bad.  Two distinct increments at: {hex(pointer)}')
                elif (not good_unix_time) and good_t_time:
                    unix_time = trackpt_store.unix_time + delta_t_time # Correct unixtime by using totaltime.
                    print(f'Bad unixtime at: {hex(pointer)}')
                elif (not good_unix_time) and (not good_t_time):
                    (unix_time, t_time) = (
                        t + 0.2 for t in  # Add 0.2 s (should be < 1.0 s) to both, as a compromise.
                        (trackpt_store.unix_time, trackpt_store.t_time))
                    print(f'Bad unixtime and totaltime at: {hex(pointer)}')
                else: # good_unix_time and (not good_t_time)
                    t_time = trackpt_store.t_time + delta_unix_time # Correct totaltime by using unixtime.
                    print(f'Bad totaltime at: {hex(pointer)}')
                
                if track_count > 0: # Spikes in y, x, z and total_distance.  Replace it with its previous value.
                    if abs(trackpt_store.y_degree - y_degree) >= 0.001: # Threshold of 0.001 deg.
                        y_degree = trackpt_store.y_degree
                        print(f'Bad y at: {hex(pointer)}')
                    if abs(trackpt_store.x_degree - x_degree) >= 0.001:
                        x_degree = trackpt_store.x_degree
                        print(f'Bad x at: {hex(pointer)}')
                    if abs(trackpt_store.z_ax - z_ax) >= 500: # Threshold of 500 m.
                        z_ax = trackpt_store.z_ax
                if not 0 <= dist - trackpt_store.dist < 1: # Up to 1 km.
                    dist = trackpt_store.dist
                
            # Other headers which I don't know.
            else:
                if not (header == 0x00 and header1 == 0x00):
                    print(f'{hex(header)} Error in the track point header: '
                          f'{track_count}, {num_trackpt}')
                    print(f'At address: {hex(pointer)}')
                    print(*trackpt)
                    print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)
                continue
                #break
                
            trackpt_store = Trackpt_store(
                unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
                x_degree=x_degree, z_ax=z_ax, v=v, d_dist=trackpt.d_dist / 1e5, 
                dist=dist, track_count=track_count, file_type=file_type)
            store_trackpt(trackpt_store)
            
            track_count += 1
            
            
        else:
            f.seek(-3, 1) # Seek forward (4 - 3 = +1 byte).

finalize_gpx(gpx, write_file=True) # True=write file, False=print.
