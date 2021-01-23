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

try: # Load LXML or fallback to cET or ET 
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
    elif (not workaround) and 0 <= timestamp < 32536799999: # From 1970-01-01T00:00:00 to 3001-01-19T07:59:59.  The range depends on your platform.
        d_t = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc)
    else:
        return None
    return (d_t.replace(tzinfo=None) if tz_info is None 
            else d_t.astimezone(tz_info))

def format_datetime(timestamp):
    d_t = dt_from_timestamp(round(timestamp, 3))
    return (d_t.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] if d_t is not None # ISO-8601 format.
            else f'INVALID({timestamp})')

def format_timedelta(t_delta):
    return str(dt.timedelta(seconds = round(t_delta, 3)))[:-3]

def read_unpack(fmt, file_object): # Helper function to read and unpack.
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
    if address is not None: file_object.seek(address, 0)
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
    # in unit:  sec.,   sec.,    deg.,     deg.,   m, km/h,  km,   km,   int. number, (track=2, route=3, tmp=4)
    
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
    gpx_target.points.append(gpx_point) # gpx_target is either gpx_route or gpx_segment shown in initialize_gpx().

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

def initialize_gpx():
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

def finalize_gpx(gpx, write_file=None):
    # Add a summary.  This part may be informative.
    to_time = t_time if total_time == 0 else total_time
    to_dist = dist if total_distance == 0 else total_distance
    n_speed = to_dist / (to_time / 3600) # Calculate net speed in km/h.
    descr = ('[' f'Total time: {format_timedelta(to_time)}' '; ' 
             f'Total distance: {round(to_dist, 3)} km' '; '
             f'Net speed: {round(n_speed, 3)} km/h')
    gpx.name = f'[{route_name}]' if file_type == 0x3 else f'[{track_name}]'
    if file_type == 0x3: # Route files.
        gpx.routes[0].name = gpx.name
        gpx.routes[0].description = (f'{descr}' ']')
    else: # Track files.
        gpx.tracks[0].name = gpx.name
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
        gpx.description = f'[{description}]' # This field shows the type of activity (walking, running, cycling, etc.).
        gpx.author_name = str(user_id)
        gpx.time = dt_from_timestamp(
            start_time, dt.timezone(dt.timedelta(hours = TZ_hours), ))
        if 'comment' in globals():
            if comment: gpx.tracks[0].comment = comment
    # Finally, print or write the gpx. 
    write_file = False if write_file is None else write_file
    if write_file:
        gpx_file = Path(argvs[1][:-3] + 'gpx')
        result = gpx.to_xml('1.1')
        result_file = open(gpx_file, 'w')
        result_file.write(result)
        result_file.close()
    else: print(gpx.to_xml('1.1'))


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads track log files (W*.dat) of symbian SportsTracker.
        Log files with heart-rate sensor were not tested.""")
    quit()
#print(argvs[1])
#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)


with in_file.open(mode='rb') as f:
    
    # Check if this is a track log file.
    #f.seek(0x00000, 0)
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (application_id, file_type) = read_unpack('<2I', f)
    if application_id != 0x0e4935e8 or file_type != 0x2: # File type: 0x1 = config, 0x2 = Track, 0x3 = Route, 0x4 = tmp.
        print(f'Unexpected file type: {file_type}')
        quit()
        
    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print(f'Version: {version}')
    oldNST = (version < 10000) # Track log files of the old Nokia SportsTracker.
    oldNST_route = (10000 <= version < 20000) # Route files of the old Nokia SportsTracker.
    NST = (20000 <= version) # Track log files of Symbian SportsTracker.
    if not NST:
        print(f'Version number less than expected: {version}')
        quit()
        
    # Initialize gpx.
    gpx, gpx_target = initialize_gpx()
    
    # Start address of the main part (pause and trackpoint data).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    (start_address, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    start_address -= 1
    #print(f'Main part address: {hex(start_address)}')
    
    # Track ID and Totaltime.
    f.seek(0x00014, 0) # Go to 0x00014, this address is fixed.
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (track_id, total_time) = read_unpack('<2I', f)
    #print(f'Track ID: {track_id}')
    
    total_time /= 100 # Totaltime in seconds.
    #print(f'Total time: {format_timedelta(total_time)}')
    
    # Total Distance.
    f.seek(0x00004, 1) # Skip 4 bytes.  Because of this, there is a 4-byte offset to oldNST.
    (total_distance, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    total_distance /= 1e5 # Total distance in km.
    #print(f'Total distance: {round(total_distance, 3)} km')
    
    # Calculate Net speed in km/h.
    net_speed = total_distance / (total_time / 3600) # km/h
    #print(f'Net speed: {round(net_speed, 3)} km/h')
    
    # Starttime and Stoptime in localtime.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    stop_localtime = symbian_to_unix_time(stop_localtime)
    
    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    #print(f'Start: {format_datetime(start_localtime)}+09:00')
    #print(f'Stop : {format_datetime(stop_localtime)}+09:00')
    
    # Calculate Realtime, which is different from Totaltime if pause is used.
    real_time = stop_localtime - start_localtime # Realtime in seconds.
    #print(f'Realtime: {format_timedelta(real_time)}')
    
    # Calculate Gross speed in km/h.
    gross_speed = total_distance / (real_time / 3600) # km/h
    #print(f'Gross speed: {round(gross_speed, 3)} km/h')
    
    # User ID, please see config.dat.
    (user_id, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print(f'User id: {user_id}')
    
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
    #print(f'Activity: {description}')
    
    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases, the name consists of ASCII characters, strings of 16 bytes, such as 
    # '24/12/2019 12:34'.  The strings are, in principle, not fully compatible with utf-8 but 
    # can be non-ASCII characters encoded with SCSU (simple compression scheme for unicode).
    track_name = scsu_reader(f, 0x0004a) # This address is fixed.
    #print(f'Track name: {track_name}')
    
    # Starttime & Stoptime in UTC.
    f.seek(0x00192, 0) # Go to 0x00192, this address is fixed.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_time, stop_time) = read_unpack('<2q', f)
    start_time = symbian_to_unix_time(start_time)
    stop_time = symbian_to_unix_time(stop_time)
    #print(f'Start Z: {format_datetime(start_time)}Z')
    #print(f'Stop Z : {format_datetime(stop_time)}Z')
    
    # We can calculate the timezone by using the starttimes in Z and in localtime.
    TZ_hours = int(start_localtime - start_time) / 3600
    
    # This will overwrite the realtime shown above.
    real_time = stop_time - start_time # Realtime in seconds.
    #print(f'Realtime Z: {format_timedelta(real_time)}')
    
    # Read SCSU encoded user comment of variable length.
    comment = scsu_reader(f, 0x00222) # This address is fixed.
    #if comment: print(f'Comment: {comment}')
    
    
    # Number of pause data.
    #start_address = 0x007ff # Usually 0x007ff.
    f.seek(start_address, 0) # Go to the start address of the main part.
    (num_pause, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print(f'Number of pause data: {num_pause}')
    pause_address = f.tell() # start_address + 4
    
    # Number of track points.
    f.seek(num_pause * 14, 1) # Pause data are 14 bytes each.  Skip pause data part.
    (num_trackpt, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print(f'Number of track pts: {num_trackpt}')
    track_address = f.tell()
    
    
    # Go to the first pause data.
    f.seek(pause_address, 0)
    
    pause_count = 0
    pause_list = []
    
    while pause_count < num_pause:
    
        # Read 14 bytes of data(1+4+1+8).  Symbiantimes of the old version are 
        # in localtime zone, while those of the new version in UTC (Z).
        # The first unknown field (always 0x01) seems to have no meaning.
        (unknown, t_time, flag, symbian_time) = read_unpack('<BIBq', f)
        
        t_time /= 100 # Totaltime in seconds.
        unix_time = symbian_to_unix_time(symbian_time)
        #utc_time = f'{format_datetime(unix_time)}Z'
        #print(f'{unknown}\t{format_timedelta(t_time)}\t{flag}\t{utc_time}')
        
        # Start flag = 1, we don't use these data.  Just store them for the future purposes.
        if flag == 1:
            starttime = unix_time
            start_t_time = t_time
            
        # Stop flag = 2, we don't use these data.  Just store them for the future purposes.
        elif flag == 2:
            stoptime = unix_time
            stop_t_time = t_time
            
        # Suspend flag = 3 (manually) or 4 (automatically).
        elif (flag == 3)|(flag == 4):
            suspend_time = unix_time
            t4_time = t_time
            
        # Resume flag = 5.
        elif flag == 5:
            # A pair of flag-4 (also flag-3) and flag-5 data should have a common totaltime.
            if t4_time != t_time:
                print('Error in pause.')
                quit()
                
            pause_time = unix_time - suspend_time # Time between suspend and resume.
            pause_list.append((t_time, pause_time, unix_time))
            
        # Flag = 8.  Not quite sure how to use the flag-8 data.  Use it as a correction of time. 
        elif flag == 8:
            pause_time = 0
            pause_list.append((t_time, pause_time, unix_time))
            
        pause_count += 1
        
    #print('Total time', '\t', 'Pause time', '\t', 'Datetime', sep ='')
    #for pause in pause_list:
    #    t_time, pause_time, unix_time = pause
    #    print(format_timedelta(t_time), '\t', 
    #          format_timedelta(pause_time), '\t', 
    #          f'{format_datetime(unix_time)}Z', sep = '')
    #print()
    #quit()
    
    
    # Go to the first trackpoint.
    f.seek(track_address, 0)
    track_count = 0
    
    # Factory functions for creating named tuples.
    type00 = 't_time, y_ax, x_ax, z_ax, v, d_dist'
    type80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist'
    typeC0 = 'dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist'
    if NST:
        type00 = type00 + ', symbian_time'
        type80, typeC0 = (t + ', unknown1, unknown2' for t in (type80, typeC0))
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
    
    # The main loop to read the trackpoints.
    while track_count < num_trackpt:
    
        pointer = f.tell()
        header_fmt = '2B' # Read the first byte of 2-byte header.
        (header, header1) = read_unpack(header_fmt, f)
        
        if header == 0x07: # Typically, 0783 or 0782.
        
            (Trackpt, fmt) = (Trackpt_type00, '<I3iHIq')
            # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
            # Read 30 bytes of data(4+4+4+4+2+4+8).  Negative y and x mean South and West, respectively.
            trackpt = Trackpt._make(read_unpack(fmt, f)) # Wrap it with named tuple.
            
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
            
            #times = f'{t_time} {format_datetime(unix_time)}Z'
            #print(hex(f.tell()), hex(header), times, *trackpt[1:-1])
            
        elif header in {0x87, 0x97, 0xC7, 0xD7}:
        
            if header in {0x87, 0x97}: # Typically 8783, 8782, 9783, 9782.
                
                Trackpt = Trackpt_type80
                # (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist, unknown1, unknown2)
                # Unknown1 & 2 might be related to heart rate sensor.
                fmt = '<B3hbH2B' if header == 0x87 else '<B4hH2B' # 0x97
                # 0x87: Read 12 bytes of data(1+2+2+2+1+2+1+1).  1-byte dv.
                # 0x97: Read 13 bytes of data(1+2+2+2+2+2+1+1).  2-byte dv.
                
            elif header in {0xC7, 0xD7}: # Typically C783, C782, D783, D782.  This case is quite rare.
            
                Trackpt = Trackpt_typeC0
                # (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist, unknown1, unknown2)
                # Unknown3 & 4 show up in distant jumps.  They might have a meaning but we can live without it.
                fmt = '<B5hbH2B' if header == 0xC7 else '<B6hH2B' # 0xD7
                # 0xC7: Read 16 bytes of data(1+2+2+2+2+2+1+2+1+1).  1-byte dv.
                # 0xD7: Read 17 bytes of data(1+2+2+2+2+2+2+2+1+1).  2-byte dv.
                
            trackpt = Trackpt._make(read_unpack(fmt, f)) # Wrap it with named tuple.
            
            t_time = trackpt_store.t_time + trackpt.dt_time / 100 # Totaltime in seconds.
            
            y_degree = trackpt_store.y_degree + trackpt.dy_ax / 1e4 / 60 # Latitudes and longitudes are given as differences.
            x_degree = trackpt_store.x_degree + trackpt.dx_ax / 1e4 / 60
            
            z_ax = trackpt_store.z_ax + trackpt.dz_ax / 10 # Altitudes in meters are also given as differences.
            v = trackpt_store.v + trackpt.dv / 100 * 3.6 # Velocity, as well.  Multiply (m/s) by 3.6 to get velocity in km/h.
            dist = trackpt_store.dist + trackpt.d_dist / 100 / 1e3 # Divide (m) by 1e3 to get total distance in km.
            unix_time = trackpt_store.unix_time + trackpt.dt_time / 100
            
            #times = f'{t_time} {format_datetime(unix_time)}Z'
            #print(hex(f.tell()), hex(header), times, *trackpt[1:])
            
        else: # Other headers which I don't know.
        
            print(f'{hex(header)} Error in the track point header: '
                  f'{track_count}, {num_trackpt}')
            print(f'At address: {hex(pointer)}')
            print(*trackpt)
            print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)
            break
            
        if pause_list:
        
            t4_time, pause_time, resume_time = pause_list[0]
            #print(format_timedelta(t4_time), format_timedelta(pause_time))
            
            # Just after the pause, use the pause data.  Still not quite sure if this works.
            if (t_time + 0.5 >= t4_time):
            
                if header != 0x07:  # Track points not starting with 0x07 need UTC times.
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time
                    
                del pause_list[0]
                
        trackpt_store = Trackpt_store(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=trackpt.d_dist / 1e5, 
            dist=dist, track_count=track_count, file_type=file_type)
        store_trackpt(trackpt_store)
        
        track_count += 1
        
        
# Handling of errors.
if track_count != num_trackpt:
    print(f'Track point count error: {track_count}, {num_trackpt}')
    quit()

finalize_gpx(gpx, write_file=False) # True=write file, False=print.
