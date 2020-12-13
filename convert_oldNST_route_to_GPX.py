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

def scsu_reader(file_object, address):
    """Reads SCSU encoded bytes of variable length from file_object and returns utf-8 using external decoder.
    
    Args: 
        file_object: file object to be read.
        address: start address of the SCSU encoded part.  The data is preceded by one byte integer (U8) 
                 which indicates the length of the character multiplied by four.
                 
    Returns:
        decoded_strings: a bytearray of decoded UTF-8.
    """
    file_object.seek(address, 0)
    (size, ) = struct.unpack('B', file_object.read(1)) # Read the size * 4 in bytes.
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
 This script reads route files (R*.dat) of old-version Nokia SportsTracker.""")
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

# Create the first route in the GPX:
gpx_route = gpxpy.gpx.GPXRoute()
gpx.routes.append(gpx_route)

# definition of extension
# Add TrackPointExtension namespace and schema location
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
    
    # Check if this is a route file.
    # 0x0E4935E8 ; Application ID.
    # 0x00000003 ; File type (c.f. 0x1 = config, 0x2 = Track, 0x3 = Route, 0x4 = tmp)
    #f.seek(0x00000, 0)
    (app_id, file_type) \
        = struct.unpack('<2I', f.read(8)) # little endian U32+U32, returns tuple
    if not (app_id == 0x0e4935e8 and file_type == 0x3):
        print('Unexpected file type:', file_type)
        quit()
        
        
    # Preliminary version check.
    # Read version number.  2 bytes.
    #f.seek(0x00008, 0) # go to 0x00008, this address is fixed.
    (version, ) \
        = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('Version: ', version)
    # 
    # Track log files of the old Nokia SportsTracker:          version < 10000.
    # Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
    # Track log files of Symbian SportsTracker:       20000 <= version
    if (version < 10000)|( 20000 <= version): # These versions are for tracks.
        print('Unexpected version number:', version)
        quit()
        
        
    # Read start address of the main part (pause and trackpoint data)
    #f.seek(0x0000C, 0) # go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    # 
    (pause_address, ) \
        = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    pause_address -= 1
    #print('Main part address: ', hex(pause_address))
    
    
    # Read Route ID, 4 bytes.
    f.seek(0x00014, 0) # go to 0x00014, this address is fixed.
    (route_id, ) \
        = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('Route ID: ', route_id)
    
    
    # Read SCSU encoded name of the route.  Its length is variable.
    #
    route_name = scsu_reader(f, 0x00018) # This address is fixed.
    #print('Route name: ', route_name)
    gpx.name = "[" + route_name + "]"
    gpx.routes[0].name = gpx.name
    
    
    # Read Total Distance, 4 bytes.
    (total_distance, ) \
        = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    total_distance /= 1e5 # Total distance in km
    #print('Total distance: ', round(total_distance, 3), ' km')
    
    
    # Add a summary of the route.  This part may be informative.
    gpx.routes[0].description = "[" \
        + "Total distance: " + str(round(total_distance, 3)) + ' km'\
        + "]"
    
    
    # Read number of track points, 4 bytes.
    #f.seek(0x000ff, 0)
    f.seek(pause_address, 0) # go to the start address of the main part, which is usually 0x000ff.
    (num_trackpt, ) \
        = struct.unpack('<I', f.read(4)) # little endian U32, returns tuple
    #print('Number of route pts: ', num_trackpt)
    
    
    # There are no pause data in route files.   
    # Go to the first trackpoint.
    
    t_time = 0 # Reset totaltime in seconds.
    dist = 0 #  Total distance in km.
    v = 0 # Velocity in km/h.
    track_count = 0

    # We have to calculate the timestamps in all of the trackpoints because of no Symbiantimes 
    # given in the trackpoint part of the old version.  This is very different from the new version.
    # We will use mtime as starttime, because the start/stop times stored in the route files are 
    # always 0, which means January 1st 0 AD 00:00:00.
    unix_time = in_file.stat().st_mtime
    last_t_time = 0
    
    while track_count < num_trackpt:
    
        (header, ) \
            = struct.unpack('B', f.read(1)) # Read the 1-byte header.
        #print(header)
        
        if header in {0x00, 0x02, 0x03}:
            # Read 22 bytes of data(4+4+4+4+2+4)
            (t_time, y_ax, x_ax, z_ax, v, d_dist) \
                = struct.unpack('<4IHI', f.read(22))
            t_time /= 100 # Totaltime in seconds
            
            # The latitudes and longtitudes are stored in I32s as popular DDDmm mmmmm format.
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
        
            if header in {0x80, 0x82, 0x83}:
            
                # Read 10 bytes of data(1+2+2+2+1+2).  1-byte dv.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) \
                    = struct.unpack('<B3hbH', f.read(10))
                
            elif (header == 0x92)|(header == 0x93):
            
                # Read 11 bytes of data(1+2+2+2+2+2).  2-byte dv.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) \
                    = struct.unpack('<B4hH', f.read(11))
                
            elif (header == 0x9A)|(header == 0x9B):
            
                # Read 13 bytes of data(1+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                (dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist) \
                    = struct.unpack('<B4hI', f.read(13))
                
            elif (header == 0xC2)|(header == 0xC3): # This case is quite rare.
            
                # Read 14 bytes of data(1+2+2+2+2+2+1+2).  1-byte dv.
                # Unknown3 & 4 show up in distant jumps.  They might have a meaning but we can live without it.  
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) \
                    = struct.unpack('<B5hbH', f.read(14))
                
            elif (header == 0xD2)|(header == 0xD3): # This case is quite rare.
            
                # Read 15 bytes of data(1+2+2+2+2+2+2+2).  2-byte dv.
                # Unknown3 & 4 show up in distant jumps.  They might have a meaning but we can live without it.  
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) \
                    = struct.unpack('<B6hH', f.read(15))
                
            elif (header == 0xDA)|(header == 0xDB): # I saw this only once in my track files.
            
                # Read 17 bytes of data(1+2+2+2+2+2+2+4).  2-byte dv. 4-byte d_dist.
                # Unknown3 & 4 show up in distant jumps.  They might have a meaning but we can live without it.  
                (dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist) \
                    = struct.unpack('<B6hI', f.read(17))
                
            t_time += dt_time / 100 # Totaltime in seconds.
            
            y_degree += dy_ax / 1e4 / 60 # Latitudes and longtitudes are given as differences.
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
            
            
        last_t_time = t_time # Store it for the next turn.
        
        
        # Print delimited text.
        #utc_time = format_datetime(unix_time) + "Z"
        #to_time = format_timedelta(t_time)
        #print(to_time, '\t', utc_time, '\t', round(d_dist / 100 / 1e3, 3), '\t', 
        #      round(dist, 3), '\t', round(y_degree, 10), '\t', round(x_degree, 10) , '\t', 
        #      round(z_ax, 1), '\t', round(v, 2), sep='')
        
        
        # Print gpx xml.
        gpx_point = gpxpy.gpx.GPXRoutePoint(
            latitude = round(y_degree, 10), 
            longitude = round(x_degree, 10), 
            elevation = round(z_ax, 1), 
            time = datetime.datetime.fromtimestamp(unix_time, datetime.timezone.utc), 
            name = str(track_count + 1))
        gpx_route.points.append(gpx_point)
        
        # This part may be informative.  Comment it out, if not necessary. 
        gpx_point.description \
            = 'Speed ' + str(round(v, 3)) + ' km/h ' + 'Distance ' + str(round(dist, 3)) + ' km'
        
        # In gpx 1.1, use trackpoint extensions to store speeds in m/s.
        speed = round(v / 3.6, 3) # velocity in m/s
        # Not quite sure if the <gpxtpx:TrackPointExtension> tags are okay in rtept.  Should it be gpxx?
        gpx_extension_speed = mod_etree.fromstring(
            f"""<gpxtpx:TrackPointExtension \
            xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v2">\
            <gpxtpx:speed>{speed}</gpxtpx:speed>\
            </gpxtpx:TrackPointExtension>""")
        gpx_point.extensions.append(gpx_extension_speed)
        
        
        track_count += 1
        
        
    # Calculate Net speed in km/h.
    net_speed = total_distance / (t_time / 3600) # km/h
    #print('Net speed: ', round(net_speed, 3), ' km/h')
    gpx.routes[0].description = gpx.routes[0].description[:-1] + '; '\
                                 + "Total time: " + format_timedelta(t_time) + '; '\
                                 + "Net speed: " + str(round(net_speed, 3)) + ' km/h' + "]"
    
    
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
    
