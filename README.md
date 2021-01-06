# Read-Symbian-SportsTracker-file -- How to read binary dat files.
 This python script, `convert_NST_to_GPX.py`, describes how you can read **symbian (Nokia) Sports Tracker log files (.dat)** stored 
in your phone as **binary format**.  You can use this code, as it is, to **convert from dat to gpx** by using 
[gpxpy](https://github.com/tkrajina/gpxpy).

 The code was tested with > 1000 of track log files copied from my Nokia phone equipped 
with GPS receiver, never tested with heart-rate sensor, though...

 There is still a few unknown part in the track logs.  So, your feedback is welcomed.

 For track log files created by **the old Nokia Sports Tracker**, use `convert_oldNST_to_GPX.py`. 
This is because the file format of the old version Sports Tracker is a bit different from those 
of the new version released from [Sports Tracking Technologies Ltd](http://www.sports-tracker.com/).  For details, please see 
the script.  (1-byte instead of 2-byte long header, start address of trackpoint is different, 
etc.)

The version number of the app used to create the file is stored as WORD at 0x0008.
- Track log files of the old Nokia SportsTracker:          version < 10000.
- Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
- Track log files of Symbian SportsTracker:       20000 <= version.

The track log readers of the oldNST and the new NST, respectively, were tested for versions of 9991-9998 and 20001-20002.

 The file formats of symbian are completely different from those of Android and iOS.

 These codes are **not based on reverse engineering of the app** itself, but on careful analysis of the track log files.
 
 Non ASCII (alpha numeric) strings contained in the track log files that are encoded by [SCSU](https://www.unicode.org/reports/tr6/tr6-4.html) 
 are decoded by using an external module, `scsu.py`.  This is a ported version of [Czyborra's decoder written in C](http://czyborra.com/scsu/), 
 `./references/scsu.c`.

## Files in the phone
There are files as followings in the directory named **_drive_name_:\SportsTracker\\** (old version) or **_drive_name_:\SportsTracker2\\** 
(new version).  _Drive_name_ (C, D, E, etc.) depends on where you installed the app (phone memory, sd card, etc.).

- `config.dat`: contains a lot of **personal data**, including _id--name_ lookup tables of user and activity, etc. 
- `W*.dat`: **track log** files in binary format.  The file formats of **the new and the old versions** are slightly different each other as
mentioned before. 
- `R*.dat`: **route** files of **the old version** in binary format.  The file format, though it lacks timestamps, is very similar to that of 
track log.  See `convert_oldNST_route_to_GPX.py` for details.
- `Rec*.tmp`: **temporal track log files** we see on application crash.  More example is needed, yet [a file useful to test was obtained from 
the internet](https://forum.allnokia.ru/viewtopic.php?t=65299&start=210).  The file format seems to be very simple, see 
`./references/Rec211109168_dump.txt` (a hex dump file with comments) and `convert_NST_Rec_to_GPX.py` (the script) for details.  The converted 
file (`./references/Rec211109168.gpx`) is also shown.

## Limitation
- Units other than Metrics (km and km/h), such as Imperial (mi and mph) and Nautical (nm and kn), were not tested.

## TODO
- A few unknown field in the track points.
- Support for heart rate in track log files of the new version (example files needed). 

## Reference
- [Sports Tracker - Wikipedia](https://en.wikipedia.org/wiki/Sports_Tracker)
- [Standard Compression Scheme for Unicode - Wikipedia](https://en.wikipedia.org/wiki/Standard_Compression_Scheme_for_Unicode)
- [A Standard Compression Scheme for Unicode - Unicode Technical Standard #6](https://www.unicode.org/reports/tr6/tr6-4.html)
- [The SCSU charset -- Roman Czyborra's decoder](http://czyborra.com/scsu/)
