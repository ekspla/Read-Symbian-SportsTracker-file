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
import datetime
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


#  The native Symbian time format is a 64-bit value that represents microseconds 
#  since January 1st 0 AD 00:00:00 local time, nominal Gregorian.
#  BC dates are represented by negative values.
#
def symbian_to_unix_time(symbian_time):
    unix_time = symbian_time / 1e6 - 62168256000
    return unix_time

def format_datetime(timestamp):
    fmt = "%Y-%m-%dT%H:%M:%S.%f" # ISO-8601 format.
    return datetime.datetime.fromtimestamp(round(timestamp, 3), 
                                           datetime.timezone.utc).strftime(fmt)[:-3]

def format_timedelta(t_delta):
    return str(datetime.timedelta(seconds = round(t_delta, 3)))[:-3]

# Helper function to read and unpack.
def read_unpack(fmt, file_object):
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, file_object.read(size))

def scsu_reader(file_object, address = None):
    """Reads SCSU encoded bytes of variable length from file_object and returns utf-8 using external decoder.
    
    Args: 
        file_object: file object to be read.
        address: start address of the SCSU encoded part.  The data is preceded by one byte integer (U8) 
                 which indicates the length of the characters multiplied by four.
                 
    Returns:
        decoded_strings: a bytearray of decoded UTF-8.
    """
    if address:
        file_object.seek(address, 0)
    (size, ) = read_unpack('B', file_object) # Read the size * 4 in bytes.
    start_of_scsu = file_object.tell()
    byte_array = file_object.read(size) # Returns bytes.
    size = int(size / 4) # Divide by 4 to obtain the length of characters.
    (output_array, byte_length, character_length) = scsu.decode(byte_array, size)
    decoded_strings = output_array.decode("utf-8", "ignore") # Sanitize and check the length.
    if len(decoded_strings) != size:
        print('SCSU decode failed.', output_array)
        quit()
    file_object.seek(start_of_scsu + byte_length, 0) # Go to the next field.
    return decoded_strings


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print("""Usage: # python %s input_filename' % argvs[0]\n
 This script reads temporal track log files (Rec*.tmp) of symbian SportsTracker.
Log files with heart-rate sensor were not tested.""")
    quit()
#print(argc)
#print(argvs[1])
#print(argvs[2])
#print(argvs[3])

#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)
gpx_file = Path(argvs[1][:-3] + 'gpx')


# Creating a new GPX:
gpx = gpxpy.gpx.GPX()

# Create the first track in the GPX:
gpx_track = gpxpy.gpx.GPXTrack()
gpx.tracks.append(gpx_track)

# Create the first segment in the GPX track:
gpx_segment = gpxpy.gpx.GPXTrackSegment()
gpx_track.segments.append(gpx_segment)

