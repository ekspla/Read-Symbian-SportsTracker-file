#coding:utf-8
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



#  The native Symbian time format is a 64-bit value that represents microseconds 
#  since January 1st 0 AD 00:00:00 local time, nominal Gregorian.
#  BC dates are represented by negative values.
#
#  unix_time = symbian_time/1e6 - 62168256000
#
def symbian_to_unix_time(tdelta):
    return tdelta / 1e6 - 62168256000



# Arguments and help
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print("""Usage: # python %s input_filename' % argvs[0]\n
 This script reads track log files (*.dat) of symbian SportsTracker.
Log files with heart-rate sensor were not tested.
You have to modify this script to read files from new-version SportsTracker
because of slightly different data format.""")
    quit()
#print(argc)
#print(argvs[1])
#print(argvs[2])
#print(argvs[3])

#path = Path('.')
in_file = Path(argvs[1])
#print(in_file)



dist = 0 #  Total distance in km.
t_time = 0 # Totaltime in seconds.
v = 0 # Velocity in km/h.
unix_time = 0 # unix time.
fmt = "%Y-%m-%dT%H:%M:%S.%f" # ISO-8601 format.
fmt1 = "%H:%M:%S.%f" # Format for totaltime and realtime.



# Creating a new GPX:
# --------------------
    
gpx = gpxpy.gpx.GPX()

# Create the first track in the GPX:
gpx_track = gpxpy.gpx.GPXTrack()
gpx.tracks.append(gpx_track)

# Create the first segment in the GPX track:
gpx_segment = gpxpy.gpx.GPXTrackSegment()
gpx_track.segments.append(gpx_segment)
# definition of extension
# Add TrackPointExtension namespace
gpx.nsmap["gpxtpx"] = "http://www.garmin.com/xmlschemas/TrackPointExtension/v1"
gpx.nsmap["gpxx"] = "http://www.garmin.com/xmlschemas/GpxExtensions/v3"

#add extension to header
#nsmap = {namespace[1:-1]:'https://www8.garmin.com/xmlschemas/TrackPointExtensionv2.xsd'}
#gpx.nsmap = nsmap



