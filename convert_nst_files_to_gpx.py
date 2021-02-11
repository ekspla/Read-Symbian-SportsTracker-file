#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""Script to read the old- and the new-ver (Nokia) Symbian SportsTracker files.

External modules, nst.py and scsu.py, are used to parse the data in the files.
For temporal track files (Rec*.tmp), use convert_nst_rec_to_gpx.py.
"""
import sys
from pathlib import Path

import nst
(CONFIG, TRACK, ROUTE, TMP) = (nst.CONFIG, nst.TRACK, nst.ROUTE, nst.TMP)

def args_usage():
    # Arguments and help.
    argvs = sys.argv
    argc = len(argvs)
    if argc < 2:
        print(f'Usage: # python {argvs[0]} input_filename\n'
            'This script reads track/route files (W*.dat/R*.dat) of the old-'
            'version and track files of the new-version (W*.dat) Symbian '
            '(Nokia) SportsTracker.\n Track files with heart-rate sensor (the '
            'new ver.) were not tested.')
        sys.exit(0)
    #print(argvs[1])
    in_file = Path(argvs[1])
    #print(in_file)
    return in_file

def check_file_type_version(f):
    # Check if it is the correct file.
    #f.seek(0x00000, 0)
    # 8 (4+4) bytes, little endian U32+U32.
    (application_id, nst.FILE_TYPE) = nst.read_unpack('<2I', f)
    if application_id != nst.APP_ID or nst.FILE_TYPE not in {TRACK, ROUTE}:
        print(f'Unexpected file type: {nst.FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Version: {version}')
    (nst.OLDNST, nst.OLDNST_ROUTE, nst.NST) = (
        version < 10000, 10000 <= version < 20000, 20000 <= version)

def parse_info_part_of_tracks(f):
    # Track ID and Totaltime.
    track_id_addr = 0x00014 # Fixed addresses of oldNST and the new NST tracks.
    if nst.FILE_TYPE == TMP: track_id_addr += 0x04 # The 4-byte blank (0x18).
    f.seek(track_id_addr, 0) # 8 (4+4) bytes, little endian U32+U32.
    (track_id, total_time) = nst.read_unpack('<2I', f)
    del track_id # Not in use.
    #print(f'Track ID: {track_id}')

    nst.total_time = total_time / 100 # Totaltime in seconds.
    #print(f'Total time: {nst.format_timedelta(nst.total_time)}')

    # Total Distance.
    if nst.NST: f.seek(0x00004, 1) # Skip.  4-byte offset to OLDNST.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    #print(f'Total distance: {round(nst.total_distance, 3)} km')

    # Calculate Net speed in km/h.
    net_speed = nst.total_distance / (nst.total_time / 3600) # km/h
    del net_speed # Not in use.
    #print(f'Net speed: {round(net_speed, 3)} km/h')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = nst.read_unpack('<2q', f)
    nst.START_LOCALTIME = nst.symbian_to_unix_time(start_localtime)
    nst.stop_localtime = nst.symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    #print(f'Start: {nst.format_datetime(nst.START_LOCALTIME)}+09:00')
    #print(f'Stop : {nst.format_datetime(nst.stop_localtime)}+09:00')

    # Calculate Realtime, which is greater than totaltime if pause is used.
    real_time = nst.stop_localtime - nst.START_LOCALTIME # Realtime in seconds.
    #print(f'Realtime: {nst.format_timedelta(real_time)}')

    # Calculate Gross speed in km/h.
    gross_speed = nst.total_distance / (real_time / 3600) # km/h
    del gross_speed # Not in use.
    #print(f'Gross speed: {round(gross_speed, 3)} km/h')

    # User ID, please see config.dat.
    (nst.USER_ID, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'User id: {nst.USER_ID}')

    # Type of activity.  Walk, run, bicycle, etc. See config.dat for details.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = nst.read_unpack('<H', f) # 2 bytes, little endian U16.
    nst.activity_type = (str(activity) if activity >= len(nst.ACTIVITIES) 
                         else nst.ACTIVITIES[activity])
    #print(f'Activity: {nst.activity_type}')

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
    nst.START_TIME = nst.symbian_to_unix_time(start_time)
    nst.stop_time = nst.symbian_to_unix_time(stop_time)
    #print(f'Start Z: {nst.format_datetime(nst.START_TIME)}Z')
    #print(f'Stop Z : {nst.format_datetime(nst.stop_time)}Z')

    # Timezone can be calculated with the starttimes in Z and in localtime.
    nst.TZ_HOURS = int(nst.START_LOCALTIME - nst.START_TIME) / 3600

    # This will overwrite the realtime shown above.
    real_time = nst.stop_time - nst.START_TIME # Realtime in seconds.
    #print(f'Realtime Z: {nst.format_timedelta(real_time)}')

    if nst.NST:
        # Read SCSU encoded user comment of variable length.
        comment_addr = 0x00222 # Fixed address of NST tracks.
        if nst.FILE_TYPE == TMP: comment_addr += 0x4 # The 4-byte blank (0x226).
        nst.comment = nst.scsu_reader(f, comment_addr) # This address is fixed.
        #if nst.comment: print(f'Comment: {nst.comment}')

def parse_info_part_of_routes(f):
    # Route ID.
    f.seek(0x00014, 0) # Go to 0x00014, this address is fixed.
    (route_id, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    del route_id # Not in use.
    #print(f'Route ID: {route_id}')

    # Read SCSU encoded name of the route.  Its length is variable.
    #f.seek(0x00018, 0) # Go to 0x00018, this address is fixed.
    nst.route_name = nst.scsu_reader(f)
    #print(f'Route name: {nst.route_name}')

    # Totaltime is not stored in the route file.

    # Total Distance.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    #print(f'Total distance: {round(nst.total_distance, 3)} km')

def read_pause_and_track(f, start_address):
    f.seek(start_address, 0) # Go to the start address of the main part.
    # Read pause data.  There is no pause data in route file.
    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if nst.FILE_TYPE in {ROUTE, TMP} 
        else nst.read_pause_data(f))
    del pause_count # Not in use.
    #if nst.FILE_TYPE == TRACK: nst.print_pause_list(pause_list) # For debug.
    #sys.exit(0)

    # Read trackpoint data.  The last trackpt_store is necessary in summarizing.
    (track_count, trackpt_store) = nst.read_trackpoints(f, pause_list)
    del track_count # Not in use.
    return trackpt_store

WRITE_FILE = False
def main():
    in_file = args_usage() # Arguments and help.

    with in_file.open(mode='rb') as f:

        check_file_type_version(f)
        gpx, nst.gpx_target = nst.initialize_gpx()

        # Start address of the main part (a pause data and a trackpt block).
        #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
        # Usually the numbers (4 bytes, little endian U32) are for 
        #     the new track 0x0800 = 0x07ff + 0x1, 
        #     the old track 0x0400 = 0x03ff + 0x1 and 
        #     the old route 0x0100 = 0x00ff + 0x1
        # but can be changed in a very rare case.
        (start_address, ) = nst.read_unpack('<I', f)
        start_address -= 1
        #print(f'Main part address: {hex(start_address)}')

        # Read information part of track/route files.
        if nst.FILE_TYPE == TRACK:
            parse_info_part_of_tracks(f)
        elif nst.FILE_TYPE == ROUTE:
            parse_info_part_of_routes(f)

        # Read the main part consisting a pause- and a trackpoint-data blocks.
        trackpt_store = read_pause_and_track(f, start_address)

    nst.add_gpx_summary(gpx, trackpt_store)

    gpx_path = Path(str(in_file)[:-3] + 'gpx') if WRITE_FILE else None
    nst.finalize_gpx(gpx, gpx_path) # Gpx xml to a file or print (if None).


if __name__ == '__main__':
    main()
