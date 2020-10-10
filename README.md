# Read-Symbian-SportsTracker-file
This python script describes how you can read symbian Sports Tracker log files stored in 
your phone as binary format.

The code was tested with > 1000 of track log files copied from my Nokia phone equipped 
with GPS receiver, never tested with heart-rate sensor, though...

There is still a few unknown part in the track logs.  So, your feedback is welcomed.

I had to modify the code a bit to read old-version Nokia SportsTracker files because of 
slightly different format.  For details, please see the script named as 'convert_oldNST_to_GPX.py'.
(1-byte instead of 2-byte long header, start address of trackpoint is different, etc.)
