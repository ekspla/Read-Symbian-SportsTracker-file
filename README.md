# Read-Symbian-SportsTracker-file -- How to read binary dat files.
 This python script, `convert_NST_to_GPX.py`, describes how you can read **symbian (Nokia) Sports Tracker log files (.dat)** stored 
in your phone as **binary format**.  You can use this code, as it is, to **convert from dat to gpx** by using [gpxpy](https://github.com/tkrajina/gpxpy).

 The code was tested with > 1000 of track log files copied from my Nokia phone equipped 
with GPS receiver, never tested with heart-rate sensor, though...

 There is still a few unknown part in the track logs.  So, your feedback is welcomed.

 For track log files created by the old Nokia Sports Tracker, use `convert_oldNST_to_GPX.py`. 
This is because the file format of the old version Sports Tracker is a bit different from those 
of the new version released from [Sports Tracking Technologies Ltd](http://www.sports-tracker.com/).  For details, please see 
the script.  (1-byte instead of 2-byte long header, start address of trackpoint is different, 
etc.)

The version number of the app used to create the file is stored as WORD at 0x0008.
- Track log files of the old Nokia SportsTracker:          version < 10000.
- Route files of the old Nokia SportsTracker:     10000 <= version < 20000.
- Track log files of Symbian SportsTracker:       20000 <= version.

The track log readers of oldNST and the new NST, respectively, were tested for versions of 9991-9998 and 20001-20002.

 The file formats of symbian are completely different from those of Android and iOS.

 These codes are **not based on reverse engineering of the app.** itself, but on careful analysis of the track log files.
 
 Non ASCII (alpha numeric) strings contained in the track log files that are encoded by [SCSU](https://www.unicode.org/reports/tr6/tr6-4.html) are decoded by using an external module, `scsu.py`.  This is a translated version of [Czyborra's decoder written in C](http://czyborra.com/scsu/), `scsu.c`.

## Limitation
- Units other than Metrics (km and km/h), such as Imperial (mi and mph) and Nautical (nm and kn), were not tested.

## TODO
- Read and process the temporally `Rec*.tmp` files.  These files are used to generate compressed track log files, but we see them only when application crashes.  A file useful to test was obtained in the internet, but more example is needed.
- A few unknown fields in the track points.
- Support for heart rate in track log files of the new version.

## Reference
- [Sports Tracker - Wikipedia](https://en.wikipedia.org/wiki/Sports_Tracker)
- [Standard Compression Scheme for Unicode - Wikipedia](https://en.wikipedia.org/wiki/Standard_Compression_Scheme_for_Unicode)
- [A Standard Compression Scheme for Unicode - Unicode Technical Standard #6](https://www.unicode.org/reports/tr6/tr6-4.html)
- [The SCSU charset -- Roman Czyborra's decoder](http://czyborra.com/scsu/)
