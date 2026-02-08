# HOWTO: Conversion from Symbian Time to Unix Time, and v.v.
(c) 2026, [ekspla](https://github.com/ekspla/Read-Symbian-SportsTracker-file/references/symbian_time.md)

## Introduction
I found very recently that there were lots of wrong explanations on the internet how to deal 
with *Symbian time*. 
Symbian time uses 64-bit timestamp of microsecond resolution with *Gregorian calender* starting 
1st Jan. 1 AD. 
Because there were ways to handle Gregorian calender back in the days before it was introduced 
in 1582, these confusion might occur.  

## A brief history 
The old *Julian calendar* by Julius Caesar has a simple rule of leap year every 4th year. 
Because of its limited precision, accumulated error of about 10 days has been adjusted and 
additional rules of leap year (see below) has been introduced by Gregorian calender. 
Gregorian calender started at 15 Oct. 1582 with 10-day offset to its successor, Julian calender.  

Gregorian leap-year rule.  

| Year | Leap year ? |
| ---- | --------- |
| 1600 | leap year |
| 1700 |           |
| 1800 |           |
| 1900 |           |
| 2000 | leap year |
| 2100 |           |

## The ways to handle backwards

  - Proleptic Gregorian Calender  
Most of the current databases use so called *Proleptic Gregorian Calender*, that is supposed to be 
the Gregorian calendar extended to backwards. 
In this way, difference in Gregorian time (in sec) and unixtime is calculated as 62167219200 (A few 
reference shows it as 62167132800 because of 1 day difference at start, which is caused by the 
difference in definition of 1st Jan. 1 AD.)  
This value was also confirmed from [Wolfram Alpha in Wolfram site](https://www.wolframalpha.com/):  

719528 days \* 24 \* 60 \* 60 = 62167219200 sec.  

  - Symbian Time  
Symbian uses *a mixed way of Julian and Gregorian* calenders; it preserve the old rule before the 
Gregorian. 
As the result year 1500 (before Gregorian) is leap year, but 1700 (after Gregorian) is not.  

| Year | Symbian | Proleptic Gregorian |
| ---- | --------- | --------- |
| 1700 |           |           |
| 1600 | leap year | leap year |
| 1500 | leap year |           |
| 1400 | leap year |           |
| 1300 | leap year |           |
| 1200 | leap year | leap year |
| 1100 | leap year |           |
| 1000 | leap year |           |
|  900 | leap year |           |
|  800 | leap year | leap year |
|  700 | leap year |           |
|  600 | leap year |           |
|  500 | leap year |           |
|  400 | leap year | leap year |
|  300 | leap year |           |
|  200 | leap year |           |
|  100 | leap year |           |

As shown in the table above, Symbian time is greater than proleptic Gregorian by *12 days*.  

12 days \* 24 hours \* 60 min \* 60 sec = 1036800 sec.  

By addition of 62167219200 sec in proleptic Gregorian as shown above, we obtain the difference in 
Symbian's way as  

62167219200 + 1036800 = 62168256000 sec.  
