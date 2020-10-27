# Read-Symbian-SportsTracker-file -- How to read binary dat files.
 This python script, `convert_NST_to_GPX.py`, describes how you can read **symbian (Nokia) Sports Tracker log files (dat)** stored 
in your phone as **binary format**.  You can use this code, as it is, to **convert from dat to gpx** by using [gpxpy](https://github.com/tkrajina/gpxpy).

 The code was tested with > 1000 of track log files copied from my Nokia phone equipped 
with GPS receiver, never tested with heart-rate sensor, though...

 There is still a few unknown part in the track logs.  So, your feedback is welcomed.

 For track log files created by the old Nokia Sports Tracker, use `convert_oldNST_to_GPX.py`. 
This is because the file format of old version Sports Tracker seems different from those 
of the new version released from [Sports Tracking Technologies Ltd](http://www.sports-tracker.com/).  For details, please see 
the script.  (1-byte instead of 2-byte long header, start address of trackpoint is different, 
etc.)

 This code is **not based on reverse engineering of the app.**, but is based on careful analysis of the track log files.
 
## TODO
- A few unknown fields in the track points.
- Support for heart rate in track log files of the new version.
- Read and check the version number of Sports Tracker app. used to create the track log files.  It is stored as WORD at 0x0008.