with in_file.open(mode='rb') as f:
    # Read Track ID and Totaltime, 4+4 bytes.
    f.seek(0x00014, 0) # go to 0x00014, this address is fixed.
    #print(f.tell())
    (track_id, total_time) = struct.unpack('<2I', f.read(8)) # little endian U32+U32, returns tuple
    #print('Track ID: ', track_id) # print Track ID.
    
    total_time /= 100 # Totaltime in seconds.
    #print('Total time: ', datetime.datetime.fromtimestamp(round(total_time, 3), datetime.timezone.utc).strftime(fmt1)[:-3])
    
    
    # Read Total Distance, 4 bytes.
    (total_distance,) = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    total_distance /= 1e5 # Total distance in km
    #print('Total distance: ', round(total_distance, 3), ' km')
    
    
    # Calculate Net speed in km/h.
    net_speed = total_distance / (total_time / 3600) # km/h
    #print('Net speed: ', round(net_speed, 3), ' km/h')
    
    
    # Read Starttime and Stoptime in localtime, 8+8 bytes.
    (start_localtime, stop_localtime) = struct.unpack('<2q', f.read(16)) # little endian I64+I64, returns tuple
    start_localtime = symbian_to_unix_time(start_localtime)
    # Print start time in localtime.  Change the suffix according to your timezone.  There are no timezone information in Symbian.
    # Take difference of starttime in localtime and those in UTC (see below) to see the timezone+DST.
    #print('Start: ', datetime.datetime.fromtimestamp(round(start_localtime, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "+09:00")
    
    stop_localtime = symbian_to_unix_time(stop_localtime)
    #print('Stop : ', datetime.datetime.fromtimestamp(round(stop_localtime, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "+09:00")
    
    
    # Calculate Realtime, which is different from Totaltime if autopause is used.
    real_time = stop_localtime - start_localtime # Realtime in seconds.
    # Never use the following line if your track is longer than a day.  This is an ad-hoc implimentation.
    #print('Realtime: ', datetime.datetime.fromtimestamp(round(real_time, 3), datetime.timezone.utc).strftime(fmt1)[:-3])
    
    
    # Calculate Gross speed in km/h.
    gross_speed = total_distance / (real_time / 3600) # km/h
    #print('Gross speed: ', round(gross_speed, 3), ' km/h')
    
    
    # Read User ID, please see config.dat.
    (user_id,) = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('User id: ', user_id)
    gpx.author_name = str(user_id)
    
    
    # Read type of activity.  For details, please see config.dat.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity,) = struct.unpack('<H', f.read(2)) # little endian U16, returns tuple
    if activity == 0:
        #print('Activity: Walking')
        gpx.description = "[" + 'Walking' + "]"
    elif activity == 1:
        #print('Activity: Running')
        gpx.description = "[" + 'Running' + "]"
    elif activity == 2:
        #print('Activity: Cycling')
        gpx.description = "[" + 'Cycling' + "]"
    else:
        #print('Activity: ', activity) # Please see config.dat.
        gpx.description = "[" + str(activity) + "]"
    
    
    # Read name of the track, which is usually the datetime.
    f.seek(0x00047, 0) # go to address 0x00047, this address is fixed.
    (track_name,) = struct.unpack('16s', f.read(16)) # The name is strings of 16 bytes.
    #print('Track name: ', track_name.decode())
    gpx.name = "[" + str(track_name.decode()) + "]"
    gpx.tracks[0].name = gpx.name
    
    
    # Read Starttime & Stoptime in UTC.
    f.seek(0x0018E, 0) # go to 0x0018E, this address is fixed.
    (start_time, stop_time) = struct.unpack('<2q', f.read(16)) # little endian I64+I64, returns tuple
    start_time = symbian_to_unix_time(start_time)
    #print('Start Z: ', datetime.datetime.fromtimestamp(round(start_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z")
    
    # This is for localtime in JST.
    #gpx.time = datetime.datetime.fromtimestamp(start_time, datetime.timezone(datetime.timedelta(hours=+9),))
    # We can calculate the timezone by using the starttimes in Z and localtime.
    TZ_hours = int(start_localtime - start_time) / 3600
    gpx.time = datetime.datetime.fromtimestamp(start_time, datetime.timezone(datetime.timedelta(\
                                                hours = TZ_hours),))
    
    stop_time = symbian_to_unix_time(stop_time)
    #print('Stop Z : ', datetime.datetime.fromtimestamp(round(stop_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z")
    
    # This will overwrite the realtime shown above.
    real_time = stop_time - start_time # Realtime in seconds.
    # Never use the following line if your track is longer than a day.  This is an ad-hoc implimentation.
    #print('Realtime Z: ', datetime.datetime.fromtimestamp(round(real_time, 3), datetime.timezone.utc).strftime(fmt1)[:-3])
    
    
    # Read number of autopause data, 4 bytes.
    f.seek(0x003ff, 0) # go to address 0x003ff, this address is fixed.
    (num_pause,) = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('Number of pause data: ', num_pause) # print number of pause data
    pause_address = f.tell()
    
    track_address = pause_address + num_pause * 14 # Autopause data are 14 bytes.
    # Read number of track points, 4 bytes.
    f.seek(track_address, 0) # skip autopause data part
    (num_trackpt,) = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('Number of track pts: ', num_trackpt)
    track_address = f.tell()
    
    t_time = 0
    pause_count = 0
    utc_time = ''
    pause_list = []
    
    f.seek(pause_address, 0)
    while pause_count < num_pause:
    
        pause_time = 0 # Reset pause_time
        
        # Read 14 bytes of data(1+4+1+8).  Symbiantimes in the old version files are in localtime zone.
        (unknown, t_time, flag, symbian_time) = struct.unpack('<BIBq', f.read(14))
        pause_address = f.tell()
        
        t_time = t_time / 100 # Totaltime in seconds
        unix_time = symbian_to_unix_time(symbian_time)
        #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z"
        #print(unknown, '\t', datetime.timedelta(seconds=round(t_time, 3)), '\t',  flag, '\t', utc_time, sep = '')
        
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
            if t4_time != t_time:
                print('Error in autopause.')
                quit()
                
            pause_time = unix_time - suspend_time
            pause_list.append((t_time, pause_time, unix_time))

        # Resume flag = 8 # Not quite sure how to use the flag = 8 data.  Use it as a correction of time. 
        elif flag == 8:
            pause_time = 0
            pause_list.append((t_time, pause_time, unix_time))

        pause_count += 1
        
    #print('Total time', '\t', 'Pause time', '\t', 'UTC', sep ='')
    #for pause in pause_list:
    #    t_time, pause_time, unix_time = pause
    #    print(datetime.timedelta(seconds=round(t_time, 3)), '\t', \
    #          datetime.timedelta(seconds=round(pause_time, 3)), '\t', \
    #          datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z", sep = '')
    #quit()
    
    # Go to the first trackpoint.
    f.seek(track_address, 0)
    
    t_time = 0
    track_count = 0
    unix_time = start_time
    last_t_time = 0
    while track_count < num_trackpt:
    
        (header,) = struct.unpack('B', f.read(1)) # Read the 1-byte header.
        #print(header)
        
        # For header 0x0*
        if header in {0x00, 0x02, 0x03}: # Read 22 bytes of data(4+4+4+4+2+4)
            (t_time, y_ax, x_ax, z_ax, v, d_dist) = struct.unpack('<4IHI', f.read(22))
            t_time = t_time / 100 # Totaltime in seconds
            
            # The latitudes and longtitudes are stored in I32s as popular DDDmm mmmmm format.
            y_degree = int(y_ax / 1e6)
            x_degree = int(x_ax / 1e6)
            y_mm_mmmm = y_ax % 1e6
            x_mm_mmmm = x_ax % 1e6
            y_degree += y_mm_mmmm / 1e4 / 60 # Convert minutes to degrees.
            x_degree += x_mm_mmmm / 1e4 / 60
            
            z_ax /= 10 # Altitude in meter.
            
            v = v / 100 * 3.6 # Multiply (m/s) by 3.6 to get velocity in km/h.
            
            dist += d_dist / 100 / 1e3 # Divide (m) by 1e3 to get distance in km.
            
            unix_time = unix_time + (t_time - last_t_time)
            
            #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 2), datetime.timezone.utc).isoformat()
            #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z"
            #print(t_time, y_ax, x_ax , z_ax, v, dist, utc_time)
            
        elif header in {0x80, 0x82, 0x83, 0x92, 0x93, 0x9A, 0x9B, 0xC2, 0xC3, 0xD2, 0xD3, 0xDA, 0xDB}:
        
            # For header 0x8*.
            if header in {0x80, 0x82, 0x83}:
            
                # Read 10 bytes of data(1+2+2+2+1+2).  1-byte dv.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) = struct.unpack('<B3hbH', f.read(10))
                
            # For header 0x92 or 0x93.
            elif (header == 0x92)|(header == 0x93):
            
                # Read 11 bytes of data(1+2+2+2+2+2).  2-byte dv.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) = struct.unpack('<B4hH', f.read(11))

            # For header 0x9A or 0x9B.
            elif (header == 0x9A)|(header == 0x9B):
            
                # Read 13 bytes of data(1+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) = struct.unpack('<B4hI', f.read(13))
                
            # For header 0xC*.  This case is quite rare.
            # We don't know about the additional two parameters.
            elif (header == 0xC2)|(header == 0xC3):
            
                # Read 14 bytes of data(1+2+2+2+2+2+1+2).  1-byte dv, in analogy to those with 0x8* header.
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) = struct.unpack('<B5hbH', f.read(14))
                
            # For header 0xD2 or 0xD3.  This case is quite rare.
            # We don't know about the additional two parameters.
            elif (header == 0xD2)|(header == 0xD3):
            
                # Read 15 bytes of data(1+2+2+2+2+2+2+2).  2-byte dv, in analogy to those with 0x9* header.
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) = struct.unpack('<B6hH', f.read(15))
                
            # For header 0xDA or 0xDB.
            # We don't know about the additional two parameters.
            elif (header == 0xDA)|(header == 0xDB):
            
                # Read 17 bytes of data(1+2+2+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) = struct.unpack('<B6hI', f.read(17))
                
            t_time += dt_time / 100 # Totaltime in seconds.
            
            y_degree += dy_ax / 1e4 / 60 # Latitudes and longtitudes are given as differences.
            x_degree += dx_ax / 1e4 / 60
            
            z_ax += dz_ax / 10 # Altitudes in meters are also given as differences.
            
            v += dv / 100 * 3.6 # Velocity, as well.  Multiply (m/s) by 3.6 to get velocity in km/h.
            
            dist += d_dist / 100 / 1e3 # Divide (m) by 1e3 to get total distance in km.
            
            unix_time += dt_time / 100
            #unix_time += unknown1 / 100 # This doesn't work.
            #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 2), datetime.timezone.utc).isoformat()
            #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z"
            #print(t_time, dy_ax, dx_ax , z_ax, v, dist, unknown1, unknown2)
            
        # Other headers which I don't know.
        else:
        
            print('At address:', hex(f.tell() - 1))
            break
            
            
        if len(pause_list) > 0:
        
            t4_time, pause_time, resume_time = pause_list[0]
            #print(datetime.timedelta(seconds=round(t4_time, 3)), datetime.timedelta(seconds=round(pause_time, 3)))
            
            # Just after the autopause, use the autopause data.
            # Still not quite sure if this works.
            if (t_time >= t4_time):
            
                if (unix_time < resume_time - TZ_hours * 3600):
                    unix_time = (t_time - t4_time) + (resume_time - TZ_hours * 3600) # There might be few second of error, which I don't care.
                    
                del pause_list[0]
                
        last_t_time = t_time # Store it for the next turn.
        
        
        # Print delimited text.
        #utc_time = datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc).strftime(fmt)[:-3] + "Z"
        # Never use the following line if your track is longer than a day.  This is an ad-hoc implimentation.
        #to_time = datetime.datetime.fromtimestamp(round(t_time, 3), datetime.timezone.utc).strftime(fmt1)[:-3]
        #print(to_time, '\t', utc_time, '\t', round(d_dist / 100 / 1e3, 3), '\t', \
        #      round(dist, 3), '\t', round(y_degree, 10), '\t', round(x_degree, 10) , '\t', round(z_ax, 1), '\t', \
        #      round(v, 2), sep='')
        
        
        # Print gpx xml.
        gpx_point=gpxpy.gpx.GPXTrackPoint(latitude=round(y_degree, 10), longitude=round(x_degree, 10), \
                                            elevation=round(z_ax, 1), \
                                            time=datetime.datetime.fromtimestamp(round(unix_time, 3), datetime.timezone.utc), \
                                            name=str(track_count + 1))
        gpx_segment.points.append(gpx_point)
        
        # This part may be informative.  Comment it out, if not necessary. 
        gpx_point.description='Speed ' + str(round(v, 3)) + ' km/h ' + 'Distance ' + str(round(dist, 3)) + ' km'
        
        # In gpx 1.1, use trackpoint extensions to store speeds in m/s.
        speed = round(v / 3.6, 3) # velocity in m/s
        gpx_extension_speed = mod_etree.fromstring(f"""<gpxtpx:TrackPointExtension \
                                                    xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\
                                                    <gpxtpx:speed>{speed}</gpxtpx:speed>\
                                                    </gpxtpx:TrackPointExtension>\
                                                    """)
        gpx_point.extensions.append(gpx_extension_speed)
        
        
        track_count += 1
        
        
    # Handling of errors.
    if track_count != num_trackpt:
        print('Track points count error: ', track_count, num_trackpt)
        #print(track_count, num_trackpt)
        quit()
        
        
    # Finally, print or write the gpx. 
    print(gpx.to_xml('1.1'))
    
    #result = gpx.to_xml('1.1')
    #result_file = open(gpx_file, 'w')
    #result_file.write(result)
    #result_file.close()
    
