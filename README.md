# Read-Symbian-SportsTracker-file
This python script describes how you can read symbian SportsTracker log files in binary format.

The code was tested with > 1000 of track log files copied from my Nokia phone equipped with GPS,
never tested with heart-rate sensor, though...

There are still a few unknown parts in the track logs.  So, your feedbacks are welcomed.

You have to modify the code a bit to read old-version Nokia SportsTracker files because of 
slightly different format. 
(1-byte instead of 2-byte long header, start address of trackpoints is different, etc.)
