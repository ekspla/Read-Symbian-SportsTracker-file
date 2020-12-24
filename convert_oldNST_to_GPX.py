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

# Helper function to read and unpack
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


# Arguments and help
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print("""Usage: # python %s input_filename' % argvs[0]\n
 This script reads track log files (W*.dat) of old-version Nokia SportsTracker.""")
    quit()
#print(argc)
#print(argvs[1])
#print(argvs[2])
#print(argvs[3])

#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)
#gpx_file = Path(argvs[1][:-3] + 'gpx')


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
    
    # Check if this is a track log file.
    # 0x0E4935E8 ; Application ID.
    # 0x00000002 ; File type (c.f. 0x1 = config, 0x2 = Track, 0x3 = Route, 0x4 = tmp)
    #f.seek(0x00000, 0)
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (app_id, file_type) = read_unpack('<2I', f)
    if not (app_id == 0x0e4935e8 and file_type == 0x2):
        print('Unexpected file type:', file_type)
        quit()
        
        
    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print('Version: ', version)
    # 
    # Track log files of the old Nokia SportsTracker:          version < 10000.
    # Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
    # Track log files of Symbian SportsTracker:       20000 <= version
    if version >= 10000:
        print('Version number greater than expected:', version)
        quit()
        
        
    # Start address of the main part (pause and trackpoint data).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    # 
    (start_address, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    start_address -= 1
    #print('Main part address: ', hex(start_address))
    
    
    # Track ID and Totaltime.
    f.seek(0x00014, 0) # Go to 0x00014, this address is fixed.
    # Read 8 (4+4) bytes, little endian U32+U32, returns tuple.
    (track_id, total_time) = read_unpack('<2I', f)
    #print('Track ID: ', track_id)
    
    total_time /= 100 # Totaltime in seconds.
    #print('Total time: ', format_timedelta(total_time))
    
    
    # Total Distance.
    (total_distance, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    total_distance /= 1e5 # Total distance in km
    #print('Total distance: ', round(total_distance, 3), ' km')
    
    
    # Calculate Net speed in km/h.
    net_speed = total_distance / (total_time / 3600) # km/h
    #print('Net speed: ', round(net_speed, 3), ' km/h')
    
    
    # Starttime and Stoptime in localtime.
    # Read 16 (8+8) bytes, little endian I64+I64, returns tuple.
    (start_localtime, stop_localtime) = read_unpack('<2q', f)
    start_localtime = symbian_to_unix_time(start_localtime)
    # Print start time in localtime.  Change the suffix according to your timezone, 
    # because there is no timezone information in Symbian.
    # Take difference of starttime in localtime and those in UTC (see below) to see the timezone+DST.
    #print('Start: ', format_datetime(start_localtime) + "+09:00")
    
    stop_localtime = symbian_to_unix_time(stop_localtime)
    #print('Stop : ', format_datetime(stop_localtime) + "+09:00")
    
    
    # Calculate Realtime, which is different from Totaltime if pause is used.
    real_time = stop_localtime - start_localtime # Realtime in seconds.
    #print('Realtime: ', format_timedelta(real_time))
    
    
    # Calculate Gross speed in km/h.
    gross_speed = total_distance / (real_time / 3600) # km/h
    #print('Gross speed: ', round(gross_speed, 3), ' km/h')
    
    
    # Add a summary of the track.  This part may be informative.
    gpx.tracks[0].description = "[" \
        + "Total time: " + format_timedelta(total_time) + '; '\
        + "Total distance: " + str(round(total_distance, 3)) + ' km; '\
        + "Net speed: " + str(round(net_speed, 3)) + ' km/h; '\
        + "Start localtime: " + format_datetime(start_localtime) + '; '\
        + "Stop localtime: " + format_datetime(stop_localtime) + '; '\
        + "Real time: " + format_timedelta(real_time) + '; '\
        + "Gross speed: " + str(round(gross_speed, 3)) + ' km/h'\
        + "]"
    
    
    # User ID, please see config.dat.
    (user_id, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print('User id: ', user_id)
    gpx.author_name = str(user_id)
    
    
    # Type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = read_unpack('<H', f) # Read 2 bytes, little endian U16, returns tuple.
    activities = ['Walking', 'Running', 'Cycling', 'Skiing', 'Other 1', 'Other 2', 'Other 3', 
                  'Other 4', 'Other 5', 'Other 6', 'Mountain biking', 'Hiking', 'Roller skating', 
                  'Downhill skiing', 'Paddling', 'Rowing', 'Golf', 'Indoor']
    description = activities[activity] if activity < len(activities) else str(activity)
    #print('Activity: ', description)
    gpx.description = "[" + description + "]"
    
    
    # Read SCSU encoded name of the track, which is usually the datetime.
    # 
    # In most cases, the name consists of ASCII characters, strings of 16 bytes, such as 
    # '24/12/2019 12:34'.  The strings are, in principle, not fully compatible with utf-8 but 
    # can be non-ASCII characters encoded with SCSU (simple compression scheme for unicode).
    #
    track_name = scsu_reader(f, 0x00046) # This address is fixed.
    #print('Track name: ', track_name)
    gpx.name = "[" + track_name + "]"
    gpx.tracks[0].name = gpx.name
    
    
    # Starttime & Stoptime in UTC.
    f.seek(0x0018e, 0) # Go to 0x0018e, this address is fixed.
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
    
    # This will overwrite the realtime shown above.
    real_time = stop_time - start_time # Realtime in seconds.
    #print('Realtime Z: ', format_timedelta(real_time))
    
    
    # Number of pause data.
    #start_address = 0x003ff
    f.seek(start_address, 0) # Go to the start address of the main part, which is usually 0x003ff.
    (num_pause, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print('Number of pause data: ', num_pause)
    pause_address = f.tell() # start_address + 4
    
    # Number of track points.
    f.seek(num_pause * 14, 1) # Pause data are 14 bytes each.  Skip pause data part.
    (num_trackpt, ) = read_unpack('<I', f) # Read 4 bytes, little endian U32, returns tuple.
    #print('Number of track pts: ', num_trackpt)
    track_address = f.tell()
    
    
    # Go to the first pause data.
    f.seek(pause_address, 0)
    
    t_time = 0 # Totaltime in seconds.
    unix_time = 0 # unix time.
    utc_time = ''
    pause_time = 0 # Time between suspend and resume.
    pause_count = 0
    pause_list = []
    
    while pause_count < num_pause:
    
        # Read 14 bytes of data(1+4+1+8).  Symbiantimes of the old version are in localtime zone,
        # while those of the new version in UTC (Z).
        # The first unknown field seems to have no meaning because it is always 0x01.
        (unknown, t_time, flag, symbian_time) = read_unpack('<BIBq', f)
        
        t_time /= 100 # Totaltime in seconds.
        unix_time = symbian_to_unix_time(symbian_time)
        #utc_time = format_datetime(unix_time) #+ "Z"
        #print(unknown, '\t', format_timedelta(t_time), '\t', flag, '\t', utc_time, sep = '')
        
        # Start flag = 1, we don't use these data.  Just store them for the future purposes.
        if flag == 1:
            starttime = unix_time
            start_t_time = t_time
            
        # Stop flag = 2, we don't use these data.  Just store them for the future purposes.
        elif flag == 2:
            stoptime = unix_time
            stop_t_time = t_time
            
        # Suspend flag = 3 (manually) or 4 (automatically)
        elif (flag == 3)|(flag == 4):
            suspend_time = unix_time
            t4_time = t_time
            
        # Resume flag = 5
        elif flag == 5:
            # A pair of flag-4 (also flag-3) and flag-5 data should have a common totaltime.
            if t4_time != t_time:
                print('Error in pause.')
                quit()
                
            pause_time = unix_time - suspend_time
            pause_list.append((t_time, pause_time, unix_time))
            
        # Resume flag = 8 # Not quite sure how to use the flag-8 data.  Use it as a correction of time. 
        elif flag == 8:
            pause_time = 0
            pause_list.append((t_time, pause_time, unix_time))
            
        pause_count += 1
        
    #print('Total time', '\t', 'Pause time', '\t', 'Datetime', sep ='')
    #for pause in pause_list:
    #    t_time, pause_time, unix_time = pause
    #    print(format_timedelta(t_time), '\t', 
    #          format_timedelta(pause_time), '\t', 
    #          format_datetime(unix_time) + "I", sep = '')
    #quit()
    
    
    # Go to the first trackpoint.
    f.seek(track_address, 0)
    
    t_time = 0 # Reset totaltime in seconds.
    dist = 0 #  Total distance in km.
    v = 0 # Velocity in km/h.
    track_count = 0

    # We have to calculate the timestamps in all of the trackpoints because of no Symbiantimes 
    # given in the trackpoint part of the old version.  This is very different from the new version.
    unix_time = start_time
    last_t_time = 0
    
    while track_count < num_trackpt:
    
        (header, ) = read_unpack('B', f) # Read the 1-byte header.
        #print(header)
        
        if header in {0x00, 0x02, 0x03}:
            # Read 22 bytes of data(4+4+4+4+2+4).  Negative y and x mean South and West, respectively.
            (t_time, y_ax, x_ax, z_ax, v, d_dist) = read_unpack('<I3iHI', f)
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
            
            unix_time += (t_time - last_t_time)
            #utc_time = format_datetime(unix_time) + "Z"
            #print(t_time, y_ax, x_ax, z_ax, v, dist, utc_time)
            
        elif header in {0x80, 0x82, 0x83, 
                        0x92, 0x93, 
                        0x9A, 0x9B, 
                        0xC2, 0xC3, 
                        0xD2, 0xD3, 
                        0xDA, 0xDB}:
        
            if header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B}:
            
                if header in {0x80, 0x82, 0x83}:
                    fmt = '<B3hbH' # 0x80-83: Read 10 bytes of data(1+2+2+2+1+2).  1-byte dv.
                elif header in {0x92, 0x93}:
                    fmt = '<B4hH' # 0x92-93: Read 11 bytes of data(1+2+2+2+2+2).  2-byte dv.
                else: # 0x9A, 0x9B
                    fmt = '<B4hI' # 0x9A-9B: Read 13 bytes of data(1+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) = read_unpack(fmt, f)
                
            elif header in {0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}: # This case is quite rare.
            
                if header in {0xC2, 0xC3}:
                    fmt = '<B5hbH' # 0xC2-C3: Read 14 bytes of data(1+2+2+2+2+2+1+2).  1-byte dv.
                elif header in {0xD2, 0xD3}:
                    fmt = '<B6hH' # 0xD2-D3: Read 15 bytes of data(1+2+2+2+2+2+2+2).  2-byte dv.
                else: # 0xDA, 0xDB
                    fmt = '<B6hI' # 0xDA-DB: Read 17 bytes of data(1+2+2+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                
                # Unknown3 & 4 show up in distant jumps.  They might have a meaning but we can live without it.
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) = read_unpack(fmt, f)
                
            t_time += dt_time / 100 # Totaltime in seconds.
            
            y_degree += dy_ax / 1e4 / 60 # Latitudes and longitudes are given as differences.
            x_degree += dx_ax / 1e4 / 60
            
            z_ax += dz_ax / 10 # Altitudes in meters are also given as differences.
            
            v += dv / 100 * 3.6 # Velocity, as well.  Multiply (m/s) by 3.6 to get velocity in km/h.
            
            dist += d_dist / 100 / 1e3 # Divide (m) by 1e3 to get total distance in km.
            
            unix_time += dt_time / 100
            #utc_time = format_datetime(unix_time) + "Z"
            #print(t_time, dy_ax, dx_ax, z_ax, v, dist, unknown3, unknown4)
            
        # Other headers which I don't know.
        else:
        
            print('At address:', hex(f.tell() - 1))
            break
            
            
        if pause_list:
        
            t4_time, pause_time, resume_time = pause_list[0]
            #print(format_timedelta(t4_time), format_timedelta(pause_time))
            
            # Just after the pause, use the pause data.
            # Still not quite sure if this works.
            if (t_time + 0.5 >= t4_time):
            
                resume_time -= TZ_hours * 3600 # Conversion from localtime to UTC.
                
                if unix_time < resume_time:
                    # There might be few second of error, which I don't care.
                    unix_time = (t_time - t4_time) + resume_time
                    
                del pause_list[0]
                
        last_t_time = t_time # Store it for the next turn.
        
        
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
        
        
        track_count += 1
        
        
    # Handling of errors.
    if track_count != num_trackpt:
        print('Track point count error: ', track_count, num_trackpt)
        quit()
        
        
    # Finally, print or write the gpx. 
    print(gpx.to_xml('1.1'))
    
    #result = gpx.to_xml('1.1')
    #result_file = open(gpx_file, 'w')
    #result_file.write(result)
    #result_file.close()
    
