#!/usr/bin/env python
#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""Script to read temporal track log files (Rec*.tmp) of Symbian SportsTracker.

Modules of nst.py, scsu.py and mini_gpx.py are used to parse data in the files.
Gpx writing part depends on lxml and its use is strongly recommended due to 
performance reasons, though a fallback to built-in ElementTree is implemented.
For usual track/route files (W*.dat/R*.dat), use convert_nst_files_to_gpx.py.
"""
from os import getenv
import sys
import struct
from pathlib import Path

import nst
(CONFIG, TRACK, ROUTE, TMP) = (nst.CONFIG, nst.TRACK, nst.ROUTE, nst.TMP)

def args_usage():
    """A blief explanation of usage and handling of command line arguments.

    Returns:
        in_file: a path object of input file.
    """
    argvs = sys.argv
    argc = len(argvs)
    if argc < 2:
        print(f'Usage: # python {argvs[0]} input_filename\n'
            'This script reads temporal track log files (Rec*.tmp) of symbian'
            'SportsTracker.  Log files with heart-rate sensor were not tested.')
        sys.exit(0)
    in_file = Path(argvs[1])
    return in_file

def check_file_type_version(f):
    """Checks if it is the correct file by reading app_id, file_type & version.

    Sets FILE_TYPE(int 2-4) and NEW_FORMAT(bool, new trackpt format) in nst.py.

    Args:
        f: a file object to be read.

    Returns:
        version: int 0, 1, 2.  To be used in parse_track_informations().
    """
    # Chunks in the temporal file always start with b'\x00\x00\x00\x00' blank.
    # Due to this blank, there is a 4-byte offset to the addresses shown below.
    #f.seek(0x00000, 0)
    # 12 (4+4+4) bytes, little endian U32+U32+U32.
    (application_id, nst.FILE_TYPE, blank) = nst.read_unpack('<3I', f)
    if application_id != nst.APP_ID or nst.FILE_TYPE != TMP or blank != 0x0:
        print(f'Unexpected file type: {nst.FILE_TYPE}')
        sys.exit(1)

    #f.seek(0x00008 + 0x04, 0) # Go to 0x0000C, this address is fixed.
    (ver, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'Version: {ver}')
    (ver0, ver1, ver2) = (ver < 10000, 10000 <= ver < 20000, 20000 <= ver)
    # NEW_FORMAT indicates trackpoint format: True/False = New/Old format.
    if ver0:
        (nst.NEW_FORMAT, version) = (False, 0)
    elif ver1 and nst.FILE_TYPE == ROUTE:
        (nst.NEW_FORMAT, version) = (False, 1)
    elif ver1 and nst.FILE_TYPE == TRACK:
        (nst.NEW_FORMAT, version) = (True, 1)
    else: # if ver2
        (nst.NEW_FORMAT, version) = (True, 2)

    if not (ver1 or ver2): # Preliminary version check.
        print(f'Unexpected version number: {ver}')
        sys.exit(1)

    return version

def parse_track_informations(f, ver=1):
    """Reads and processes the track information.

    START_LOCALTIME, START_TIME and TZ_HOURS are stored in the nst.py module.

    Args:
        f: the file object.
        ver (optional): file version (int 0, 1 or 2).  Defaults to 1.
    """
    # Track ID and Totaltime.
    track_id_addr = 0x00014 # Fixed addresses of the old and the new NST tracks.
    if nst.FILE_TYPE == TMP: track_id_addr += 0x04 # The 4-byte blank (0x18).
    f.seek(track_id_addr, 0) # 8 (4+4) bytes, little endian U32+U32.
    (track_id, total_time) = nst.read_unpack('<2I', f)
    print(f'Track ID: {track_id}')

    nst.total_time = total_time / 100 # Totaltime in seconds.
    print(f'Total time: {nst.format_timedelta(nst.total_time)}')

    # Total Distance.
    if ver != 0: f.seek(0x00004, 1) # Skip.  4-byte offset to the old NST.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    print(f'Total distance: {round(nst.total_distance, 3)} km')

    # Calculate Net speed in km/h.
    #net_speed = nst.total_distance / (nst.total_time / 3600) # km/h
    #print(f'Net speed: {round(net_speed, 3)} km/h')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = nst.read_unpack('<2q', f)
    if stop_localtime <= start_localtime: stop_localtime = 0 # Avoid error.
    nst.START_LOCALTIME = nst.symbian_to_unix_time(start_localtime)
    nst.stop_localtime = nst.symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    print(f'Start: {nst.format_datetime(nst.START_LOCALTIME)}+07:00')
    #print(f'Stop : {nst.format_datetime(nst.stop_localtime)}+07:00')

    # Calculate Realtime, which is greater than totaltime if pause is used.
    #real_time = nst.stop_localtime - nst.START_LOCALTIME # Realtime in seconds.
    #print(f'Realtime: {nst.format_timedelta(real_time)}')

    # Calculate Gross speed in km/h.
    #gross_speed = nst.total_distance / (real_time / 3600) # km/h
    #print(f'Gross speed: {round(gross_speed, 3)} km/h')

    # User ID, please see config.dat.
    (nst.USER_ID, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'User id: {nst.USER_ID}')

    # Type of activity.  Walk, run, bicycle, etc. See ACTIVITIES in nst.py.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = nst.read_unpack('<H', f) # 2 bytes, little endian U16.
    nst.activity_type = (str(activity) if activity >= len(nst.ACTIVITIES) 
                         else nst.ACTIVITIES[activity])
    print(f'Activity: {nst.activity_type}')

    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases the name consists of 16-byte ASCII characters, e.g. 
    # '24/12/2019 12:34'.  They are not fully compatible with utf-8 in 
    # principle because they can be SCSU-encoded non-ASCII characters.
    track_name_addr = 0x00046 # This is the fixed address of the old NST track.
    if ver != 0: track_name_addr += 0x04 # Offset at total_distance (-> 0x4a).
    if nst.FILE_TYPE == TMP: track_name_addr += 0x04 # 4-byte blank (-> 0x4e).
    nst.track_name = nst.scsu_reader(f, track_name_addr)
    print(f'Track name: {nst.track_name}')

    # Starttime & Stoptime in UTC.
    # Due to the previous SCSU data field of variable length, this address is not fixed.
    f.seek(0x0137, 1) # Skip 312 bytes.  16 (8+8) bytes, little endian I64+I64.
    (start_time, stop_time) = nst.read_unpack('<2q', f)
    if stop_time <= start_time: stop_time = 0 # Avoid error.
    nst.START_TIME = nst.symbian_to_unix_time(start_time)
    nst.stop_time = nst.symbian_to_unix_time(stop_time)
    #print(f'Start Z: {nst.format_datetime(nst.START_TIME)}Z')
    #print(f'Stop Z : {nst.format_datetime(nst.stop_time)}Z')

    # Timezone can be calculated from the starttimes in Z and in localtime.
    nst.TZ_HOURS = int(nst.START_LOCALTIME - nst.START_TIME) / 3600

    # This will overwrite the realtime shown above.
    #real_time = nst.stop_time - nst.START_TIME # Realtime in seconds.
    #print(f'Realtime Z: {nst.format_timedelta(real_time)}')

    if ver == 2:
        # Read SCSU encoded user comment of variable length.
        comment_addr = 0x00222 # Fixed address of NST tracks.
        if nst.FILE_TYPE == TMP: comment_addr += 0x4 # The 4-byte blank (0x226).
        nst.comment = nst.scsu_reader(f, comment_addr)
        if nst.comment: print(f'Comment: {nst.comment}')

PRINT_PAUSE_LIST = False
def read_pause_and_track(f, start_address):
    """Reads the main part that consisits of a mixed pause-/track-data block.

    Args:
        f: the file object.
        start_address: the address of the main part.

    Returns:
        trackpt_store: the last trackpoint after processing.
    """
    def print_raw():
        times = f'{t_time} {nst.format_datetime(unix_time)}Z'
        # Remove symbiantime from trackpt if new NST and header0x07.
        trackpt_ = (trackpt[1:-1] if nst.NEW_FORMAT and header == 0x07 
                    else trackpt[1:])
        print(hex(f.tell()), hex(header), times, *trackpt_)

    def print_other_header_error():
        print(f'{header:#x} Error in the track point header: {track_count}, '
              f'{num_trackpt}' '\n' f'At address: {pointer:#x}')
        print(*trackpt)
        print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)

    f.seek(start_address, 0) # Go to the start address of the main part.
    # Read pause data.  There is no pause data in route file.
    (pause_list, pause_count) = (([], None) if nst.FILE_TYPE in {ROUTE, TMP} 
                                  else nst.read_pause_data(f))
    if PRINT_PAUSE_LIST and pause_list: nst.print_pause_list(pause_list)
    del pause_count # Not in use.
    #sys.exit(0)

    # Number of track points.
    num_trackpt = None # The number in the Rec*.tmp file is useless.

    # Trackpoint and pause data are labeled differently.  Each trackpoint 
    # following this label is always starting with 0x07 header, which means 
    # data with symbian_time. Read the trackpoint data exclusively because we 
    # don't have to use pause data to see the symbian_time.
    (pause_label, track_label) = (b'\x01\x00\x00\x00', b'\x02\x00\x00\x00')
    del pause_label # Not in use.

    switch_formats, TrackptStore = nst.define_data_structures_and_formats()
    header = 0x07 # Fixed trkpt headers in FILE_TYPE == TMP.
    process_trackpt, Trackpt, fmt = switch_formats[header]
    # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
    # 30 bytes (4+4+4+4+2+4+8).  y(+/-): North/South; x(+/-): East/West.

    # A temporal storage for the processed trackpt.
    trackpt_store = TrackptStore(unix_time=nst.START_TIME, t_time=0, dist=0)

    # For removing spikes.
    suspect_pause = None # A flag to handle the trackpoints after a pause.

    # The main loop to read the trackpoints.
    track_count = 0
    while True: # We don't know how many trackpoints exist in the temporal file.
        num_bytes = len(track_label)
        preceding_label = f.read(num_bytes)
        if len(preceding_label) < num_bytes: # Check end of file.
            break
        elif preceding_label != track_label:
            f.seek(1 - len(preceding_label), 1) # Seek forward for 1 byte.
            continue

        # if preceding_label == track_label:
        pointer = f.tell()
        header_fmt = '2B' # 2-byte header.
        num_bytes = struct.calcsize(header_fmt)
        headers = f.read(num_bytes)
        if len(headers) < num_bytes: # Check end of file.
            break

        (header, header1) = struct.unpack(header_fmt, headers)
        # Other headers which I don't know.
        if header != 0x07 or header1 not in {0x83, 0x82}:
            if not (header == 0x00 and header1 == 0x00):
                print_other_header_error()
            continue
            #break

        # if header == 0x07 and header1 in {0x83, 0x82}:
        num_bytes = struct.calcsize(fmt)
        track_data = f.read(num_bytes)
        if len(track_data) < num_bytes: # Check end of file.
            break

        trackpt = Trackpt._make(struct.unpack(fmt, track_data)) # Read and wrap.

        unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, dist = (
            process_trackpt(trackpt, trackpt_store)) # Using tp & the previous.
        print_raw() # For debugging purposes.

        # Remove spikes because there are lots of errors in the temporal file.
        # TODO: It is better to read and use both the trackpt and pause data to 
        #       correct bad timestamps, though errors also exist in pause data.
        # In most cases, the following two delta_s (~1 s) are equal each other.
        delta_unix_time = unix_time - trackpt_store.unix_time
        delta_t_time = t_time - trackpt_store.t_time
        good_unix_time = 0 < delta_unix_time < 1 * 3600 # Up to 1 hr.
        good_t_time = 0 <= delta_t_time < 5 * 60 # Up to 5 min.

        if track_count == 0 or suspect_pause:
            suspect_pause = False # No time correction; reset the flag.

        # There are four cases due to the two boolean conditions.
        elif good_unix_time and good_t_time:
            # Set the max of usual pause in seconds (suppose traffic signal).
            # Out of this range is most likely caused by a very long pause 
            # (e.g. lunch), but might be by an error.
            if not -0.5 < delta_unix_time - delta_t_time <= 130:
                (unix_time, t_time) = (
                    t + min(delta_unix_time, delta_t_time) for t in 
                    (trackpt_store.unix_time, trackpt_store.t_time))
                # Set the flag to see if this is due to a pause.  Seems to work 
                # because the first step after a pause is usually very short.
                suspect_pause = True
                print(f'Bad.  Two distinct delta_s at: {hex(pointer)}')
        elif (not good_unix_time) and good_t_time:
            # Correct unixtime by using totaltime.
            unix_time = trackpt_store.unix_time + delta_t_time
            print(f'Bad unixtime at: {hex(pointer)}')
        elif (not good_unix_time) and (not good_t_time):
            # Add 0.2 s (should be < 1.0) to both as a compromise; better than 
            # step over the next.  They are adjusted within a couple of steps.
            (unix_time, t_time) = (
                t + 0.2 for t in
                (trackpt_store.unix_time, trackpt_store.t_time))
            print(f'Bad unixtime and totaltime at: {hex(pointer)}')
        else: # good_unix_time and (not good_t_time)
            # Correct totaltime by using unixtime.
            t_time = trackpt_store.t_time + delta_unix_time
            print(f'Bad totaltime at: {hex(pointer)}')

        if track_count > 0: # Use previous values for spikes in y, x, z 
            # and total_distance.  Interpolation would be a better choice.
            if abs(trackpt_store.y_degree - y_degree) >= 0.001: # degree.
                y_degree = trackpt_store.y_degree
                print(f'Bad y at: {hex(pointer)}')
            if abs(trackpt_store.x_degree - x_degree) >= 0.001:
                x_degree = trackpt_store.x_degree
                print(f'Bad x at: {hex(pointer)}')
            if abs(trackpt_store.z_ax - z_ax) >= 500: # meter.
                z_ax = trackpt_store.z_ax
        if not 0 <= d_dist < 10**5: # 1 cm * 10**5 = 1 km.
            d_dist = 0
            dist = trackpt_store.dist

        trackpt_store = TrackptStore(
            unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
            x_degree=x_degree, z_ax=z_ax, v=v, d_dist=d_dist, 
            dist=dist, track_count=track_count, file_type=nst.FILE_TYPE)

        nst.store_trackpt(trackpt_store)

        track_count += 1

    return trackpt_store

WRITE_FILE = True
def main():
    in_file = args_usage() # Arguments and help.

    with in_file.open(mode='rb') as f:
        version = check_file_type_version(f) # FILE_TYPE(int), NEW_FORMAT(bool).
        (gpx, nst.gpx_target) = nst.initialize_gpx()

        # Start address of the main part (mixed pause and trackpoint data).
        # We don't read the address from the file because it is useless.
        start_address = 0x250 # Not quite sure if this is the best point.

        # Read information part of track/route files.
        parse_track_informations(f, version) # START_*TIME, TZ_HOURS.

        # Read the main part consisting a pause- and a trackpoint-data blocks.
        trackpt_store = read_pause_and_track(f, start_address)

    nst.add_gpx_summary(gpx, trackpt_store)

    write_file = getenv('GPX_WRITE_FILE') or WRITE_FILE
    gpx_path = in_file.with_suffix('.gpx') if write_file else None
    nst.finalize_gpx(gpx, gpx_path) # Gpx xml to a file or print (if None).


if __name__ == '__main__':
    main()
