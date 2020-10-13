# Read-Symbian-SportsTracker-file
 This python script describes how you can read symbian Sports Tracker log files (dat) stored 
in your phone as binary format.  You can use this code, as it is, to convert from dat to gpx.

 The code was tested with > 1000 of track log files copied from my Nokia phone equipped 
with GPS receiver, never tested with heart-rate sensor, though...

 There is still a few unknown part in the track logs.  So, your feedback is welcomed.

 For track log files created by the old Nokia Sports Tracker, use 'convert_oldNST_to_GPX.py.' 
This is because the file format of old version Sports Tracker seems different from those 
of the new version released from Sports Tracking Technologies Ltd.  For details, please see 
the script.  (1-byte instead of 2-byte long header, start address of trackpoint is different, 
etc.)
