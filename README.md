# Read-Symbian-SportsTracker-file -- How to read binary dat files.
 This python script, `convert_nst_files_to_gpx.py`, describes how you can read **symbian (Nokia) Sports Tracker files (W\*.dat and R\*.dat)** 
 stored in your phone as **binary format**.  You can use this code, as it is, to **convert from dat to gpx** by using 
[gpxpy](https://github.com/tkrajina/gpxpy).

 The code was tested with > 1000 of track log files copied from my Nokia phone equipped with GPS receiver, never tested with heart-rate 
 sensor, though...

 There is still a few unknown part in the track logs.  So, your [feedback](https://github.com/ekspla/Read-Symbian-SportsTracker-file/issues) is welcomed.

## How to use
Install from [PyPI](https://pypi.org/project/symbian-sports-tracker/)
```Shell
pip install symbian-sports-tracker
```

alternatively from github as follows:
```Shell
pip install "git+https://github.com/ekspla/Read-Symbian-SportsTracker-file.git@pip_install"
```

Now you can run `convert_nst_files_to_gpx input_filename.dat > output_filename.gpx` where input_filename.dat is the name of the track or route 
file.

## Detailed explanation
This package consists of four \*.py files.  `nst.py` and `scsu.py` are pure library modules while `convert_nst_files_to_gpx.py` and 
`convert_nst_rec_to_gpx.py` are scripts using the modules.

`convert_nst_files_to_gpx.py` works also for track/route files created by **the old Nokia Sports Tracker**, whose format is a bit different from the new 
version released from [Sports Tracking Technologies Ltd](http://www.sports-tracker.com/).  For details, please see the codes.  (1-byte instead 
of 2-byte long header, start address of trackpoint is different, etc.)

The version number of the file is stored as WORD at 0x0008.
- Track log files of the old Nokia SportsTracker (ver0):                version < 10000.
- Track/Route files of the old Nokia SportsTracker (ver1):     10000 <= version < 20000.
- Track log files of Symbian SportsTracker (ver2):             20000 <= version.

The track reading function was tested for the old and the new NST versions of 9991-9998, 10102 and 20001-20002, while 
the route reading one was tested for version of 11400.

 The file formats of symbian are completely different from those of Android and iOS.

 These codes are **not based on reverse engineering of the app** itself, but on careful analysis of the track log files.
 
 **Non ASCII** (non-alphanumeric) **characters** contained in the track log files that are encoded by [SCSU](https://www.unicode.org/reports/tr6/tr6-4.html) 
 are read by using an external module, `scsu.py`.  This is a ported version of [Czyborra's decoder written in C](http://czyborra.com/scsu/), 
 `references/scsu.c`.  (Characters of Arabic, Bengali, Chinese, German, Hindi, Japanese, Portuguese, Punjabi, Russian, Spanish and surrogate pairs 
 were tested, see `test_scsu/`.)

## Files in the phone
There are files as followings in the directory named **_drive_name_:\SportsTracker\\** (old version) or **_drive_name_:\SportsTracker2\\** 
(new version).  _Drive_name_ (C, D, E, etc.) depends on where you installed the app (phone memory, sd card, etc.).

- `config.dat`: contains a lot of **personal data**, including _id--name_ lookup tables of user and activity, etc. 
- `W*.dat`: **track log** files in binary format.  The file formats of **the new and the old versions** are slightly different each other as
mentioned before.  [A fetched sample file (the old format)](https://www.elektroda.pl/rtvforum/topic1416097.html), 
[another one (the new format)](https://sourceforge.net/p/gpsbabel/mailman/message/26219411/) and the converted gpx files are in `references/`.
- `R*.dat`: **route** files of **the old version** in binary format.  The file format, though it lacks for timestamps, is very similar to that of 
track log of the old version NST.
- `Rec*.tmp`: **temporal track log files** we see on application crash.  More example is needed, yet [a file useful to test was obtained from 
the internet](https://forum.allnokia.ru/viewtopic.php?t=65299&start=210).  The file format seems to be very simple, see 
`references/Rec211109168_dump.txt` (a hex dump file with comments), `convert_nst_rec_to_gpx.py` (the script)  and 
`references/Rec211109168.gpx` (the converted gpx file) for details. 

## Limitation
- Units other than Metrics (km and km/h), such as Imperial (mi and mph) and Nautical (nm and kn), were not tested.

## TODO
- A few unknown field in the track points.
- Support for heart rate in track log files of the new version (example files needed).
- A test for a file in the West or South hemisphere, supposed to work though.  The codes were only tested for the real files in the North-East 
(both the latitudes and the longitudes of positive values).

## License
This software is released under the LGPL v2.1 License.

## Reference
- [Sports Tracker - Wikipedia](https://en.wikipedia.org/wiki/Sports_Tracker)
- [Standard Compression Scheme for Unicode - Wikipedia](https://en.wikipedia.org/wiki/Standard_Compression_Scheme_for_Unicode)
- [A Standard Compression Scheme for Unicode - Unicode Technical Standard #6](https://www.unicode.org/reports/tr6/tr6-4.html)
- [The SCSU charset -- Roman Czyborra's decoder](http://czyborra.com/scsu/)
