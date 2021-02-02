#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads track log files of the old-version Nokia SportsTracker.
"""
import sys
from pathlib import Path

import nst


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads track log files (W*.dat) of the old-version Nokia 
        SportsTracker.""")
    sys.exit(0)
#print(argvs[1])
nst.in_file = Path(argvs[1])
#print(nst.in_file)

with nst.in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    #f.seek(0x00000, 0)
    # 8 (4+4) bytes, little endian U32+U32.
    (APPLICATION_ID, nst.FILE_TYPE) = nst.read_unpack('<2I', f)
    (CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
    if APPLICATION_ID != 0x0e4935e8 or nst.FILE_TYPE != TRACK:
        print(f'Unexpected file type: {nst.FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Version: {version}')
    (nst.OLDNST, nst.OLDNST_ROUTE, nst.NST) = (
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not nst.OLDNST:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, nst.gpx_target = nst.initialize_gpx(nst.FILE_TYPE)

    # Start address of the main part (a pause data block and a trackpt block).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    (START_ADDRESS, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    START_ADDRESS -= 1
    #print(f'Main part address: {hex(START_ADDRESS)}')

    # Track ID and Totaltime.
    track_id_addr = 0x00014 # Fixed addresses of oldNST and the new NST tracks.
    if nst.FILE_TYPE == TMP: track_id_addr += 0x04 # The 4-byte blank (0x18).
    f.seek(track_id_addr, 0) # 8 (4+4) bytes, little endian U32+U32.
    (TRACK_ID, total_time) = nst.read_unpack('<2I', f)
    #print(f'Track ID: {TRACK_ID}')

    nst.total_time = total_time / 100 # Totaltime in seconds.
    #print(f'Total time: {nst.format_timedelta(nst.total_time)}')

    # Total Distance.
    if nst.NST: f.seek(0x00004, 1) # Skip.  4-byte offset to oldNST due to this.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    #print(f'Total distance: {round(nst.total_distance, 3)} km')

    # Calculate Net speed in km/h.
    net_speed = nst.total_distance / (nst.total_time / 3600) # km/h
    #print(f'Net speed: {round(net_speed, 3)} km/h')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = nst.read_unpack('<2q', f)
    nst.start_localtime = nst.symbian_to_unix_time(start_localtime)
    nst.stop_localtime = nst.symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    #print(f'Start: {nst.format_datetime(nst.start_localtime)}+09:00')
    #print(f'Stop : {nst.format_datetime(nst.stop_localtime)}+09:00')

    # Calculate Realtime, which is greater than totaltime if pause is used.
    real_time = nst.stop_localtime - nst.start_localtime # Realtime in seconds.
    #print(f'Realtime: {nst.format_timedelta(real_time)}')

    # Calculate Gross speed in km/h.
    gross_speed = nst.total_distance / (real_time / 3600) # km/h
    #print(f'Gross speed: {round(gross_speed, 3)} km/h')

    # User ID, please see config.dat.
    (nst.USER_ID, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'User id: {nst.USER_ID}')

    # Type of activity.  Walk, run, bicycle, etc. See config.dat for details.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = nst.read_unpack('<H', f) # 2 bytes, little endian U16.
    nst.description = (str(activity) if activity >= len(nst.ACTIVITIES) 
                       else nst.ACTIVITIES[activity])
    #print(f'Activity: {nst.description}')

    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases the name consists of 16-byte ASCII characters, e.g. 
    # '24/12/2019 12:34'.  They are not fully compatible with utf-8 in 
    # principle because they can be SCSU-encoded non-ASCII characters.
    track_name_addr = 0x00046 # This is the fixed address of the oldNST track.
    if nst.NST: track_name_addr += 0x04 # Offset at total_distance (-> 0x4a).
    if nst.FILE_TYPE == TMP: track_name_addr += 0x04 # 4-byte blank (-> 0x4e).
    nst.track_name = nst.scsu_reader(f, track_name_addr)
    #print(f'Track name: {nst.track_name}')

    # Starttime & Stoptime in UTC.
    start_stop_z_addr = 0x0018e # This is the fixed address of oldNST track.
    if nst.NST: start_stop_z_addr += 0x04 # Offset at total_distance (0x192).
    if nst.FILE_TYPE == TMP: start_stop_z_addr += 0x04 # 4-byte blank (0x196).
    f.seek(start_stop_z_addr, 0) # 16 (8+8) bytes, little endian I64+I64.
    (start_time, stop_time) = nst.read_unpack('<2q', f)
    nst.start_time = nst.symbian_to_unix_time(start_time)
    nst.stop_time = nst.symbian_to_unix_time(stop_time)
    #print(f'Start Z: {nst.format_datetime(nst.start_time)}Z')
    #print(f'Stop Z : {nst.format_datetime(nst.stop_time)}Z')

    # Timezone can be calculated with the starttimes in Z and in localtime.
    nst.TZ_HOURS = int(nst.start_localtime - nst.start_time) / 3600

    # This will overwrite the realtime shown above.
    real_time = nst.stop_time - nst.start_time # Realtime in seconds.
    #print(f'Realtime Z: {nst.format_timedelta(real_time)}')


    f.seek(START_ADDRESS, 0) # Go to the start address of the main part.
    # Read pause data.
    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if nst.FILE_TYPE in {ROUTE, TMP} else nst.read_pause_data(f))
    #print_pause_list(pause_list) # For debugging purposes.
    #sys.exit(0)

    # Read trackpoint data.  The last trackpoint is necessary in summarizing.
    (track_count, trackpoint_store) = nst.read_trackpoints(f, pause_list)

nst.add_gpx_summary(gpx, trackpoint_store)
WRITE_FILE = False
gpx_path = (Path(str(nst.in_file)[:-3] + 'gpx') if WRITE_FILE
            else None)
nst.finalize_gpx(gpx, gpx_path) # Gpx to a file or print (if None).
