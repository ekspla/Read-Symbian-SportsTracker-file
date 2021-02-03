#coding:utf-8
#
# (c) 2020 ekspla.
# This code is written by ekspla and distributed at the following site under 
# LGPL v2.1 license.  https://github.com/ekspla/Read-Symbian-SportsTracker-file
"""This script reads temporal track log files of SportsTracker.
"""
import sys
import struct
from collections import namedtuple
from pathlib import Path

import nst


def print_raw_track(): # Remove symbiantime from trackpt if NST and header0x07.
    times = f'{t_time} {nst.format_datetime(unix_time)}Z'
    trackpt_ = trackpt[1:-1] if nst.NST and header == 0x07 else trackpt[1:]
    print(hex(f.tell()), hex(header), times, *trackpt_)

def print_other_header_error():
    print(f'{header:#x} Error in the track point header: {track_count}, '
          f'{NUM_TRACKPT}' '\n' f'At address: {pointer:#x}')
    print(*trackpt)
    print(t_time, y_degree, x_degree, z_ax, v, dist, unix_time)


# Arguments and help.
argvs = sys.argv
argc = len(argvs)
if argc < 2:
    print(f"""Usage: # python {argvs[0]} input_filename\n
        This script reads temporal track log files (Rec*.tmp) of symbian 
        SportsTracker.  Log files with heart-rate sensor were not tested.""")
    sys.exit(0)
#print(argvs[1])
nst.in_file = Path(argvs[1])
#print(nst.in_file)