# Definition of extension.
# Add TrackPointExtension namespace and schema location.
gpx.nsmap["gpxtpx"] = "http://www.garmin.com/xmlschemas/TrackPointExtension/v2"
gpx.nsmap["gpxx"] = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"

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
    # 0x00000004 ; File type (cf. 0x1 = config, 0x2 = Track, 0x3 = Route, 0x4 = tmp)
    #
    # Chunks of data in the temporal file always start with b'\x00\x00\x00\x00' blank.
    # Because of this blank, there is a 4-byte offset to the addresses shown below.
    #f.seek(0x00000, 0)
    # Read 12 (4+4+4) bytes, little endian U32+U32+U32, returns tuple.
    (app_id, file_type, blank) = read_unpack('<3I', f)
    if not (app_id == 0x0e4935e8 and file_type == 0x4 and blank == 0x0):
        print('Unexpected file type:', file_type)
        quit()
        
        
    # Preliminary version check.
    #f.seek(0x00008 + 0x4, 0) # Go to 0x00008 + 0x4, this address is fixed.
    (version, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    print('Version: ', version)
    # 
    # Track log files of the old Nokia SportsTracker:          version < 10000.
    # Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
    # Track log files of Symbian SportsTracker:       20000 <= version.
    if version < 20000:
        print('Version number less than expected:', version)
        quit()
        
        
    # Track ID and Totaltime.
    f.seek(0x00014 + 0x4, 0) # Go to 0x00014 + 0x4, this address is fixed.
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (track_id, total_time) = read_unpack('<2I', f)
    print('Track ID: ', track_id)
    
    total_time /= 100 # Totaltime in seconds.
    print('Total time: ', format_timedelta(total_time))
    
    
    # Total Distance.
    f.seek(0x00004, 1) # Skip 4 bytes.  Because of this, there is a 4-byte offset to oldNST. 
    (total_distance, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    total_distance /= 1e5 # Total distance in km.
    print('Total distance: ', round(total_distance, 3), ' km')
    
    
    # Starttime and Stoptime in localtime.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    # Print start time in localtime.  Change the suffix according to your timezone, 
    # because there is no timezone information in Symbian.
    # Take difference of starttime in localtime and those in UTC (see below) to see the timezone+DST.
    print('Start: ', format_datetime(start_localtime) + "+07:00")
    
    stop_localtime = symbian_to_unix_time(stop_localtime)
    #print('Stop : ', format_datetime(stop_localtime) + "+07:00")
    
    
    # User ID, please see config.dat.
    (user_id, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    print('User id: ', user_id)
    gpx.author_name = str(user_id)
    
    
    # Type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = read_unpack('<H', f) # Read 2 bytes, little endian U16, returns tuple.
    activities = ['Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 'Other 3', 
                  'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 'Hiking', 'Roller skating', 
                  'Downhill skiing', 'Paddling', 'Rowing', 'Golf', 'Indoor']
    description = activities[activity] if activity < len(activities) else str(activity)
    print('Activity: ', description)
    gpx.description = "[" + description + "]"
    
    
    # Read SCSU encoded name of the track, which is usually the datetime.
    # 
    # In most cases, the name consists of ASCII characters, strings of 16 bytes, such as 
    # '24/12/2019 12:34'.  The strings are, in principle, not fully compatible with utf-8 but 
    # can be non-ASCII characters encoded with SCSU (simple compression scheme for unicode).
    #
    track_name = scsu_reader(f, 0x0004a + 0x4) # This address is fixed.
    print('Track name: ', track_name)
    gpx.name = "[" + track_name + "]"
    gpx.tracks[0].name = gpx.name
    
    
    # Starttime & Stoptime in UTC.
    f.seek(0x00192 + 0x4, 0) # Go to 0x00192 + 0x4, this address is fixed.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_time, stop_time) = read_unpack('<2q', f)
    start_time = symbian_to_unix_time(start_time)
    #print('Start Z: ', format_datetime(start_time) + "Z")
    
    # We can calculate the timezone by using the starttimes in Z and in localtime.
    TZ_hours = int(start_localtime - start_time) / 3600
    gpx.time = datetime.datetime.fromtimestamp(
        start_time, datetime.timezone(datetime.timedelta(hours = TZ_hours), ))
    
    stop_time = symbian_to_unix_time(stop_time)
    #print('Stop Z : ', format_datetime(stop_time) + "Z")
    
    
    # Read SCSU encoded user comment of variable length.
    comment = scsu_reader(f, 0x00222 + 0x4) # This address is fixed.
    if comment:
        print('Comment:', comment)
        gpx.tracks[0].comment = comment
    


    t_time = 0 # Totaltime in seconds.
    unix_time = start_time # unixtime.
    utc_time = ''
    dist = 0 #  Total distance in km.
    v = 0 # Velocity in km/h.
    track_count = 0
    
    # For removing noise.
    last_t_time = 0
    last_unix_time = start_time
    last_dist = 0
    
    start_address = 0x250 # Not quite sure if this is a good starting point to read.
    f.seek(start_address, 0)
    
    while True: # We don't know how many trackpoints exist in the temporal file.
    
        # Trackpoints and pause data, respectively, are labeled by b'\x02\x00\x00\x00' 
        # and b'\x01\x00\x00\x00'. The trackpoint data is always starting with 0x07 header, 
        # which means data with symbian_time. Read the trackpoint data exclusively 
        # because we don't have to use pause data to see the symbian_time.
        preceding_label = f.read(4)
        if len(preceding_label) < 4: # Check end of file.
            break
        elif preceding_label == b'\x02\x00\x00\x00':
            headers = f.read(2) # Read the 2-byte header.
            if len(headers) < 2: # Check end of file.
                break
            (header, header1) = struct.unpack('2B', headers)
            #print(header, header1)
            if header == 0x07 and header1 in {0x83, 0x82}: # Typically, 0783 or 0782.
                # Read 30 bytes of data(4+4+4+4+2+4+8).  Negative y and x mean South and West, respectively.
                track_data = f.read(30)
                if len(track_data) < 30: # Check end of file.
                    break
                (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time) \
                    = struct.unpack('<I3iHIq', track_data)
                
                t_time /= 100 # Totaltime in seconds.
                
                # The latitudes and longitudes are stored in I32s as popular DDDmm mmmm format.
                y_degree = y_ax // 1e6
                x_degree = x_ax // 1e6
                y_mm_mmmm = y_ax % 1e6
                x_mm_mmmm = x_ax % 1e6
                y_degree += y_mm_mmmm / 1e4 / 60 # Convert minutes to degrees.
                x_degree += x_mm_mmmm / 1e4 / 60
                
                z_ax /= 10 # Altitude in meter.
                
                v = v / 100 * 3.6 # Multiply (m/s) by 3.6 to get velocity in km/h.
                
                dist += d_dist / 100 / 1e3 # Divide (m) by 1e3 to get distance in km.
                
                unix_time = symbian_to_unix_time(symbian_time)
                #print(unix_time)
                
                # For removing noise.
                if not (last_unix_time <= unix_time < last_unix_time + 1 * 3600): # Up to 1 hr.  Don't take a big lunch.
                    unix_time = last_unix_time + (t_time - last_t_time)
                    print('Strange timestamp.  At:', hex(f.tell() - 36))
                if not (last_t_time <= t_time < last_t_time + 5 * 60): # Up to 5 min.
                    t_time = last_t_time + (unix_time - last_unix_time)
                    print('Strange totaltime.  At:', hex(f.tell() - 36))
                if track_count != 0:
                    if abs(gpx_point.latitude - y_degree) >= 0.001: # Threshold of 0.001 deg.
                        y_degree = gpx_point.latitude
                        print('Strange y.  At:', hex(f.tell() - 36))
                    if abs(gpx_point.longitude - x_degree) >= 0.001:
                        x_degree = gpx_point.longitude
                        print('Strange x.  At:', hex(f.tell() - 36))
                    if abs(gpx_point.elevation - z_ax) >= 500: # Threshold of 500 m.
                        z_ax = gpx_point.elevation
                if not (last_dist <= dist < last_dist + 1): # Up to 1 km.
                    dist = last_dist
                    
                utc_time = format_datetime(unix_time) + "Z"
                print(t_time, y_ax, x_ax, z_ax, v, dist, utc_time)
                
                
            # Other headers which I don't know.
            else:
                if not (header == 0x00 and header1 == 0x00):
                    print('At address:', hex(f.tell() - 6))
                continue
                #break
                
            # Print delimited text.
            #utc_time = format_datetime(unix_time) + "Z"
            #to_time = format_timedelta(t_time)
            #print(to_time, '\t', utc_time, '\t', round(d_dist / 100 / 1e3, 3), '\t', 
            #      round(dist, 3), '\t', round(y_degree, 10), '\t', round(x_degree, 10) , '\t', 
            #      round(z_ax, 1), '\t', round(v, 2), sep='')
            
            # Print gpx xml.
            gpx_point = gpxpy.gpx.GPXTrackPoint(
                latitude = round(y_degree, 10), 
                longitude = round(x_degree, 10), 
                elevation = round(z_ax, 1), 
                time = datetime.datetime.fromtimestamp(unix_time, datetime.timezone.utc), 
                name = str(track_count + 1))
            gpx_segment.points.append(gpx_point)
            
            # This part may be informative.  Comment it out, if not necessary. 
            gpx_point.description \
               = 'Speed ' + str(round(v, 3)) + ' km/h ' + 'Distance ' + str(round(dist, 3)) + ' km'
            
            # In gpx 1.1, use trackpoint extensions to store speeds in m/s.
            speed = round(v / 3.6, 3) # velocity in m/s
            gpx_extension_speed = mod_etree.fromstring(
                f"""<gpxtpx:TrackPointExtension \
                xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2">\
                <gpxtpx:speed>{speed}</gpxtpx:speed>\
                </gpxtpx:TrackPointExtension>""")
            gpx_point.extensions.append(gpx_extension_speed)
            
            # For removing noise.
            last_t_time = t_time
            last_unix_time = unix_time
            last_dist = dist
            
            track_count += 1
            
            
        else:
            f.seek(-3, 1) # Seek forward (4 - 3 = +1 byte).
        
        
        
# Add a summary of the track.  This part may be informative.
if total_time == 0:
    total_time = t_time
if total_distance == 0:
    total_distance = dist
net_speed = total_distance / (total_time / 3600) # km/h
if stop_localtime == symbian_to_unix_time(0):
    stop_localtime = unix_time + TZ_hours * 3600
real_time = stop_localtime - start_localtime
gross_speed = total_distance / (real_time / 3600) # km/h
gpx.tracks[0].description = "[" \
    + "Total time: " + format_timedelta(total_time) + '; '\
    + "Total distance: " + str(round(total_distance, 3)) + ' km; '\
    + "Net speed: " + str(round(net_speed, 3)) + ' km/h; '\
    + "Start time: " + format_datetime(start_localtime) + '; '\
    + "Stop time: " + format_datetime(stop_localtime) + '; '\
    + "Real time: " + format_timedelta(real_time) + '; '\
    + "Gross speed: " + str(round(gross_speed, 3)) + ' km/h'\
    + "]"
    
# Finally, print or write the gpx. 
#print(gpx.to_xml('1.1'))

result = gpx.to_xml('1.1')
result_file = open(gpx_file, 'w')
result_file.write(result)
result_file.close()
    
