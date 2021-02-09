#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads route files of the old-version Nokia SportsTracker.
"""
import sys
from pathlib import Path

import nst
(CONFIG, TRACK, ROUTE, TMP) = (nst.CONFIG, nst.TRACK, nst.ROUTE, nst.TMP)


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads route files (R*.dat) of the old-version Nokia 
        SportsTracker.""")
    sys.exit(0)
#print(argvs[1])
in_file = Path(argvs[1])
#print(in_file)

with in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    #f.seek(0x00000, 0)
    # 8 (4+4) bytes, little endian U32+U32.
    (application_id, nst.FILE_TYPE) = nst.read_unpack('<2I', f)
    if application_id != nst.APP_ID or nst.FILE_TYPE != ROUTE:
        print(f'Unexpected file type: {nst.FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008, 0) # Go to 0x00008, this address is fixed.
    (version, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Version: {version}')
    (nst.OLDNST, nst.OLDNST_ROUTE, nst.NST) = (
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not nst.OLDNST_ROUTE:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, nst.gpx_target = nst.initialize_gpx(nst.FILE_TYPE)

    # Start address of the main part (a trackpt block).
    #f.seek(0x0000C, 0) # Go to 0x0000C, this address is fixed.
    # Usually the numbers are for 
    #     the new track 0x0800 = 0x07ff + 0x1, 
    #     the old track 0x0400 = 0x03ff + 0x1 and 
    #     the old route 0x0100 = 0x00ff + 0x1
    # but can be changed in a very rare case.
    (START_ADDRESS, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    START_ADDRESS -= 1
    #print(f'Main part address: {hex(START_ADDRESS)}')

    # Route ID.
    f.seek(0x00014, 0) # Go to 0x00014, this address is fixed.
    (ROUTE_ID, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    #print(f'Route ID: {ROUTE_ID}')

    # Read SCSU encoded name of the route.  Its length is variable.
    #f.seek(0x00018, 0) # Go to 0x00018, this address is fixed.
    nst.route_name = nst.scsu_reader(f)
    #print(f'Route name: {route_name}')

    # Totaltime is not stored in the route file.

    # Total Distance.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    #print(f'Total distance: {round(nst.total_distance, 3)} km')


    f.seek(START_ADDRESS, 0) # Go to the start address of the main part.
    # Read pause data.
    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if nst.FILE_TYPE in {ROUTE, TMP} else nst.read_pause_data(f))
    #nst.print_pause_list(pause_list) # For debugging purposes.
    #sys.exit(0)

    # Read trackpoint data.  The last trackpt_store is necessary in summarizing.
    (track_count, trackpt_store) = nst.read_trackpoints(f, pause_list)

nst.add_gpx_summary(gpx, trackpt_store)

WRITE_FILE = False
gpx_path = Path(str(in_file)[:-3] + 'gpx') if WRITE_FILE else None
nst.finalize_gpx(gpx, gpx_path) # Gpx xml to a file or print (if None).