with nst.in_file.open(mode='rb') as f:

    # Check if it is the correct file.
    # Chunks in the temporal file always start with b'\x00\x00\x00\x00' blank.
    # Due to this blank, there is a 4-byte offset to the addresses shown below.
    #f.seek(0x00000, 0)
    # 12 (4+4+4) bytes, little endian U32+U32+U32.
    (APPLICATION_ID, nst.FILE_TYPE, blank) = nst.read_unpack('<3I', f)
    (CONFIG, TRACK, ROUTE, TMP) = (0x1, 0x2, 0x3, 0x4) # FILE_TYPE.
    if APPLICATION_ID != 0x0e4935e8 or nst.FILE_TYPE != TMP or blank != 0x0:
        print(f'Unexpected file type: {nst.FILE_TYPE}')
        sys.exit(1)

    # Preliminary version check.
    #f.seek(0x00008 + 0x4, 0) # Go to 0x00008 + 0x4, this address is fixed.
    (version, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'Version: {version}')
    (nst.OLDNST, nst.OLDNST_ROUTE, nst.NST) = (
        version < 10000, 10000 <= version < 20000, 20000 <= version)
    if not nst.NST:
        print(f'Unexpected version number: {version}')
        sys.exit(1)

    gpx, nst.gpx_target = nst.initialize_gpx(nst.FILE_TYPE)

    # Start address of the main part (mixed pause and trackpoint data).
    # We don't read the address from the file because it is useless.
    START_ADDRESS = 0x250 # Not quite sure if this is the best starting point.

    # Track ID and Totaltime.
    track_id_addr = 0x00014 # Fixed addresses of oldNST and the new NST tracks.
    if nst.FILE_TYPE == TMP: track_id_addr += 0x04 # The 4-byte blank (0x18).
    f.seek(track_id_addr, 0) # 8 (4+4) bytes, little endian U32+U32.
    (TRACK_ID, total_time) = nst.read_unpack('<2I', f)
    print(f'Track ID: {TRACK_ID}')

    nst.total_time = total_time / 100 # Totaltime in seconds.
    print(f'Total time: {nst.format_timedelta(nst.total_time)}')

    # Total Distance.
    if nst.NST: f.seek(0x00004, 1) # Skip.  4-byte offset to oldNST due to this.
    (total_distance, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    nst.total_distance = total_distance / 1e5 # Total distance in km.
    print(f'Total distance: {round(nst.total_distance, 3)} km')

    # Starttime and Stoptime in localtime.
    # 16 (8+8) bytes, little endian I64+I64.
    (start_localtime, stop_localtime) = nst.read_unpack('<2q', f)
    nst.start_localtime = nst.symbian_to_unix_time(start_localtime)
    nst.stop_localtime = nst.symbian_to_unix_time(stop_localtime)

    # Change the suffix according to your timezone, because there is no 
    # timezone information in Symbian.  Take difference of starttime in 
    # localtime and those in UTC (see below) to see the timezone+DST.
    print(f'Start: {nst.format_datetime(nst.start_localtime)}+07:00')
    #print(f'Stop : {nst.format_datetime(nst.stop_localtime)}+07:00')

    # User ID, please see config.dat.
    (nst.USER_ID, ) = nst.read_unpack('<I', f) # 4 bytes, little endian U32.
    print(f'User id: {nst.USER_ID}')

    # Type of activity.  Walk, run, bicycle, etc. See config.dat for details.
    f.seek(0x00004, 1) # Skip 4 bytes.
    (activity, ) = nst.read_unpack('<H', f) # 2 bytes, little endian U16.
    nst.description = (str(activity) if activity >= len(nst.ACTIVITIES) 
                       else nst.ACTIVITIES[activity])
    print(f'Activity: {nst.description}')

    # Read SCSU encoded name of the track, which is usually the datetime.
    # In most cases the name consists of 16-byte ASCII characters, e.g. 
    # '24/12/2019 12:34'.  They are not fully compatible with utf-8 in 
    # principle because they can be SCSU-encoded non-ASCII characters.
    track_name_addr = 0x00046 # This is the fixed address of the oldNST track.
    if nst.NST: track_name_addr += 0x04 # Offset at total_distance (-> 0x4a).
    if nst.FILE_TYPE == TMP: track_name_addr += 0x04 # 4-byte blank (-> 0x4e).
    nst.track_name = nst.scsu_reader(f, track_name_addr)
    print(f'Track name: {nst.track_name}')

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

    # Read SCSU encoded user comment of variable length.
    comment_addr = 0x00222 # Fixed address of NST tracks.
    if nst.FILE_TYPE == TMP: comment_addr += 0x4 # The 4-byte blank (0x226).
    nst.comment = nst.scsu_reader(f, comment_addr) # This address is fixed.
    if nst.comment: print(f'Comment: {nst.comment}')


    f.seek(START_ADDRESS, 0) # Go to the start address of the main part.
    # Read pause data.
    (pause_list, pause_count) = ( # Do not read pause data if ROUTE or TMP.
        ([], None) if nst.FILE_TYPE in {ROUTE, TMP} else nst.read_pause_data(f))
    #print_pause_list(pause_list) # For debugging purposes.
    #sys.exit(0)

    # Number of track points.
    NUM_TRACKPT = None # The number in the Rec*.tmp file is useless.
    # Go to the first data.

    track_count = 0

    # Factory functions for creating named tuples.
    TYPE00 = 't_time, y_ax, x_ax, z_ax, v, d_dist'
    TYPE80 = 'dt_time, dy_ax, dx_ax, dz_ax, dv, d_dist'
    TYPEC0 = 'dt_time, unknown3, dy_ax, dx_ax, unknown4, dz_ax, dv, d_dist'
    if nst.NST: # The fields shown below are added in the new version.
        TYPE00 += ', symbian_time'
        TYPE80, TYPEC0 = (t + ', unknown1, unknown2' for t in (TYPE80, TYPEC0))
    TYPE_STORE = ('unix_time, t_time, y_degree, x_degree, z_ax, v, d_dist, '
                  'dist, track_count, file_type')
    TrackptType00 = namedtuple('TrackptType00', TYPE00)
    TrackptType80 = namedtuple('TrackptType80', TYPE80)
    TrackptTypeC0 = namedtuple('TrackptTypeC0', TYPEC0)
    TrackptStore = namedtuple('TrackptStore', TYPE_STORE)
    TrackptStore.__new__.__defaults__ = (None,) * len(TrackptStore._fields)

    # For oldNST_route, use mtime as start_time because the start/stop times 
    # stored are always 0 which means January 1st 0 AD 00:00:00.
    if nst.OLDNST_ROUTE: nst.start_time = nst.in_file.stat().st_mtime
    trackpt_store = TrackptStore() # A temporal storage to pass the trackpt.
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
            header_fmt = '2B' # 2-byte header.
            num_bytes = struct.calcsize(header_fmt)
            headers = f.read(num_bytes)
            if len(headers) < num_bytes: # Check end of file.
                break
            (header, header1) = struct.unpack(header_fmt, headers)

            if header == 0x07 and header1 in {0x83, 0x82}:
                (Trackpt, fmt) = (TrackptType00, '<I3iHIq')
                # (t_time, y_ax, x_ax, z_ax, v, d_dist, symbian_time)
                # 30 bytes (4+4+4+4+2+4+8).  y(+/-): N/S; x(+/-): E/W.
                num_bytes = struct.calcsize(fmt)
                track_data = f.read(num_bytes)
                if len(track_data) < num_bytes: # Check end of file.
                    break
                # Namedtuple wrapped.
                trackpt = Trackpt._make(struct.unpack(fmt, track_data))
                t_time = trackpt.t_time / 100 # Totaltime / seconds.

                # The lat. and lon. are in I32s (DDDmm mmmm format).
                y_degree = nst.dmm_to_decdeg(trackpt.y_ax)# Decimal degrees.
                x_degree = nst.dmm_to_decdeg(trackpt.x_ax)

                z_ax = trackpt.z_ax / 10 # Altitude / meter.
                v = trackpt.v / 100 * 3.6 # Velocity: v (m/s) * 3.6 = v (km/h).
                dist = trackpt_store.dist + trackpt.d_dist / 1e5 # Distance/km.
                unix_time = nst.symbian_to_unix_time(trackpt.symbian_time)
                print_raw_track() # For debugging purposes.

                # Remove spikes: there are lots of errors in the tmp file.
                # TODO: It is better to read and use both the trackpt and pause 
                #       data to correct bad timestamps in the temporal file.
                # In most cases, the two delta_s (~1 s) are equal each other.
                delta_unix_time = unix_time - trackpt_store.unix_time
                delta_t_time = t_time - trackpt_store.t_time
                good_unix_time = 0 < delta_unix_time < 1 * 3600 # Up to 1 hr.
                good_t_time = 0 <= delta_t_time < 5 * 60 # Up to 5 min.

                if track_count == 0 or suspect_pause:
                    suspect_pause = False # No time correction; reset the flag.

                # There are four cases due to the two boolean conditions.
                elif good_unix_time and good_t_time:
                    # Set the max of usual pause (suppose traffic signal).
                    # Out of this range is most likely caused by a very long 
                    # pause (e.g. lunch), but might be by an error.
                    if not -0.5 < delta_unix_time - delta_t_time <= 130:
                        (unix_time, t_time) = (
                            t + min(delta_unix_time, delta_t_time) for t in 
                            (trackpt_store.unix_time, trackpt_store.t_time))
                        # Set the flag to see if this is because of a pause.
                        suspect_pause = True
                        print(f'Bad.  Two distinct delta_s at: {hex(pointer)}')
                elif (not good_unix_time) and good_t_time:
                    # Correct unixtime by using totaltime.
                    unix_time = trackpt_store.unix_time + delta_t_time
                    print(f'Bad unixtime at: {hex(pointer)}')
                elif (not good_unix_time) and (not good_t_time):
                    # Add 0.2 s (should be < 1.0 s) to both, as a compromise.
                    (unix_time, t_time) = (
                        t + 0.2 for t in
                        (trackpt_store.unix_time, trackpt_store.t_time))
                    print(f'Bad unixtime and totaltime at: {hex(pointer)}')
                else: # good_unix_time and (not good_t_time)
                    # Correct totaltime by using unixtime.
                    t_time = trackpt_store.t_time + delta_unix_time
                    print(f'Bad totaltime at: {hex(pointer)}')

                if track_count > 0: # Use previous values for spikes in y, x, z 
                    # and total_distance.  Interpolation would be better choice.
                    if abs(trackpt_store.y_degree - y_degree) >= 0.001: # deg.
                        y_degree = trackpt_store.y_degree
                        print(f'Bad y at: {hex(pointer)}')
                    if abs(trackpt_store.x_degree - x_degree) >= 0.001:
                        x_degree = trackpt_store.x_degree
                        print(f'Bad x at: {hex(pointer)}')
                    if abs(trackpt_store.z_ax - z_ax) >= 500: # Meter.
                        z_ax = trackpt_store.z_ax
                if not 0 <= dist - trackpt_store.dist < 1: # Up to 1 km.
                    dist = trackpt_store.dist

            else: # Other headers which I don't know.
                if not (header == 0x00 and header1 == 0x00):
                    print_other_header_error()
                continue
                #break

            trackpt_store = TrackptStore(
                unix_time=unix_time, t_time=t_time, y_degree=y_degree, 
                x_degree=x_degree, z_ax=z_ax, v=v, d_dist=trackpt.d_dist / 1e5, 
                dist=dist, track_count=track_count, file_type=nst.FILE_TYPE)
            nst.store_trackpt(trackpt_store)

            track_count += 1

        else:
            f.seek(-3, 1) # Seek forward (4 - 3 = +1 byte).

nst.add_gpx_summary(gpx, trackpt_store)
WRITE_FILE = True
gpx_path = (Path(str(nst.in_file)[:-3] + 'gpx') if WRITE_FILE
            else None)
nst.finalize_gpx(gpx, gpx_path) # Gpx to a file or print (if None).
